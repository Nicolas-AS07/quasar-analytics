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
    """Cliente para comunicação com a API do Google Gemini (Google AI Studio)."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-exp"):
        """
        Inicializa o cliente da API do Google Gemini.
        
        Args:
            api_key (str): Chave da API do Google AI Studio
            model (str): Modelo a ser usado (padrão: gemini-2.0-flash-exp)
        """
        self.api_key = api_key
        self.model = model
        # URL oficial da API Google Gemini
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        self.headers = {
            "Content-Type": "application/json"
        }
        # Parâmetros opcionais do .env
        try:
            self.temperature = float(os.getenv("TEMPERATURE", "0.3"))
        except ValueError:
            self.temperature = 0.3
        try:
            self.max_tokens = int(os.getenv("MAX_TOKENS", "4096"))
        except ValueError:
            self.max_tokens = 4096
        # Caminho opcional para um prompt de sistema externo
        self.system_prompt_path = os.getenv("SYSTEM_PROMPT_PATH", "")
    
    def send_message(self, message: str, conversation_history: Optional[list] = None) -> Dict[str, Any]:
        """
        Envia uma mensagem para a API Google Gemini e retorna a resposta.
        
        Args:
            message (str): Mensagem do usuário
            conversation_history (list, optional): Histórico da conversa
            
        Returns:
            Dict[str, Any]: Resposta da API ou erro
        """
        try:
            # ===== Prompt do Sistema =====
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
                    pass
            
            # 3. Fallback para prompt básico
            if not system_text:
                system_text = (
                    "Você responde em português e usa a seção 'Contexto' quando disponível.\n"
                    "Siga este protocolo: 1) entenda a tarefa; 2) localize dados relevantes no Contexto; "
                    "3) calcule/extraia números; 4) resposta clara e objetiva com tabela/lista quando necessário.\n"
                    "Apenas apresente a resposta final; não mostre raciocínio intermediário."
                )
            
            # ===== Monta o conteúdo completo =====
            # Gemini API não tem "system role" separado, então incluímos no contexto
            full_message = f"{system_text}\n\n{message}"
            
            # Constrói array de contents no formato Gemini
            contents = []
            
            # Adiciona histórico se fornecido (formato Gemini: {role, parts})
            if conversation_history:
                for msg in conversation_history:
                    role = msg.get("role", "user")
                    # Gemini usa "user" e "model" (não "assistant")
                    if role == "assistant":
                        role = "model"
                    contents.append({
                        "role": role,
                        "parts": [{"text": msg.get("content", "")}]
                    })
            
            # Adiciona mensagem atual do usuário
            contents.append({
                "role": "user",
                "parts": [{"text": full_message}]
            })
            
            # Prepara o payload para a API Google Gemini
            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": self.temperature,
                    "maxOutputTokens": self.max_tokens,
                    "topP": 0.95,
                    "topK": 40
                }
            }
            
            # Faz a requisição para a API Google Gemini
            # API key vai como query parameter
            url_with_key = f"{self.base_url}?key={self.api_key}"
            
            response = requests.post(
                url_with_key,
                headers=self.headers,
                data=json.dumps(payload),
                timeout=600  # 10 MINUTOS - máximo possível para não dar timeout
            )
            
            # Verifica se a requisição foi bem-sucedida
            response.raise_for_status()
            
            # Retorna a resposta parseada (formato Gemini)
            response_data = response.json()
            
            # Extrai o texto da resposta
            # Formato: {candidates: [{content: {parts: [{text: "..."}]}}]}
            try:
                candidate = response_data.get("candidates", [{}])[0]
                content_part = candidate.get("content", {}).get("parts", [{}])[0]
                message_text = content_part.get("text", "")
            except (IndexError, KeyError):
                message_text = "Erro ao extrair resposta do modelo"
            
            return {
                "success": True,
                "message": message_text,
                "usage": response_data.get("usageMetadata", {}),
                "model": self.model
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