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
        "1. GOOGLE_SERVICE_ACCOUNT_CREDENTIALS (JSON completo)\n"
        "2. GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH (caminho do arquivo)\n"
    )


# Variáveis globais (carregadas na importação, como no projeto funcionando)
GOOGLE_DRIVE_FOLDER_ID = _get("GOOGLE_DRIVE_FOLDER_ID", default="")
SHEETS_FOLDER_ID = GOOGLE_DRIVE_FOLDER_ID  # Alias
GEMINI_API_KEY = _get("GEMINI_API_KEY", default="")
ABACUS_API_KEY = _get("ABACUS_API_KEY", default="")
MODEL_NAME = _get("MODEL_NAME", default="gemini-2.5-pro")


# Funções getter (compatibilidade com código existente)
def get_abacus_api_key() -> Optional[str]:
    return ABACUS_API_KEY or None


def get_model_name(default: str = "gemini-2.5-pro") -> str:
    return MODEL_NAME or default


def get_service_account_email() -> Optional[str]:
    """Extrai email da service account."""
    try:
        creds = get_google_service_account_credentials()
        return creds.get("client_email")
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
    if path and os.path.isfile(path):
        try:
            return service_account.Credentials.from_service_account_file(path, scopes=SCOPES)
        except Exception as e:
            raise RuntimeError(f"Erro ao carregar credenciais do arquivo {path}: {e}")

    # Debug: mostra o que está disponível
    debug_info = []
    debug_info.append(f"GOOGLE_SERVICE_ACCOUNT_CREDENTIALS definido: {bool(get_str_setting('GOOGLE_SERVICE_ACCOUNT_CREDENTIALS'))}")
    debug_info.append(f"google_service_account (secrets): {bool(_secrets_get(('google_service_account',)))}")
    debug_info.append(f"GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH: {get_str_setting('GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH')}")
    
    if _HAS_STREAMLIT:
        try:
            import streamlit as st
            st.error("❌ Nenhuma credencial válida encontrada!")
            st.info("🔍 Debug info:\n" + "\n".join(debug_info))
        except:
            pass
    
    raise RuntimeError(
        "Não foi possível localizar as credenciais da Service Account. "
        "Defina 'GOOGLE_SERVICE_ACCOUNT_CREDENTIALS' nos secrets (JSON como string) "
        "ou use o bloco [google_service_account], ou ainda a env var "
        "GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH apontando para um arquivo.\n\n"
        f"Debug: {'; '.join(debug_info)}"
    )


def get_google_apis_services():
    """Retorna (drive_service, sheets_service)."""
    creds = get_google_service_account_credentials()
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return drive, sheets


# ---------------- App settings ----------------
def get_sheets_folder_id() -> Optional[str]:
    return get_str_setting("SHEETS_FOLDER_ID")


def get_sheets_ids() -> List[str]:
    return get_list_setting("SHEETS_IDS")


def get_sheet_range(default: str = "A:Z") -> str:
    return get_str_setting("SHEET_RANGE", default=default) or default


def get_abacus_api_key() -> Optional[str]:
    val = get_str_setting("ABACUS_API_KEY")
    if not val:
        val = get_str_setting("API_KEY") or get_str_setting("ABACUS", "API_KEY")
    return val


def get_model_name(default: str = "gemini-2.5-pro") -> str:
    return get_str_setting("MODEL_NAME", default=default) or default


def get_service_account_email() -> Optional[str]:
    """Extrai client_email das credenciais (pra instruir o compartilhamento da pasta)."""
    try:
        js = get_str_setting("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS")
        if js:
            info = json.loads(js)
            if isinstance(info, dict):
                return str(info.get("client_email") or "")
        for key in ("google_service_account", "gcp_service_account"):
            obj = _secrets_get((key,))
            if isinstance(obj, dict):
                return str(obj.get("client_email") or "")
            if isinstance(obj, str):
                info = json.loads(obj)
                if isinstance(info, dict):
                    return str(info.get("client_email") or "")
        path = get_str_setting("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH", "GOOGLE_APPLICATION_CREDENTIALS")
        if path and os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                info = json.load(f)
            return str(info.get("client_email") or "")
    except Exception:
        return None
    return None
