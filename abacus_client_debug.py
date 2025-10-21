import requests
import json
from typing import Optional, Dict, Any


class AbacusClientFixed:
    """Cliente corrigido para comunicação com a API da Abacus."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        """
        Inicializa o cliente da API Abacus.
        
        Args:
            api_key (str): Chave da API da Abacus
            model (str): Modelo a ser usado (padrão: gemini-2.5-flash)
        """
        self.api_key = api_key
        self.model = model
        
        # Lista de possíveis URLs da API para testar
        self.possible_urls = [
            "https://api.abacus.ai/v1/chat/completions",
            "https://api.abacus.ai/chat/completions", 
            "https://abacus.ai/api/v1/chat/completions",
            "https://chat.abacus.ai/v1/completions",
            "https://api.abacus.ai/v1/completions"
        ]
        
        self.base_url = None
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "AbacusClient/1.0"
        }
    
    def find_working_endpoint(self) -> bool:
        """Encontra o endpoint correto da API testando diferentes URLs."""
        for url in self.possible_urls:
            try:
                # Teste simples com uma requisição HEAD ou GET para verificar disponibilidade
                test_payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 1
                }
                
                response = requests.post(url, headers=self.headers, json=test_payload, timeout=10)
                
                if response.status_code in [200, 400, 401]:  # 400/401 indicam que o endpoint existe
                    self.base_url = url
                    print(f"Endpoint encontrado: {url}")
                    return True
                    
            except Exception as e:
                print(f"Testando {url}: {str(e)}")
                continue
                
        return False
    
    def send_message(self, message: str, conversation_history: Optional[list] = None) -> Dict[str, Any]:
        """
        Envia uma mensagem para a API e retorna a resposta.
        """
        # Se ainda não encontrou o endpoint, tenta encontrar
        if not self.base_url:
            if not self.find_working_endpoint():
                return {
                    "success": False,
                    "error": "Nenhum endpoint válido encontrado",
                    "message": "Não foi possível conectar com a API da Abacus. Verifique sua chave de API."
                }
        
        try:
            # Constrói as mensagens
            messages = []
            
            # Mensagem de sistema
            messages.append({
                "role": "system",
                "content": "Você é um assistente útil e prestativo. Responda de forma clara, educada e objetiva."
            })
            
            # Histórico da conversa
            if conversation_history:
                messages.extend(conversation_history)
            
            # Mensagem atual do usuário
            messages.append({
                "role": "user",
                "content": message
            })
            
            # Payload da requisição
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1000,
                "stream": False
            }
            
            print(f"Enviando requisição para: {self.base_url}")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            
            # Fazer a requisição
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            print(f"Status da resposta: {response.status_code}")
            print(f"Resposta: {response.text[:500]}...")
            
            # Verificar status da resposta
            if response.status_code == 401:
                return {
                    "success": False,
                    "error": "Chave de API inválida",
                    "message": "Sua chave de API parece estar incorreta. Verifique e tente novamente."
                }
            elif response.status_code == 403:
                return {
                    "success": False,
                    "error": "Acesso negado",
                    "message": "Acesso negado à API. Verifique suas permissões."
                }
            elif response.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "message": f"Erro na API (Status {response.status_code}). Tente novamente."
                }
            
            # Processar resposta
            response_data = response.json()
            
            # Verificar se a resposta tem o formato esperado
            if "choices" in response_data and len(response_data["choices"]) > 0:
                content = response_data["choices"][0].get("message", {}).get("content", "")
                if not content:
                    content = response_data["choices"][0].get("text", "")
            else:
                # Tentar formatos alternativos
                content = response_data.get("response", "")
                if not content:
                    content = response_data.get("message", "")
                if not content:
                    content = "Resposta recebida mas formato não reconhecido."
            
            return {
                "success": True,
                "message": content,
                "usage": response_data.get("usage", {}),
                "model": response_data.get("model", self.model),
                "raw_response": response_data
            }
            
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Timeout na requisição",
                "message": "A requisição demorou muito para responder. Tente novamente."
            }
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": "Erro de conexão",
                "message": "Não foi possível conectar com a API. Verifique sua conexão com a internet."
            }
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Erro ao decodificar JSON: {str(e)}",
                "message": "Resposta da API em formato inválido."
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Erro inesperado: {str(e)}",
                "message": f"Erro inesperado: {str(e)}"
            }
    
    def validate_connection(self) -> bool:
        """Valida se a conexão com a API está funcionando."""
        try:
            response = self.send_message("Teste de conexão")
            return response.get("success", False)
        except:
            return False