"""
Configuração centralizada (Cloud-first) para o Quasar Analytics.

Prioridade:
1) st.secrets (Streamlit Cloud)
2) Variáveis de ambiente
3) .env (via python-dotenv)

Também expõe utilitários para criar as credenciais da Service Account e
ler parâmetros (SHEETS_FOLDER_ID, SHEETS_IDS, SHEET_RANGE, etc).
"""
from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

try:
    import streamlit as st  # type: ignore
    _HAS_STREAMLIT = True
except Exception:
    st = None  # type: ignore
    _HAS_STREAMLIT = False

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _secrets_get(path: Tuple[str, ...]) -> Optional[Any]:
    if not _HAS_STREAMLIT or not hasattr(st, "secrets"):
        return None
    try:
        cur: Any = st.secrets  # type: ignore[attr-defined]
        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                return None
        return cur
    except Exception:
        return None


def _clean_json_string(json_str: str) -> str:
    """Limpa e corrige problemas comuns em strings JSON."""
    cleaned = json_str.strip()
    
    # Remove aspas externas se existirem
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
        cleaned = cleaned[1:-1]
    
    # Corrige escape sequences comuns do Streamlit Cloud
    fixes = [
        # Quebras de linha
        ('\\\\n', '\\n'),  # \\n -> \n
        ('\\\n', '\\n'),   # \<newline> -> \n
        
        # Aspas
        ('\\"', '"'),      # \" -> "
        ("\\'", "'"),      # \' -> '
        
        # Barras
        ('\\\\', '\\'),    # \\ -> \
    ]
    
    for old, new in fixes:
        cleaned = cleaned.replace(old, new)
    
    return cleaned


def _get_credentials_json() -> Optional[str]:
    """Função específica para obter o JSON das credenciais com diferentes tentativas."""
    # Tenta diferentes formatos comuns no Streamlit Cloud
    attempts = [
        ("st.secrets GOOGLE_SERVICE_ACCOUNT_CREDENTIALS", _secrets_get(("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS",))),
        ("env GOOGLE_SERVICE_ACCOUNT_CREDENTIALS", os.getenv("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS")),
        ("st.secrets google_service_account block", _secrets_get(("google_service_account",))),
    ]
    
    for source, val in attempts:
        if not val:
            continue
            
        # Se é dict (bloco TOML), converte para JSON
        if isinstance(val, dict):
            try:
                return json.dumps(val)
            except:
                continue
                
        # Se é string, limpa e valida
        if isinstance(val, str):
            cleaned = _clean_json_string(val)
            
            # Se não começa com {, não é JSON válido
            if not cleaned.startswith('{'):
                continue
                
            # Debug apenas se Streamlit disponível
            if _HAS_STREAMLIT:
                try:
                    import streamlit as st
                    st.write(f"🔍 Tentando {source}: {len(cleaned)} chars")
                    # Mostra uma amostra segura (sem a private key)
                    sample = cleaned[:200] + "..." if len(cleaned) > 200 else cleaned
                    if '"private_key"' in sample:
                        sample = sample.split('"private_key"')[0] + '"private_key":"[HIDDEN]"...'
                    st.code(sample, language='json')
                except:
                    pass
            
            return cleaned
                
    return None


def get_str_setting(*names: str, default: Optional[str] = None) -> Optional[str]:
    # Para credenciais, usa função específica
    if names and names[0] == "GOOGLE_SERVICE_ACCOUNT_CREDENTIALS":
        return _get_credentials_json()
        
    # 1) raiz
    for name in names:
        val = _secrets_get((name,))
        if val is not None:
            s = str(val).strip()
            if s:
                return s
    # 1.1) seções alternativas
    sections = ("sheets", "google_sheets", "google_service_account", "abacus")
    for name in names:
        for sect in sections:
            val = _secrets_get((sect, name))
            if val is not None:
                s = str(val).strip()
                if s:
                    return s
    # 2) env
    for name in names:
        s = os.getenv(name, "").strip().strip("\"'")
        if s:
            return s
    return default


def get_list_setting(*names: str) -> List[str]:
    # secrets raiz
    for name in names:
        val = _secrets_get((name,))
        if isinstance(val, list):
            return [str(x).strip() for x in val if str(x).strip()]
        if val is not None:
            csv = str(val).strip()
            if csv:
                return [x.strip() for x in csv.split(",") if x.strip()]
    # seções
    sections = ("sheets", "google_sheets", "google_service_account")
    for name in names:
        for sect in sections:
            val = _secrets_get((sect, name))
            if isinstance(val, list):
                return [str(x).strip() for x in val if str(x).strip()]
            if val is not None:
                csv = str(val).strip()
                if csv:
                    return [x.strip() for x in csv.split(",") if x.strip()]
    # env
    for name in names:
        csv = os.getenv(name, "").strip()
        if csv:
            return [x.strip() for x in csv.split(",") if x.strip()]
    return []


# ---------------- Credenciais ----------------
def get_google_service_account_credentials():
    """
    Prioridade (otimizada para Streamlit Cloud):
      1) st.secrets["GOOGLE_SERVICE_ACCOUNT_CREDENTIALS"] (JSON string) - RECOMENDADO PARA CLOUD
      2) st.secrets["google_service_account"] (tabela TOML) - para desenvolvimento local
      3) GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH / GOOGLE_APPLICATION_CREDENTIALS (arquivo)
    Retorna: google.oauth2.service_account.Credentials
    """
    # 1) JSON string explícito (MELHOR para Streamlit Cloud)
    try:
        js = get_str_setting("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS")
        if js:
            # Remove possíveis aspas extras e whitespace
            js = js.strip().strip('"').strip("'")
            
            # Debug para Streamlit Cloud
            if _HAS_STREAMLIT:
                try:
                    import streamlit as st
                    st.write(f"🔍 DEBUG: JSON string tem {len(js)} caracteres")
                    st.write(f"🔍 DEBUG: Começa com: '{js[:50]}...'")
                except:
                    pass
            
            info = json.loads(js)
            if isinstance(info, dict) and info.get("client_email"):
                if _HAS_STREAMLIT:
                    try:
                        import streamlit as st
                        st.success(f"✅ Credenciais carregadas! Email: {info.get('client_email')}")
                    except:
                        pass
                return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
            else:
                error_msg = f"JSON parseado mas não tem client_email. Keys: {list(info.keys()) if isinstance(info, dict) else 'não é dict'}"
                if _HAS_STREAMLIT:
                    try:
                        import streamlit as st
                        st.error(f"❌ {error_msg}")
                    except:
                        print(f"DEBUG: {error_msg}")
                else:
                    print(f"DEBUG: {error_msg}")
                    
    except json.JSONDecodeError as e:
        error_msg = f"Erro ao fazer parse do JSON: {e}"
        
        # Tenta identificar o problema específico
        if "Invalid control character" in str(e):
            error_msg += "\n\n🔧 SOLUÇÃO: O JSON contém caracteres de controle inválidos (provavelmente quebras de linha mal escapadas)."
            error_msg += "\n\nPara corrigir:"
            error_msg += "\n1. Use JSON em linha única (sem quebras de linha)"
            error_msg += "\n2. OU escape as quebras de linha como \\\\n"
            error_msg += "\n3. OU use o bloco [google_service_account] no TOML"
            
        # Mostra o contexto do erro se possível
        if hasattr(e, 'pos') and js:
            start = max(0, e.pos - 50)
            end = min(len(js), e.pos + 50)
            context = js[start:end]
            error_msg += f"\n\nContexto do erro (posição {e.pos}):\n...{context}..."
            
        if _HAS_STREAMLIT:
            try:
                import streamlit as st
                st.error(f"❌ {error_msg}")
                
                # Oferece solução alternativa
                st.info("💡 **Solução alternativa**: Configure usando o bloco [google_service_account] nos secrets:")
                st.code("""[google_service_account]
type = "service_account"
project_id = "seu-projeto-id"
private_key_id = "sua-private-key-id"
private_key = '''-----BEGIN PRIVATE KEY-----
SUA_CHAVE_PRIVADA_AQUI
-----END PRIVATE KEY-----'''
client_email = "seu-service-account@projeto.iam.gserviceaccount.com"
client_id = "seu-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
universe_domain = "googleapis.com\"""", language='toml')
            except:
                print(f"DEBUG: {error_msg}")
        else:
            print(f"DEBUG: {error_msg}")
    except Exception as e:
        error_msg = f"Erro inesperado ao processar GOOGLE_SERVICE_ACCOUNT_CREDENTIALS: {e}"
        
        # Identifica erros específicos comuns
        if "Incorrect padding" in str(e):
            error_msg += "\n\n🔧 CAUSA: A private_key está mal formatada ou corrompida."
            error_msg += "\n\nSOLUÇÕES:"
            error_msg += "\n1. ✅ Use o bloco [google_service_account] que é mais confiável"
            error_msg += "\n2. Baixe novamente o arquivo service_account.json do Google Cloud"
            error_msg += "\n3. Verifique se a private_key não foi cortada/alterada"
        elif "ValueError" in str(e) or "Invalid" in str(e):
            error_msg += "\n\n🔧 CAUSA: Formato inválido na private_key."
            error_msg += "\n\nSOLUÇÃO: ✅ Use o bloco [google_service_account] em vez de JSON string."
            
        if _HAS_STREAMLIT:
            try:
                import streamlit as st
                st.error(f"❌ {error_msg}")
                
                # Sempre oferece a solução TOML como alternativa
                st.success("💡 **SOLUÇÃO RECOMENDADA**: Use o bloco [google_service_account]")
                st.info("Cole isto nos seus secrets do Streamlit Cloud:")
                st.code("""[google_service_account]
type = "service_account"
project_id = "chatbotaula17"
private_key_id = "fddef514a2e4ac16bd01c5639eaa2d07d96b17fd"
private_key = '''-----BEGIN PRIVATE KEY-----
SUA_CHAVE_PRIVADA_COMPLETA_DO_ARQUIVO_JSON
-----END PRIVATE KEY-----'''
client_email = "sheets-reader@chatbotaula17.iam.gserviceaccount.com"
client_id = "117193447779719276268"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/sheets-reader@chatbotaula17.iam.gserviceaccount.com"
universe_domain = "googleapis.com\"""", language='toml')
                st.warning("⚠️ **IMPORTANTE**: Substitua 'SUA_CHAVE_PRIVADA_COMPLETA_DO_ARQUIVO_JSON' pela private_key real do seu arquivo service_account.json")
            except:
                print(f"DEBUG: {error_msg}")
        else:
            print(f"DEBUG: {error_msg}")
        # Não levanta erro aqui, continua tentando outros métodos

    # 2) Bloco [google_service_account] ou [gcp_service_account] (para dev local)
    for key in ("google_service_account", "gcp_service_account"):
        try:
            obj = _secrets_get((key,))
            if isinstance(obj, dict) and obj.get("client_email"):
                info = dict(obj)
                return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
            if isinstance(obj, str):
                info = json.loads(obj)
                if isinstance(info, dict) and info.get("client_email"):
                    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception:
            pass

    # 3) Caminho de arquivo (para desenvolvimento local)
    path = get_str_setting("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH", "GOOGLE_APPLICATION_CREDENTIALS")
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
