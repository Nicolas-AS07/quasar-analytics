import os
import json
from typing import List, Optional

try:
    import streamlit as st  # disponível no Cloud; pode não existir localmente em alguns contextos
    _HAS_STREAMLIT = True
except Exception:
    st = None  # type: ignore
    _HAS_STREAMLIT = False

from google.oauth2.service_account import Credentials


# Escopos padrão usados pela app
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _get_secret(key: str):
    if _HAS_STREAMLIT and hasattr(st, "secrets"):
        try:
            return st.secrets.get(key)  # type: ignore[attr-defined]
        except Exception:
            return None
    return None


def get_credentials() -> Credentials:
    """Cria o objeto Credentials priorizando:
    1) Arquivo local (GOOGLE_APPLICATION_CREDENTIALS)
    2) Secrets do Streamlit (google_service_account | GOOGLE_SERVICE_ACCOUNT_JSON | gcp_service_account)
    3) JSON em variável de ambiente (GOOGLE_SERVICE_ACCOUNT_JSON)
    """
    # 1) Arquivo local
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip().strip("\"'")
    if cred_path and os.path.exists(cred_path):
        return Credentials.from_service_account_file(cred_path, scopes=SCOPES)

    # 2) Secrets no Streamlit (dict ou string JSON)
    for key in ("google_service_account", "GOOGLE_SERVICE_ACCOUNT_JSON", "gcp_service_account"):
        raw = _get_secret(key)
        if raw is None:
            continue
        try:
            info = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(info, dict):
                return Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception:
            continue

    # 3) JSON em variável de ambiente
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if sa_json:
        try:
            info = json.loads(sa_json)
            if isinstance(info, dict):
                return Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception:
            pass

    raise FileNotFoundError(
        "Credenciais não encontradas. Defina GOOGLE_APPLICATION_CREDENTIALS (arquivo) ou um secret com a chave da service account."
    )


def _getenv_strip(name: str) -> str:
    return str(os.getenv(name, "")).strip().strip("\"'")


def get_sheet_range(default: str = "A:Z") -> str:
    rng = _getenv_strip("SHEET_RANGE")
    if not rng:
        val = _get_secret("SHEET_RANGE")
        if val is not None:
            rng = str(val).strip()
    return rng or default


def get_folder_id() -> Optional[str]:
    fid = _getenv_strip("SHEETS_FOLDER_ID")
    if not fid:
        val = _get_secret("SHEETS_FOLDER_ID")
        if val is not None:
            fid = str(val).strip()
    return fid or None


def get_explicit_sheet_ids() -> List[str]:
    """Retorna lista de IDs vindos de SHEETS_IDS (env ou secrets)."""
    ids = _getenv_strip("SHEETS_IDS")
    if not ids:
        val = _get_secret("SHEETS_IDS")
        if isinstance(val, list):
            return [str(x).strip() for x in val if str(x).strip()]
        if val is not None:
            ids = str(val).strip()
    if not ids:
        return []
    return [x.strip() for x in ids.split(",") if x.strip()]
