"""
Config centralizada (Cloud-first) para o Quasar Analytics.

Prioridade de leitura:
1) st.secrets (inclui GOOGLE_SERVICE_ACCOUNT_CREDENTIALS e seção [google_service_account])
2) Variáveis de ambiente (os.environ)
3) .env (lido via python-dotenv)

Expõe helpers para credenciais e serviços Google (Drive/Sheets),
além de chaves de app (ABACUS_API_KEY, MODEL_NAME, etc.).
"""
from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

# Carrega o .env cedo (útil em dev local)
load_dotenv()

# Streamlit pode não existir em execução local de testes
try:
    import streamlit as st  # type: ignore
    _HAS_STREAMLIT = True
except Exception:
    st = None  # type: ignore
    _HAS_STREAMLIT = False

# --- Google Auth / APIs
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Escopos somente leitura
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]


# -------------------- utils de leitura --------------------
def _secrets_get(path: Tuple[str, ...]) -> Optional[Any]:
    """Busca um valor aninhado em st.secrets usando um caminho (ex.: ('google_service_account',))."""
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
    """Lê string por prioridade: secrets (raiz e seções) -> env -> default."""
    # secrets na raiz
    for name in names:
        val = _secrets_get((name,))
        if val is not None:
            s = str(val).strip()
            if s:
                return s
    # secrets em seções comuns
    for name in names:
        for sect in ("sheets", "google_sheets", "google_service_account", "abacus"):
            val = _secrets_get((sect, name))
            if val is not None:
                s = str(val).strip()
                if s:
                    return s
    # env
    for name in names:
        s = os.getenv(name, "").strip().strip("\"'")
        if s:
            return s
    return default


def get_list_setting(*names: str) -> List[str]:
    """Lê listas; aceita lista real no secrets ou CSV em string nas fontes suportadas."""
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
    for name in names:
        for sect in ("sheets", "google_sheets", "google_service_account"):
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


# -------------------- credenciais (com o trecho que você pediu) --------------------
def get_google_service_account_credentials():
    """
    Resolve credenciais em 3 passos (o seu trecho + fallbacks):
    1) JSON em string: secret 'GOOGLE_SERVICE_ACCOUNT_CREDENTIALS'
    2) Tabela/objeto: seção [google_service_account] em secrets
    3) Caminho de arquivo: env GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH/GOOGLE_APPLICATION_CREDENTIALS
    """
    # 1) JSON em string (GOOGLE_SERVICE_ACCOUNT_CREDENTIALS)
    if _HAS_STREAMLIT:
        try:
            js = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS", "")
            if js:
                info = json.loads(js)
                return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception:
            pass

        # 2) Tabela [google_service_account]
        try:
            tbl = st.secrets.get("google_service_account", None)
            if isinstance(tbl, dict) and tbl.get("client_email"):
                info = dict(tbl)
                return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception:
            pass

    # 3) Caminho de arquivo via env (dev local / fallback)
    path = (
        os.getenv("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH", "").strip().strip("\"'")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip().strip("\"'")
    )
    if path and os.path.isfile(path):
        return service_account.Credentials.from_service_account_file(path, scopes=SCOPES)

    # Falha geral
    raise RuntimeError(
        "Não foi possível localizar as credenciais da Service Account. "
        "Defina 'GOOGLE_SERVICE_ACCOUNT_CREDENTIALS' nos secrets (JSON como string) "
        "ou use o bloco [google_service_account], ou ainda a env var "
        "GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH apontando para um arquivo."
    )


def get_google_apis_services():
    """Cria os serviços Drive e Sheets já autenticados."""
    creds = get_google_service_account_credentials()
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return drive, sheets


# -------------------- chaves/parametrizações do app --------------------
def get_sheets_folder_id() -> Optional[str]:
    return get_str_setting("SHEETS_FOLDER_ID")


def get_sheets_ids() -> List[str]:
    return get_list_setting("SHEETS_IDS")


def get_sheet_range(default: str = "A:Z") -> str:
    return get_str_setting("SHEET_RANGE", default=default) or default


def get_abacus_api_key() -> Optional[str]:
    # aceita [abacus].API_KEY, ABACUS_API_KEY, API_KEY
    val = get_str_setting("ABACUS_API_KEY")
    if not val:
        val = get_str_setting("API_KEY")
        if not val:
            val = get_str_setting("ABACUS", "API_KEY")
    return val


def get_model_name(default: str = "gemini-2.5-pro") -> str:
    return get_str_setting("MODEL_NAME", default=default) or default


def get_service_account_email() -> Optional[str]:
    """Tenta extrair o client_email para exibir na UI (compartilhamento da pasta)."""
    # 1) fonte primária: JSON em string
    try:
        if _HAS_STREAMLIT:
            js = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS", "")
            if js:
                info = json.loads(js)
                if isinstance(info, dict) and info.get("client_email"):
                    return str(info["client_email"])
            tbl = st.secrets.get("google_service_account", None)
            if isinstance(tbl, dict) and tbl.get("client_email"):
                return str(tbl["client_email"])
    except Exception:
        pass
    # 2) arquivo local via env
    try:
        path = (
            os.getenv("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH", "").strip().strip("\"'")
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip().strip("\"'")
        )
        if path and os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get("client_email"):
                return str(data["client_email"])
    except Exception:
        pass
    return None
