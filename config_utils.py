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
            sec = st.secrets  # type: ignore[attr-defined]
            if key in sec:
                return sec[key]
        except Exception:
            return None
    return None


def get_credentials() -> Credentials:
    """Cria o objeto Credentials priorizando ambiente de Streamlit Cloud.

    Ordem de busca:
    1) Secrets do Streamlit (google_service_account | gcp_service_account | GOOGLE_SERVICE_ACCOUNT_JSON | GOOGLE_SERVICE_ACCOUNT_CREDENTIALS)
    2) JSON em variável de ambiente (GOOGLE_SERVICE_ACCOUNT_JSON | GOOGLE_SERVICE_ACCOUNT_CREDENTIALS)
    3) Arquivo local (GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH | GOOGLE_APPLICATION_CREDENTIALS) — fallback para dev local
    """
    # 1) Secrets no Streamlit (dict ou string JSON)
    for key in ("google_service_account", "gcp_service_account", "GOOGLE_SERVICE_ACCOUNT_JSON", "GOOGLE_SERVICE_ACCOUNT_CREDENTIALS"):
        raw = _get_secret(key)
        if raw is None:
            continue
        try:
            info = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(info, dict):
                return Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception:
            continue

    # 2) JSON em variável de ambiente
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip() or os.getenv("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS", "").strip()
    if sa_json:
        try:
            info = json.loads(sa_json)
            if isinstance(info, dict):
                return Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception:
            pass

    # 3) Arquivo local (fallback para desenvolvimento)
    cred_path = (
        os.getenv("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH", "").strip().strip("\"'")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip().strip("\"'")
    )
    if cred_path and os.path.exists(cred_path):
        return Credentials.from_service_account_file(cred_path, scopes=SCOPES)

    raise FileNotFoundError(
        "Credenciais não encontradas. Configure no Streamlit um secret GOOGLE_SERVICE_ACCOUNT_CREDENTIALS (JSON como string) ou a seção [google_service_account],\n"
        "ou defina GOOGLE_SERVICE_ACCOUNT_CREDENTIALS (env) com o JSON,\n"
        "ou aponte GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH/GOOGLE_APPLICATION_CREDENTIALS para um arquivo local."
    )


def _getenv_strip(name: str) -> str:
    return str(os.getenv(name, "")).strip().strip("\"'")


def get_sheet_range(default: str = "A:Z") -> str:
    rng = _getenv_strip("SHEET_RANGE")
    if not rng:
        # raiz
        val = _get_secret("SHEET_RANGE")
        if val is not None:
            rng = str(val).strip()
        # tabelas alternativas
        if not rng and _HAS_STREAMLIT and hasattr(st, "secrets"):
            try:
                sec = st.secrets
                if "sheets" in sec and "SHEET_RANGE" in sec["sheets"]:
                    rng = str(sec["sheets"]["SHEET_RANGE"]).strip()
                elif "google_sheets" in sec and "SHEET_RANGE" in sec["google_sheets"]:
                    rng = str(sec["google_sheets"]["SHEET_RANGE"]).strip()
                # fallback: alguns usuários colocam por engano dentro de [google_service_account]
                elif "google_service_account" in sec and "SHEET_RANGE" in sec["google_service_account"]:
                    rng = str(sec["google_service_account"]["SHEET_RANGE"]).strip()
            except Exception:
                pass
    return rng or default


def get_folder_id() -> Optional[str]:
    fid = _getenv_strip("SHEETS_FOLDER_ID")
    if not fid:
        # raiz
        val = _get_secret("SHEETS_FOLDER_ID")
        if val is not None:
            fid = str(val).strip()
        # tabelas alternativas
        if not fid and _HAS_STREAMLIT and hasattr(st, "secrets"):
            try:
                sec = st.secrets
                if "sheets" in sec and "SHEETS_FOLDER_ID" in sec["sheets"]:
                    fid = str(sec["sheets"]["SHEETS_FOLDER_ID"]).strip()
                elif "google_sheets" in sec and "SHEETS_FOLDER_ID" in sec["google_sheets"]:
                    fid = str(sec["google_sheets"]["SHEETS_FOLDER_ID"]).strip()
                elif "google_service_account" in sec and "SHEETS_FOLDER_ID" in sec["google_service_account"]:
                    fid = str(sec["google_service_account"]["SHEETS_FOLDER_ID"]).strip()
            except Exception:
                pass
    return fid or None


def get_explicit_sheet_ids() -> List[str]:
    """Retorna lista de IDs vindos de SHEETS_IDS (env ou secrets)."""
    ids = _getenv_strip("SHEETS_IDS")
    if not ids:
        # raiz
        val = _get_secret("SHEETS_IDS")
        if isinstance(val, list):
            return [str(x).strip() for x in val if str(x).strip()]
        if val is not None:
            ids = str(val).strip()
        # tabelas alternativas
        if not ids and _HAS_STREAMLIT and hasattr(st, "secrets"):
            try:
                sec = st.secrets
                candidate = None
                if "sheets" in sec and "SHEETS_IDS" in sec["sheets"]:
                    candidate = sec["sheets"]["SHEETS_IDS"]
                elif "google_sheets" in sec and "SHEETS_IDS" in sec["google_sheets"]:
                    candidate = sec["google_sheets"]["SHEETS_IDS"]
                elif "google_service_account" in sec and "SHEETS_IDS" in sec["google_service_account"]:
                    candidate = sec["google_service_account"]["SHEETS_IDS"]
                if isinstance(candidate, list):
                    return [str(x).strip() for x in candidate if str(x).strip()]
                if candidate is not None:
                    ids = str(candidate).strip()
            except Exception:
                pass
    if not ids:
        return []
    return [x.strip() for x in ids.split(",") if x.strip()]
