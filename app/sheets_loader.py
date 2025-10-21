from __future__ import annotations
from typing import List
import os
import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def get_credentials() -> Credentials:
    """Cria credenciais da Service Account (Cloud-first).

    Ordem de busca:
    1) Secrets do Streamlit (google_service_account | GOOGLE_SERVICE_ACCOUNT_JSON | gcp_service_account)
    2) JSON em variável de ambiente (GOOGLE_SERVICE_ACCOUNT_JSON)
    3) Caminho de arquivo (GOOGLE_APPLICATION_CREDENTIALS) — fallback local
    """
    # 1) secrets no Streamlit Cloud
    try:
        import streamlit as st
        for key in ("google_service_account", "GOOGLE_SERVICE_ACCOUNT_JSON", "gcp_service_account"):
            try:
                if key in st.secrets:
                    sa_info = st.secrets[key]
                    if isinstance(sa_info, str):
                        sa_info = json.loads(sa_info)
                    if isinstance(sa_info, dict):
                        return Credentials.from_service_account_info(sa_info, scopes=SCOPES)
            except Exception:
                continue
    except Exception:
        # st.secrets pode não estar disponível em alguns contextos
        pass

    # 2) JSON em variável de ambiente
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if sa_json:
        try:
            info = json.loads(sa_json)
            if isinstance(info, dict):
                return Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception:
            pass

    # 3) caminho local
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip().strip("\"'")
    if creds_path and os.path.exists(creds_path):
        return Credentials.from_service_account_file(creds_path, scopes=SCOPES)

    # Sem fonte válida
    raise FileNotFoundError(
        "Credenciais da Service Account não encontradas. Configure um secret do Streamlit (google_service_account) ou a variável GOOGLE_SERVICE_ACCOUNT_JSON."
    )


def _num(v) -> float:
    s = str(v).strip()
    if s == "":
        return 0.0
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


def _to_int(v) -> int:
    try:
        return int(float(str(v).strip().replace(",", ".")))
    except Exception:
        return 0


def collect_sheet_ids(folder_id: str | None, extra_ids: list[str]) -> list[str]:
    """Lista IDs de planilhas Google Sheets dentro da pasta (não recursivo) + extra_ids, sem duplicar."""
    ids: List[str] = []
    if folder_id:
        creds = get_credentials()
        drive = build('drive', 'v3', credentials=creds, cache_discovery=False)
        q = f"mimeType='application/vnd.google-apps.spreadsheet' and trashed=false and '{folder_id}' in parents"
        page_token = None
        while True:
            resp = drive.files().list(q=q, fields="files(id,name),nextPageToken", pageToken=page_token).execute()
            for f in resp.get('files', []):
                ids.append(f['id'])
            page_token = resp.get('nextPageToken')
            if not page_token:
                break
    for x in extra_ids or []:
        if x not in ids:
            ids.append(x)
    return ids


def load_raw_rows(sheet_ids: list[str], sheet_range: str, year: int | None, months: list[int]) -> pd.DataFrame:
    """Baixa valores via Sheets API e retorna DataFrame com colunas padronizadas + mes/ano."""
    creds = get_credentials()
    gc = gspread.authorize(creds)
    frames: List[pd.DataFrame] = []
    required = ["Data", "ID_Transacao", "Produto", "Categoria", "Regiao", "Quantidade", "Preco_Unitario", "Receita_Total"]

    for sid in sheet_ids:
        try:
            sh = gc.open_by_key(sid)
            for ws in sh.worksheets():
                rng = sheet_range
                # Se o range tem 'Aba!' já embutido e não casar com a aba atual, pule
                if "!" in rng and not rng.split("!", 1)[0].strip().lower() == ws.title.strip().lower():
                    continue
                if "!" in rng:
                    # mantém aba do range
                    use_range = rng
                else:
                    use_range = rng
                values = ws.get(use_range) or []
                if len(values) < 2:
                    continue
                headers = [str(h).strip() for h in values[0]]
                rows = values[1:]
                # mapeia colunas requeridas
                import unicodedata
                def norm(s: str) -> str:
                    s = s.strip().lower()
                    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
                    s = s.replace(" ", "_")
                    return s
                norm_headers = [norm(h) for h in headers]
                norm_required = [norm(c) for c in required]
                idx = {col: (norm_headers.index(norm(col)) if norm(col) in norm_headers else -1) for col in required}
                if any(idx[c] < 0 for c in required):
                    # warning: cabeçalho inválido nesta aba
                    continue
                recs = []
                for r in rows:
                    try:
                        data_raw = r[idx["Data"]]
                        # tenta ISO e dd/mm/yyyy
                        from datetime import datetime
                        dt = None
                        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                            try:
                                dt = datetime.strptime(str(data_raw).strip(), fmt).date()
                                break
                            except Exception:
                                continue
                        if not dt:
                            continue
                        if year is not None and dt.year != year:
                            continue
                        if months and dt.month not in months:
                            continue
                        row = {
                            "Data": dt,
                            "ID_Transacao": str(r[idx["ID_Transacao"]]).strip(),
                            "Produto": str(r[idx["Produto"]]).strip(),
                            "Categoria": str(r[idx["Categoria"]]).strip(),
                            "Regiao": str(r[idx["Regiao"]]).strip(),
                            "Quantidade": _to_int(r[idx["Quantidade"]]),
                            "Preco_Unitario": _num(r[idx["Preco_Unitario"]]),
                            "Receita_Total": _num(r[idx["Receita_Total"]]),
                            "sheet_id": sid,
                            "aba": ws.title,
                            "mes": dt.month,
                            "ano": dt.year,
                        }
                        # dropna essenciais
                        if not row["ID_Transacao"] or not row["Produto"] or row["Quantidade"] is None:
                            continue
                        recs.append(row)
                    except Exception:
                        continue
                if recs:
                    df = pd.DataFrame(recs)
                    frames.append(df)
        except Exception:
            # log warning e segue nas demais
            continue

    if not frames:
        return pd.DataFrame(columns=["Data","ID_Transacao","Produto","Categoria","Regiao","Quantidade","Preco_Unitario","Receita_Total","sheet_id","aba","mes","ano"])

    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(by=["Data", "ID_Transacao"]).reset_index(drop=True)
    return out
