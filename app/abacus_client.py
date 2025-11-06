import requests
import json
import os
from typing import Optional, Dict, Any

# ===== NOVO: Import do sistema de prompts otimizado =====
try:
    from app.prompts import get_system_prompt
    HAS_PROMPTS = True
except ImportError:
    HAS_PROMPTS = False


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
        self.base_url = "https://routellm.abacus.ai/v1/chat/completions"  # URL oficial da Abacus
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        # Parâmetros opcionais do .env
        try:
            self.temperature = float(os.getenv("TEMPERATURE", "0.3"))  # ATUALIZADO: de 0.7 para 0.3
        except ValueError:
            self.temperature = 0.3
        try:
            self.max_tokens = int(os.getenv("MAX_TOKENS", "4096"))  # ATUALIZADO: de 1000 para 4096
        except ValueError:
            self.max_tokens = 4096
        # Caminho opcional para um prompt de sistema externo
        self.system_prompt_path = os.getenv("SYSTEM_PROMPT_PATH", "")
    
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
            
            # ===== ATUALIZADO: Usa sistema de prompts otimizado V2 =====
            system_text = None
            
            # 1. Tenta usar Prompt V2 otimizado (se disponível)
            if HAS_PROMPTS:
                use_v2 = os.getenv("USE_SYSTEM_PROMPT_V2", "True").lower() == "true"
                system_text = get_system_prompt(use_v2=use_v2)
            
            # 2. Permite override via arquivo externo (se especificado)
            if self.system_prompt_path and os.path.isfile(self.system_prompt_path):
                try:
                    with open(self.system_prompt_path, "r", encoding="utf-8") as f:
                        system_text = f.read()
                except Exception:
                    pass  # Mantém o prompt padrão/V2
            
            # 3. Fallback para prompt básico (se V2 não disponível)
            if not system_text:
                system_text = (
                    "Você responde em português e usa a seção 'Contexto' quando disponível.\n"
                    "Siga este protocolo ao responder: 1) entenda a tarefa; 2) localize sinais/dados relevantes no Contexto; 3) calcule/extraia números; 4) redija resposta clara e objetiva com tabela/lista quando fizer sentido.\n"
                    "Apenas apresente a resposta final para o usuário; não mostre raciocínio intermediário."
                )
            # ==========================================================
            
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
                timeout=30
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
            
            return {
                "success": False,
                "error": f"Erro na requisição: {str(e)}{error_details}",
                "message": f"Erro ao conectar com a API. Verifique sua chave de API e conexão com a internet.{error_details}"
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