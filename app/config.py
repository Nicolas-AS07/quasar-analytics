"""
Configuração simplificada baseada no projeto funcionando MatheusFachel/Bot-Analitico-de-Vendas
Ordem de resolução: st.secrets -> env vars -> .env
"""

import os
import json
from typing import Optional, Dict, Any

# Carrega .env se existir
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Streamlit detection
try:
    import streamlit as st
except Exception:
    st = None


def _get_secret(name: str) -> Optional[str]:
    """Obtém valor do st.secrets de forma segura."""
    if st is None:
        return None
    try:
        value = st.secrets.get(name)
        return str(value) if value is not None else None
    except Exception:
        return None


def _get(name: str, *, required: bool = True, default: Optional[str] = None) -> Optional[str]:
    """Busca configuração: st.secrets -> env vars -> default."""
    # 1) st.secrets
    value = _get_secret(name)
    # 2) env vars
    if not value:
        value = os.getenv(name)
    # 3) default
    if not value and default is not None:
        value = default

    if required and not value:
        raise RuntimeError(
            f"Configuração obrigatória ausente: {name}.\n"
            f"Defina em .streamlit/secrets.toml OU como variável de ambiente.\n\n"
            f"Exemplos:\n"
            f"  - .streamlit/secrets.toml: {name} = \"valor_aqui\"\n"
            f"  - PowerShell: $env:{name} = \"valor_aqui\"\n"
            f"  - .env: {name}=valor_aqui\n"
        )
    return value


def get_google_service_account_credentials() -> Dict[str, Any]:
    """Retorna credenciais Google Service Account como dict."""
    # Método 1: JSON completo (para Streamlit Cloud)
    creds_json = _get("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS", required=False)
    
    if creds_json:
        try:
            return json.loads(creds_json)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"JSON das credenciais inválido: {e}")
    
    # Método 1b: Bloco de secrets TOML como dict (compat com projetos existentes)
    if st is not None:
        for key in ("google_service_account", "gcp_service_account"):
            try:
                obj = st.secrets.get(key)
            except Exception:
                obj = None
            # dict direto
            if isinstance(obj, dict):
                return obj  # já é o json das credenciais
            # string JSON
            if isinstance(obj, str) and obj.strip():
                try:
                    return json.loads(obj)
                except Exception:
                    # ignora e segue para outros métodos
                    pass
    
    # Método 2: Arquivo local (para desenvolvimento)
    creds_path = _get("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH", required=False)
    
    if creds_path:
        if not os.path.isfile(creds_path):
            raise RuntimeError(f"Arquivo de credenciais não encontrado: {creds_path}")
        
        try:
            with open(creds_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            raise RuntimeError(f"Erro ao ler arquivo de credenciais: {e}")
    
    raise RuntimeError(
        "Credenciais do Google Service Account não configuradas.\n\n"
        "Configure usando um dos métodos:\n"
        "1. GOOGLE_SERVICE_ACCOUNT_CREDENTIALS (JSON completo como string)\n"
        "2. Bloco [google_service_account] no secrets.toml (dict com o JSON completo)\n"
        "3. GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH (caminho do arquivo local, em dev)\n"
    )


# Variáveis globais (carregadas na importação; não obrigatórias aqui)
GOOGLE_DRIVE_FOLDER_ID = _get("GOOGLE_DRIVE_FOLDER_ID", required=False, default="")
SHEETS_FOLDER_ID = GOOGLE_DRIVE_FOLDER_ID  # Alias
GEMINI_API_KEY = _get("GEMINI_API_KEY", required=False, default="")
ABACUS_API_KEY = _get("ABACUS_API_KEY", required=False, default="")
MODEL_NAME = _get("MODEL_NAME", required=False, default="gemini-2.5-pro")


# Funções getter (compatibilidade com código existente)
def get_abacus_api_key() -> Optional[str]:
    return ABACUS_API_KEY or None


def get_model_name(default: str = "gemini-2.5-pro") -> str:
    return MODEL_NAME or default


def get_service_account_email() -> Optional[str]:
    """Extrai email da service account."""
    try:
        creds = get_google_service_account_credentials()
        return str(creds.get("client_email") or "")
    except Exception:
        return None


def get_sheets_folder_id() -> Optional[str]:
    return SHEETS_FOLDER_ID or None


def get_google_apis_services():
    """Retorna (drive_service, sheets_service) como no projeto funcionando."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/spreadsheets.readonly'
    ]
    
    creds_dict = get_google_service_account_credentials()
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    
    drive_service = build('drive', 'v3', credentials=creds, cache_discovery=False)
    sheets_service = build('sheets', 'v4', credentials=creds, cache_discovery=False)
    
    return drive_service, sheets_service


# Funções auxiliares para compatibilidade
def get_sheets_ids() -> list:
    """Retorna lista vazia - não usado na versão simplificada."""
    return []


def get_sheet_range(default: str = "A:Z") -> str:
    """Retorna range padrão."""
    return default
