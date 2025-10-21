from __future__ import annotations

import io
import re
import os
import json
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from .config import (
    get_google_service_account_credentials,
    get_google_apis_services,
    get_sheets_folder_id,
    get_sheets_ids,
    get_sheet_range,
)


# -------------------- Normalização (inspirado no projeto de referência) --------------------
def _normalize_colname(s: str) -> str:
    s = str(s or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


def _coerce_date_series(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, errors="coerce", dayfirst=True, infer_datetime_format=True)
    return dt.dt.date


def _clean_numeric_series(series: pd.Series) -> pd.Series:
    # Remove separador de milhar e converte vírgula decimal
    s = series.astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


def _rename_and_standardize(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    # cabeçalhos
    cols_norm = {c: _normalize_colname(c) for c in df.columns}
    df = df.rename(columns=cols_norm)
    # mapeamento de sinônimos -> alvo
    synonyms = {
        "data": ["data", "date", "dt", "dia"],
        "id_transacao": ["id_transacao", "id", "transacao", "pedido", "nota", "nf", "nfe", "id_pedido"],
        "produto": ["produto", "item", "produto_nome", "nome_produto"],
        "categoria": ["categoria", "categoria_produto", "grupo", "familia"],
        "regiao": ["regiao", "region", "uf", "estado"],
        "quantidade": ["quantidade", "qtd", "qtde"],
        "preco_unitario": ["preco_unitario", "preco", "preco_un", "preco_unit", "valor_unitario"],
        "receita_total": ["receita_total", "receita", "faturamento", "valor_total", "total", "venda_total"],
    }
    target_cols: Dict[str, Optional[str]] = {k: None for k in synonyms.keys()}
    for target, alts in synonyms.items():
        for alt in alts:
            if alt in df.columns:
                target_cols[target] = alt
                break
    # renomeia para nomes finais
    rename_map = {target_cols[k]: k for k in target_cols if target_cols[k]}
    if rename_map:
        df = df.rename(columns=rename_map)
    # coerções
    if "data" in df.columns:
        df["data"] = _coerce_date_series(df["data"]).astype("object")
    if "quantidade" in df.columns:
        df["quantidade"] = _clean_numeric_series(df["quantidade"])  # pode virar float
    if "preco_unitario" in df.columns:
        df["preco_unitario"] = _clean_numeric_series(df["preco_unitario"])  # float
    if "receita_total" in df.columns:
        df["receita_total"] = _clean_numeric_series(df["receita_total"])  # float
    # se não houver receita_total mas houver quantidade * preco_unitario
    if "receita_total" not in df.columns and {"quantidade", "preco_unitario"}.issubset(df.columns):
        df["receita_total"] = (df["quantidade"].fillna(0) * df["preco_unitario"].fillna(0))
    # normaliza capitalização final
    colmap = {
        "data": "Data",
        "id_transacao": "ID_Transacao",
        "produto": "Produto",
        "categoria": "Categoria",
        "regiao": "Regiao",
        "quantidade": "Quantidade",
        "preco_unitario": "Preco_Unitario",
        "receita_total": "Receita_Total",
    }
    df = df.rename(columns=colmap)
    return df


def _download_drive_file(drive, file_id: str) -> bytes:
    request = drive.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    buf.seek(0)
    return buf.read()


def _list_drive_files(drive, folder_id: str) -> List[Dict[str, Any]]:
    # Google Sheets, CSV, Excel e atalhos
    q = (
        f"'{folder_id}' in parents and trashed=false and ("
        "mimeType='application/vnd.google-apps.spreadsheet' or "
        "mimeType='application/vnd.google-apps.shortcut' or "
        "mimeType='text/csv' or "
        "mimeType='application/vnd.ms-excel' or "
        "mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')"
    )
    fields = "nextPageToken, files(id, name, mimeType, shortcutDetails(targetId, targetMimeType))"
    out: List[Dict[str, Any]] = []
    page_token: Optional[str] = None
    while True:
        resp = drive.files().list(
            q=q,
            fields=fields,
            pageToken=page_token,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
            corpora="allDrives",
            spaces="drive",
        ).execute()
        out.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return out


def _sheet_titles(sheets_service, spreadsheet_id: str) -> List[str]:
    meta = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id, fields="sheets(properties(title))").execute()
    titles = [s["properties"]["title"] for s in meta.get("sheets", [])]
    return titles


def _should_ignore_tab(title: str) -> bool:
    t = title.strip().lower()
    ignore_tokens = ["resumo", "summary", "pivot", "grafic", "dash", "dashboard"]
    return any(tok in t for tok in ignore_tokens)


@st.cache_data(show_spinner=False)
def load_sales_data_drive_folder(
    folder_id: Optional[str],
    extra_ids: Optional[List[str]] = None,
    sheet_range: str = "A:ZZZ",
) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """Carrega dados de vendas a partir de arquivos em uma pasta do Drive.

    - Lê Google Sheets via Sheets API (todas as abas, exceto de resumo/pivô)
    - Lê CSV e Excel via download + pandas
    - Normaliza colunas e tipos; agrega todos os DataFrames
    - Retorna (df_agregado, metadados_por_origem)
    """
    drive, sheets = get_google_apis_services()

    all_sources: List[Dict[str, Any]] = []
    frames: List[pd.DataFrame] = []

    # 1) Planilhas/arquivos da pasta
    ids: List[str] = []
    if folder_id:
        files = _list_drive_files(drive, folder_id)
        for f in files:
            mt = f.get("mimeType")
            if mt == "application/vnd.google-apps.spreadsheet":
                ids.append(f.get("id"))
            elif mt == "application/vnd.google-apps.shortcut":
                sd = (f.get("shortcutDetails") or {})
                if sd.get("targetMimeType") == "application/vnd.google-apps.spreadsheet":
                    ids.append(sd.get("targetId"))
            else:
                # CSV/Excel tratados depois (download)
                all_sources.append({
                    "file_id": f.get("id"),
                    "file_name": f.get("name"),
                    "mimeType": mt,
                    "type": "file",
                })

    # 2) IDs adicionais explícitos (apenas Sheets)
    for x in (extra_ids or []):
        if x and x not in ids:
            ids.append(x)

    # 3) Sheets API: valores por aba
    for sid in ids:
        try:
            for title in _sheet_titles(sheets, sid):
                if _should_ignore_tab(title):
                    continue
                rng = f"{title}!{sheet_range}" if "!" not in sheet_range else sheet_range
                resp = sheets.spreadsheets().values().get(spreadsheetId=sid, range=rng).execute()
                values = resp.get("values", [])
                if len(values) < 2:
                    continue
                header, data = values[0], values[1:]
                df = pd.DataFrame(data, columns=header).fillna("")
                df = _rename_and_standardize(df)
                if df.empty:
                    continue
                df["sheet_id"] = sid
                df["aba"] = title
                frames.append(df)
                all_sources.append({
                    "sheet_id": sid,
                    "worksheet": title,
                    "rows": int(len(df)),
                    "type": "google_sheet",
                })
        except Exception:
            continue

    # 4) Arquivos CSV/Excel: baixar e ler
    for src in [s for s in all_sources if s.get("type") == "file"]:
        fid = src.get("file_id")
        name = src.get("file_name") or ""
        mt = src.get("mimeType") or ""
        try:
            data_bytes = _download_drive_file(drive, fid)
            if mt == "text/csv" or name.lower().endswith(".csv"):
                # Tentar detectar delimitador e decimal
                text = data_bytes.decode("utf-8-sig", errors="ignore")
                # heurística simples: ; mais comum no BR
                sep = ";" if text.count(";") >= text.count(",") else ","
                df = pd.read_csv(io.StringIO(text), sep=sep)
            elif name.lower().endswith(".xlsx") or name.lower().endswith(".xls") or "spreadsheetml.sheet" in mt or "ms-excel" in mt:
                df = pd.read_excel(io.BytesIO(data_bytes))
            else:
                continue
            df = _rename_and_standardize(df)
            if df.empty:
                continue
            df["sheet_id"] = fid
            df["aba"] = name
            frames.append(df)
            src.update({"rows": int(len(df))})
        except Exception:
            continue

    if not frames:
        return pd.DataFrame(columns=[
            "Data","ID_Transacao","Produto","Categoria","Regiao","Quantidade","Preco_Unitario","Receita_Total","sheet_id","aba"
        ]), all_sources

    out = pd.concat(frames, ignore_index=True)
    # Remover duplicatas em um conjunto de chaves comuns, se existirem
    keys = [c for c in ("ID_Transacao", "Produto", "Data") if c in out.columns]
    if keys:
        out = out.drop_duplicates(subset=keys)
    # Ordena por Data (se existir)
    if "Data" in out.columns:
        out = out.sort_values(by=["Data"])  # type: ignore[arg-type]
    out = out.reset_index(drop=True)
    return out, all_sources


# Compat: funções antigas (mantidas para referência externa se houver)
def collect_sheet_ids(folder_id: str | None, extra_ids: List[str]) -> List[str]:
    drive, _ = get_google_apis_services()
    ids: List[str] = []
    if folder_id:
        for f in _list_drive_files(drive, folder_id):
            mt = f.get("mimeType")
            if mt == "application/vnd.google-apps.spreadsheet":
                ids.append(f.get("id"))
            elif mt == "application/vnd.google-apps.shortcut":
                sd = (f.get("shortcutDetails") or {})
                if sd.get("targetMimeType") == "application/vnd.google-apps.spreadsheet":
                    ids.append(sd.get("targetId"))
    for x in (extra_ids or []):
        if x not in ids:
            ids.append(x)
    return ids


def load_raw_rows(sheet_ids: List[str], sheet_range: str, year: Optional[int], months: List[int]) -> pd.DataFrame:
    """Versão simplificada usando Sheets API (deprecatada em favor de load_sales_data_drive_folder)."""
    _, sheets = get_google_apis_services()
    frames: List[pd.DataFrame] = []
    for sid in sheet_ids:
        try:
            for title in _sheet_titles(sheets, sid):
                if _should_ignore_tab(title):
                    continue
                rng = f"{title}!{sheet_range}" if "!" not in sheet_range else sheet_range
                resp = sheets.spreadsheets().values().get(spreadsheetId=sid, range=rng).execute()
                values = resp.get("values", [])
                if len(values) < 2:
                    continue
                header, data = values[0], values[1:]
                df = pd.DataFrame(data, columns=header).fillna("")
                df = _rename_and_standardize(df)
                if df.empty:
                    continue
                # filtros opcionais por ano/mes, se houver coluna Data
                if year or months:
                    if "Data" in df.columns:
                        dt = pd.to_datetime(df["Data"], errors="coerce", dayfirst=True)
                        if year:
                            df = df[dt.dt.year == year]
                        if months:
                            df = df[dt.dt.month.isin(months)]
                if df.empty:
                    continue
                df["sheet_id"], df["aba"] = sid, title
                frames.append(df)
        except Exception:
            continue
    if not frames:
        return pd.DataFrame(columns=["Data","ID_Transacao","Produto","Categoria","Regiao","Quantidade","Preco_Unitario","Receita_Total","sheet_id","aba"])
    out = pd.concat(frames, ignore_index=True)
    return out.reset_index(drop=True)

