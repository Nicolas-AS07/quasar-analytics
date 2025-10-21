"""
Configuração centralizada (Cloud-first) para o Quasar Analytics.

Ordem de prioridade para ler configurações:
1) st.secrets (quando rodando no Streamlit Cloud)
2) Variáveis de ambiente (os.environ)
3) Arquivo .env (via python-dotenv)

Também expõe utilitários para criar as credenciais da Service Account e
construir os serviços da Google API (Drive e Sheets).
"""
from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

# Carrega .env cedo para que os os.environ reflitam valores locais
load_dotenv()

try:
    import streamlit as st  # type: ignore
    _HAS_STREAMLIT = True
except Exception:
    st = None  # type: ignore
    _HAS_STREAMLIT = False

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Escopos padrão (somente leitura)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _secrets_get(path: Tuple[str, ...]) -> Optional[Any]:
    """Obtém um valor dos secrets seguindo um caminho (ex.: ("abacus", "API_KEY")).
    Retorna None se não existir ou se st.secrets não está disponível.
    """
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


def get_str_setting(*names: str, default: Optional[str] = None) -> Optional[str]:
    """Lê string de configuração por prioridade: st.secrets -> os.environ.
    Observa tanto raiz quanto seções conhecidas nos secrets.
    """
    # 1) st.secrets (raiz)
    for name in names:
        val = _secrets_get((name,))
        if val is not None:
            s = str(val).strip()
            if s:
                return s

    # 1.1) seções alternativas nos secrets
    sections = ("sheets", "google_sheets", "google_service_account", "abacus")
    for name in names:
        for sect in sections:
            val = _secrets_get((sect, name))
            if val is not None:
                s = str(val).strip()
                if s:
                    return s

    # 2) Variáveis de ambiente
    for name in names:
        s = os.getenv(name, "").strip().strip("\"'")
        if s:
            return s

    return default


def get_list_setting(*names: str) -> List[str]:
    """Lê lista de strings; aceita lista no secrets ou CSV como string."""
    # secrets raiz
    for name in names:
        val = _secrets_get((name,))
        if isinstance(val, list):
            return [str(x).strip() for x in val if str(x).strip()]
        if val is not None:
            csv = str(val).strip()
            if csv:
                return [x.strip() for x in csv.split(",") if x.strip()]
    # secrets em seções
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


# -------------------- Credenciais --------------------
def get_google_service_account_credentials() -> Credentials:
    """Cria Credentials da Service Account.

    Prioridade:
    - GOOGLE_SERVICE_ACCOUNT_CREDENTIALS (JSON como string) em secrets/env
    - google_service_account (objeto/JSON) em secrets
    - gcp_service_account (objeto/JSON) em secrets
    - GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH (caminho do arquivo local)
    """
    # 1) JSON string explícito
    raw_json = get_str_setting("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS")
    if raw_json:
        try:
            info = json.loads(raw_json)
            if isinstance(info, dict):
                return Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception:
            # Pode já vir em formato dict no secret
            pass

    # 1.1) Objetos possíveis nos secrets
    for key in ("google_service_account", "gcp_service_account"):
        obj = _secrets_get((key,))
        if isinstance(obj, dict):
            return Credentials.from_service_account_info(obj, scopes=SCOPES)
        if isinstance(obj, str):
            try:
                info = json.loads(obj)
                if isinstance(info, dict):
                    return Credentials.from_service_account_info(info, scopes=SCOPES)
            except Exception:
                pass

    # 2) Caminho de arquivo local
    path = get_str_setting("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH", "GOOGLE_APPLICATION_CREDENTIALS")
    if path and os.path.exists(path):
        return Credentials.from_service_account_file(path, scopes=SCOPES)

    raise FileNotFoundError(
        "Não foi possível localizar as credenciais da Service Account. Configure o secret 'GOOGLE_SERVICE_ACCOUNT_CREDENTIALS' (JSON como string) no Streamlit Cloud,\n"
        "ou defina a variável de ambiente GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH apontando para um arquivo fora do repositório.\n"
        "Dica: compartilhe a pasta do Drive com o e-mail client_email presente nas credenciais."
    )


def get_google_apis_services():
    """Retorna (drive_service, sheets_service) construídos com as credenciais."""
    creds = get_google_service_account_credentials()
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return drive, sheets


# -------------------- Chaves e parâmetros da aplicação --------------------
def get_sheets_folder_id() -> Optional[str]:
    return get_str_setting("SHEETS_FOLDER_ID")


def get_sheets_ids() -> List[str]:
    return get_list_setting("SHEETS_IDS")


def get_sheet_range(default: str = "A:Z") -> str:
    return get_str_setting("SHEET_RANGE", default=default) or default


def get_abacus_api_key() -> Optional[str]:
    # aceita também [abacus].API_KEY ou ABACUS_API_KEY
    val = get_str_setting("ABACUS_API_KEY")
    if not val:
        # nomes alternativos comuns
        val = get_str_setting("API_KEY")
        if not val:
            val = get_str_setting("ABACUS", "API_KEY")  # [abacus].API_KEY se estiver como seção
    return val


def get_model_name(default: str = "gemini-2.5-pro") -> str:
    val = get_str_setting("MODEL_NAME")
    if not val:
        val = default
    return val


def get_service_account_email() -> Optional[str]:
    """Extrai client_email das credenciais (útil para instrução de compartilhamento)."""
    try:
        creds = get_google_service_account_credentials()
        # A info bruta não é exposta diretamente; tentar via arquivo/secret novamente
        raw_json = get_str_setting("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS")
        if raw_json:
            info = json.loads(raw_json)
            return str(info.get("client_email")) if isinstance(info, dict) else None
        for key in ("google_service_account", "gcp_service_account"):
            obj = _secrets_get((key,))
            if isinstance(obj, dict) and obj.get("client_email"):
                return str(obj.get("client_email"))
        path = get_str_setting("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH", "GOOGLE_APPLICATION_CREDENTIALS")
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    info = json.load(f)
                return str(info.get("client_email")) if isinstance(info, dict) else None
            except Exception:
                return None
    except Exception:
        return None
    return None
