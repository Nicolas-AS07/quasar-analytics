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


def get_str_setting(*names: str, default: Optional[str] = None) -> Optional[str]:
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
    Prioridade:
      1) st.secrets["GOOGLE_SERVICE_ACCOUNT_CREDENTIALS"] (JSON string)
      2) st.secrets["google_service_account"] (tabela TOML)  OU  st.secrets["gcp_service_account"]
      3) GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH / GOOGLE_APPLICATION_CREDENTIALS (arquivo)
    Retorna: google.oauth2.service_account.Credentials
    """
    # 1) JSON string explícito
    try:
        js = get_str_setting("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS")
        if js:
            info = json.loads(js)
            return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception:
        pass

    # 2) Bloco [google_service_account] ou [gcp_service_account]
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

    # 3) Caminho de arquivo
    path = get_str_setting("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH", "GOOGLE_APPLICATION_CREDENTIALS")
    if path and os.path.isfile(path):
        return service_account.Credentials.from_service_account_file(path, scopes=SCOPES)

    raise RuntimeError(
        "Não foi possível localizar as credenciais da Service Account. "
        "Defina 'GOOGLE_SERVICE_ACCOUNT_CREDENTIALS' nos secrets (JSON como string) "
        "ou use o bloco [google_service_account], ou ainda a env var "
        "GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH apontando para um arquivo."
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
