import requests
import json
import os
from typing import Optional, Dict, Any

try:
    # Preferir config centralizada se disponível
    from app.config import get_abacus_base_url
except Exception:
    def get_abacus_base_url(default: str = "https://routellm.abacus.ai/v1/chat/completions") -> str:  # type: ignore
        return os.getenv("ABACUS_BASE_URL", default)


class AbacusClient:
    """Cliente para comunicação com a API da Abacus."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        """
        Inicializa o cliente da API Abacus.
        
        Args:
            api_key (str): Chave da API da Abacus
            model (str): Modelo a ser usado (padrão: gemini-2.5-flash)
        """
        self.api_key = api_key
        self.model = model  # Modelo especificado (p.ex. gemini-2.5-pro)
        # Base URL pode ser sobrescrita por ABACUS_BASE_URL
        self.base_url = get_abacus_base_url("https://routellm.abacus.ai/v1/chat/completions")
        # Alguns ambientes aceitam 'Authorization: Bearer', outros 'x-api-key'. Vamos enviar ambos.
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }
        # Parâmetros opcionais do .env
        try:
            self.temperature = float(os.getenv("TEMPERATURE", "0.7"))
        except ValueError:
            self.temperature = 0.7
        try:
            self.max_tokens = int(os.getenv("MAX_TOKENS", "1000"))
        except ValueError:
            self.max_tokens = 1000
        # Caminho opcional para um prompt de sistema externo
        self.system_prompt_path = os.getenv("SYSTEM_PROMPT_PATH", "system_prompt.md")
    
    def send_message(self, message: str, conversation_history: Optional[list] = None) -> Dict[str, Any]:
        """
        Envia uma mensagem para a API e retorna a resposta.
        
        Args:
            message (str): Mensagem do usuário
            conversation_history (list, optional): Histórico da conversa
            
        Returns:
            Dict[str, Any]: Resposta da API ou erro
        """
        try:
            # Constrói o histórico de mensagens
            messages = []
            
            # Adiciona mensagem de sistema para definir o comportamento do assistente
            # Carrega prompt externo, se existir; caso contrário, usa um fallback padrão
            system_text = None
            try:
                if self.system_prompt_path and os.path.isfile(self.system_prompt_path):
                    with open(self.system_prompt_path, "r", encoding="utf-8") as f:
                        system_text = f.read()
            except Exception:
                system_text = None
            if not system_text:
                system_text = (
                    "Você responde em português e usa a seção 'Contexto' quando disponível.\n"
                    "Siga este protocolo ao responder: 1) entenda a tarefa; 2) localize sinais/dados relevantes no Contexto; 3) calcule/extraia números; 4) redija resposta clara e objetiva com tabela/lista quando fizer sentido.\n"
                    "Apenas apresente a resposta final para o usuário; não mostre raciocínio intermediário."
                )
            messages.append({"role": "system", "content": system_text})
            
            # Adiciona histórico da conversa se fornecido
            if conversation_history:
                messages.extend(conversation_history)
            
            # Adiciona a mensagem atual do usuário
            messages.append({
                "role": "user",
                "content": message
            })
            
            # Prepara o payload para a API
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": False
            }
            
            # Faz a requisição para a API (formato oficial da Abacus)
            response = requests.post(
                self.base_url,
                headers=self.headers,
                data=json.dumps(payload),
                timeout=int(os.getenv("ABACUS_TIMEOUT", "60"))
            )
            
            # Verifica se a requisição foi bem-sucedida
            response.raise_for_status()
            
            # Retorna a resposta parseada
            response_data = response.json()
            
            return {
                "success": True,
                "message": response_data.get("choices", [{}])[0].get("message", {}).get("content", ""),
                "usage": response_data.get("usage", {}),
                "model": response_data.get("model", self.model)
            }
            
        except requests.exceptions.RequestException as e:
            error_details = ""
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_details = f" - Status: {e.response.status_code}, Resposta: {e.response.text}"
                except:
                    error_details = f" - Status: {e.response.status_code}"
            # Dicas de diagnóstico por status
            hint = ""
            try:
                status = getattr(e.response, "status_code", None)
                if status == 401 or status == 403:
                    hint = "Verifique ABACUS_API_KEY (nome, escopo, expirado) e se foi definido em Secrets (raiz)."
                elif status == 404:
                    hint = "Cheque ABACUS_BASE_URL (padrão: routellm.abacus.ai/v1/chat/completions)."
                elif status == 429:
                    hint = "Limite de taxa atingido. Aguarde e tente novamente."
                elif status and 500 <= status < 600:
                    hint = "Instabilidade no provedor. Tente novamente em alguns minutos."
            except Exception:
                pass
            return {
                "success": False,
                "error": f"Erro na requisição: {str(e)}{error_details}",
                "message": f"Erro ao conectar com a API. {hint} {error_details}".strip()
            }
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Erro ao decodificar resposta: {str(e)}",
                "message": "Desculpe, ocorreu um erro ao processar a resposta. Tente novamente."
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Erro inesperado: {str(e)}",
                "message": "Desculpe, ocorreu um erro inesperado. Tente novamente."
            }
    
    def validate_connection(self) -> bool:
        """
        Valida se a conexão com a API está funcionando.
        
        Returns:
            bool: True se a conexão estiver OK, False caso contrário
        """
        try:
            response = self.send_message("Olá, este é um teste de conexão.")
            return response.get("success", False)
        except:
            return False