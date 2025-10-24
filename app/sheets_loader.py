"""Carregamento e agregações de planilhas do Google Drive/Sheets.

Este loader:
- Lista arquivos (Google Sheets/CSV/XLSX) em uma pasta do Drive (My Drive ou Shared Drive)
- Carrega planilhas Google Sheets via Sheets API (range configurável)
- Normaliza colunas (produto/quantidade/receita/data) e infere período pelo nome do arquivo
- Expõe agregações úteis (top produtos por mês; todos os meses)
"""

import re
import os
import sqlite3
import time
import unicodedata
from datetime import datetime
from collections import defaultdict

import pandas as pd
from typing import List, Dict, Any, Optional, Tuple

from app.config import (
    get_google_apis_services,
    get_sheets_folder_id,
    get_sheet_range,
    get_sheets_ids,
    get_recursive_listing,
)


class DataStore:
    """Persistência local simples em SQLite para dados normalizados.

    Objetivos:
    - Evitar perda de dados em falhas transitórias ou reinícios do app
    - Permitir restauração de um estado "bom" anterior
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        try:
            base_dir = os.path.join(os.getcwd(), "data_cache")
            os.makedirs(base_dir, exist_ok=True)
            self.db_path = db_path or os.path.join(base_dir, "sheets.sqlite")
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._init_schema()
        except Exception:
            # Se não conseguir persistir, desativa o storage
            self.conn = None

    def available(self) -> bool:
        return self.conn is not None

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS norm_data (
                key TEXT,
                product TEXT,
                quantity REAL,
                revenue REAL,
                year TEXT,
                month_num TEXT,
                month TEXT,
                transaction_id TEXT,
                source_sheet TEXT,
                inserted_at TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                file_id TEXT,
                worksheet TEXT,
                file_modified_time TEXT,
                rows INTEGER,
                updated_at TEXT
            )
            """
        )
        self.conn.commit()

    def save_norm(self, key: str, df: pd.DataFrame, file_id: str, worksheet: str, file_modified_time: Optional[str]) -> None:
        if not self.available():
            return
        cur = self.conn.cursor()
        # Limpa dados anteriores dessa aba
        cur.execute("DELETE FROM norm_data WHERE key=?", (key,))

        # Insere linhas
        now = datetime.utcnow().isoformat()
        cols = [c for c in ["product", "quantity", "revenue", "year", "month_num", "month", "transaction_id", "source_sheet"] if c in df.columns]
        for _, r in df.iterrows():
            vals = [r.get(c) for c in cols]
            cur.execute(
                f"INSERT INTO norm_data (key, {', '.join(cols)}, inserted_at) VALUES ({', '.join(['?']*(len(cols)+2))})",
                [key] + vals + [now]
            )
        # Upsert metadata
        cur.execute(
            "REPLACE INTO metadata(key, file_id, worksheet, file_modified_time, rows, updated_at) VALUES (?,?,?,?,?,?)",
            (key, file_id, worksheet, file_modified_time or "", int(df.shape[0]), now)
        )
        self.conn.commit()

    def load_all_norm(self) -> Dict[str, pd.DataFrame]:
        out: Dict[str, pd.DataFrame] = {}
        if not self.available():
            return out
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT DISTINCT key FROM norm_data")
            keys = [row[0] for row in cur.fetchall()]
            for key in keys:
                cur.execute("SELECT product, quantity, revenue, year, month_num, month, transaction_id, source_sheet FROM norm_data WHERE key=?", (key,))
                rows = cur.fetchall()
                df = pd.DataFrame(rows, columns=["product", "quantity", "revenue", "year", "month_num", "month", "transaction_id", "source_sheet"])
                out[key] = df
        except Exception:
            return {}
        return out


class SheetsLoader:
    """Carregador e agregador de planilhas Google."""

    def __init__(self):
        self.sheet_folder_id = get_sheets_folder_id() or ""
        self._cache: Dict[str, pd.DataFrame] = {}
        self._last_errors: List[str] = []
        self._debug: Dict[str, Any] = {}
        self._last_counts: Dict[str, int] = {"sheets": 0, "rows": 0}
        # Usa um range amplo por padrão; ainda assim substituímos dinamicamente via gridProperties
        self._sheet_range: str = get_sheet_range("A:ZZZ")
        # Cache normalizado
        self._norm_cache: Dict[str, pd.DataFrame] = {}
        # Persistência local (opcional)
        try:
            self._store = DataStore()
            self._debug["store_available"] = self._store.available()
        except Exception as e:
            self._store = None
            self._last_errors.append(f"Datastore init error: {e}")
        # IDs extras explicitados via config
        self._extra_sheet_ids: List[str] = get_sheets_ids() or []
        self._recursive: bool = get_recursive_listing(True)

    def is_configured(self) -> bool:
        """Verifica se está configurado."""
        try:
            # Testa se consegue obter os serviços Google
            drive_service, sheets_service = get_google_apis_services()
            # Se chegou aqui, as credenciais estão OK
            has_folder = bool(self.sheet_folder_id)
            has_ids = bool(self._extra_sheet_ids)
            if has_folder or has_ids:
                return True
            else:
                self._last_errors.append("SHEETS_FOLDER_ID não configurado e nenhum SHEETS_IDS informado")
                return False
        except Exception as e:
            self._last_errors.append(f"Config error: {e}")
            return False

    def load_all(self) -> Tuple[int, int]:
        """Carrega todas as planilhas da pasta (listagem robusta, com Shared Drives) e normaliza dados."""
        if not self.is_configured():
            raise RuntimeError("SheetsLoader não está configurado")
        
        try:
            drive_service, sheets_service = get_google_apis_services()

            files: List[Dict[str, Any]] = []
            folder_meta = None
            if self.sheet_folder_id:
                # 1) Metadados da pasta — detecta Shared Drive
                folder_meta = drive_service.files().get(
                    fileId=self.sheet_folder_id,
                    fields="id, name, mimeType, driveId, parents",
                    supportsAllDrives=True,
                ).execute()
                self._debug["folder_meta"] = folder_meta

            # 2) Monta consulta robusta (diretos na pasta)
            query = (
                f"'{self.sheet_folder_id}' in parents and ("
                "mimeType='application/vnd.google-apps.spreadsheet' or "
                "mimeType='text/csv' or "
                "mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')"
            )

            params = dict(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                spaces="drive",
                pageSize=1000,
            )

            if folder_meta:
                drive_id = folder_meta.get("driveId")
                if drive_id:
                    # Pasta dentro de um Shared Drive
                    params.update(corpora="drive", driveId=drive_id)
                else:
                    # Meu Drive do usuário
                    params.update(corpora="user")

            def list_once(extra_params: dict) -> List[Dict[str, Any]]:
                tmp_files = []
                page_token = None
                p = dict(params)
                p.update(extra_params or {})
                while True:
                    if page_token:
                        p["pageToken"] = page_token
                    results = drive_service.files().list(**p).execute()
                    tmp_files.extend(results.get("files", []))
                    page_token = results.get("nextPageToken")
                    if not page_token:
                        break
                return tmp_files

            # 3) Obtenção da lista de arquivos
            if folder_meta:
                # Lista arquivos diretamente na pasta raiz
                files.extend(list_once({}))

            # Recursivo: lista subpastas e seus arquivos, mantendo o mesmo corpora/driveId
            if folder_meta and self._recursive:
                # lista subpastas
                q_folders = f"'{self.sheet_folder_id}' in parents and mimeType='application/vnd.google-apps.folder'"
                folder_params = dict(params)
                folder_params.update(q=q_folders, fields="nextPageToken, files(id, name, mimeType)")
                subfolders = list_once(folder_params)

                stack = [sf.get("id") for sf in subfolders]
                visited = set()
                while stack:
                    fid = stack.pop()
                    if not fid or fid in visited:
                        continue
                    visited.add(fid)
                    # arquivos dessa subpasta
                    q_child = (
                        f"'{fid}' in parents and ("
                        "mimeType='application/vnd.google-apps.spreadsheet' or "
                        "mimeType='text/csv' or "
                        "mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')"
                    )
                    child_params = dict(params)
                    child_params.update(q=q_child)
                    files.extend(list_once(child_params))
                    # subpastas recursivas
                    q_sub = f"'{fid}' in parents and mimeType='application/vnd.google-apps.folder'"
                    sub_params = dict(params)
                    sub_params.update(q=q_sub, fields="nextPageToken, files(id, name, mimeType)")
                    for sf in list_once(sub_params):
                        stack.append(sf.get("id"))

            # Inclui planilhas explícitas por ID, mesmo fora da pasta
            included_by_id = []
            if self._extra_sheet_ids:
                for sid in self._extra_sheet_ids:
                    try:
                        meta = self._resolve_spreadsheet_meta(drive_service, sid)
                        if meta:
                            if not any(f.get("id") == meta.get("id") for f in files):
                                files.append(meta)
                            included_by_id.append(meta)
                        else:
                            self._last_errors.append(f"ID {sid} não é uma planilha Google válida ou não acessível")
                    except Exception as e:
                        self._last_errors.append(f"Extra sheet id {sid}: {e}")

            self._debug["resolved_sheet_ids"] = self._extra_sheet_ids
            self._debug["included_by_id"] = [{"id": f.get("id"), "name": f.get("name")} for f in included_by_id]
            self._debug["files_found"] = [{"id": f.get("id"), "name": f.get("name"), "mimeType": f.get("mimeType")} for f in files]
            total_rows = 0

            # Construímos caches temporários; em caso de falhas, preservamos dados da execução anterior
            new_cache: Dict[str, pd.DataFrame] = {}
            new_norm_cache: Dict[str, pd.DataFrame] = {}

            # Index de metadados por id
            files_meta = {f.get("id"): f for f in files}

            for f in files:
                file_id = f.get("id")
                file_name = f.get("name") or ""
                mime = f.get("mimeType") or ""

                # Apenas Google Sheets no primeiro passo
                if mime == "application/vnd.google-apps.spreadsheet":
                    try:
                        raw_map, norm_map = self._load_google_sheet(file_id, file_name)
                        new_cache.update(raw_map)
                        new_norm_cache.update(norm_map)
                        # Persiste por aba
                        if getattr(self, "_store", None) and self._store and self._store.available():
                            for k, df_n in norm_map.items():
                                ws_title = k.split("::")[1] if "::" in k else ""
                                meta = files_meta.get(file_id, {})
                                self._store.save_norm(k, df_n, file_id=file_id, worksheet=ws_title, file_modified_time=meta.get("modifiedTime"))
                    except Exception as e:
                        self._last_errors.append(f"Load {file_name}: {e}")
                        continue
                # CSV/XLSX poderiam ser suportados depois com export/download

            # Contagem final
            # Mescla com caches anteriores para evitar quedas abruptas em caso de falhas transitórias
            # Mantém somente chaves cujos arquivos ainda existem na pasta
            valid_file_ids = {f.get("id") for f in files}
            def key_file_id(k: str) -> str:
                return k.split("::")[0] if "::" in k else k

            # Preserva dados antigos apenas quando a aba não foi carregada nesta execução, mas o arquivo ainda existe
            for k, df_old in list(self._cache.items()):
                if k not in new_cache and key_file_id(k) in valid_file_ids:
                    new_cache[k] = df_old
            for k, df_old in list(self._norm_cache.items()):
                if k not in new_norm_cache and key_file_id(k) in valid_file_ids:
                    new_norm_cache[k] = df_old

            # Substitui caches
            self._cache = new_cache
            self._norm_cache = new_norm_cache

            loaded_map = {k: int(v.shape[0]) for k, v in self._cache.items()}
            total_rows = sum(loaded_map.values())

            self._debug["loaded_map_preview"] = dict(list(loaded_map.items())[:5])
            self._last_counts = {"sheets": len(files), "rows": total_rows}
            # Se ainda não carregamos nada mas temos store, restaura do store
            if not self._norm_cache and getattr(self, "_store", None) and self._store and self._store.available():
                restored = self._store.load_all_norm()
                if restored:
                    self._norm_cache = restored
                    # _cache (raw) fica vazio; mas já temos normalizado suficiente para trabalhar
                    self._debug["restored_from_store"] = True
                    loaded_map = {k: int(v.shape[0]) for k, v in self._norm_cache.items()}
                    total_rows = sum(loaded_map.values())
                    self._last_counts = {"sheets": len(loaded_map), "rows": total_rows}

            return self._last_counts["sheets"], self._last_counts["rows"]
            
        except Exception as e:
            self._last_errors.append(f"Load error: {e}")
            raise

    def status(self) -> Dict[str, Any]:
        """Retorna status do loader."""
        loaded = {k: int(v.shape[0]) for k, v in self._cache.items()}
        return {
            "configured": self.is_configured(),
            "sheets_folder_id": self.sheet_folder_id,
            "recursive": self._recursive,
            "sheets_count": self._last_counts.get("sheets", 0),
            "worksheets_count": len(self._cache),
            "loaded": loaded,
            "debug": {
                "last_errors": self._last_errors[-5:],
                **self._debug,
            },
        }

    # ---------------- Camadas de contexto bruto ----------------
    def build_raw_context(
        self,
        layer: str = "samples",
        rows_per_sheet: int = 200,
        fmt: str = "csv",
        max_chars: int = 60000,
    ) -> str:
        """
        Gera um texto contendo dados brutos das abas carregadas em camadas.

        Parâmetros:
        - layer: "schema" (somente colunas e contagem), "samples" (N linhas por aba) ou "full" (todas as linhas, limitado por max_chars)
        - rows_per_sheet: usado em "samples" e como fallback em "full" quando necessário
        - fmt: "csv" ou "jsonl"
        - max_chars: limite total de caracteres do texto gerado

        Retorna:
        - Uma string com blocos demarcados por BEGIN_SHEET/END_SHEET por aba
        """
        if not self._cache:
            return ""

        layer = (layer or "samples").lower().strip()
        fmt = (fmt or "csv").lower().strip()
        if layer not in {"schema", "samples", "full"}:
            layer = "samples"
        if fmt not in {"csv", "jsonl"}:
            fmt = "csv"

        # Ordena por tamanho crescente para tentar incluir mais abas dentro do limite
        items = sorted(self._cache.items(), key=lambda kv: int(kv[1].shape[0]))

        header = f"=== DADOS BRUTOS (camada={layer}, formato={fmt}) ===\n"
        header += "Cada bloco possui demarcações: BEGIN_SHEET key=<planilha::aba> rows=<n> e END_SHEET.\n"
        header += "Use o delimitador para parsear de forma robusta.\n\n"
        out_parts: List[str] = [header]
        total = len(header)

        for key, df in items:
            n_rows = int(df.shape[0])
            cols = list(df.columns)

            if layer == "schema":
                block = (
                    f"BEGIN_SHEET key={key} rows={n_rows} format=schema\n"
                    f"columns: {', '.join(map(str, cols))}\n"
                    f"END_SHEET\n\n"
                )
                if total + len(block) > max_chars:
                    out_parts.append("...TRUNCATED DUE TO SIZE LIMIT...")
                    break
                out_parts.append(block)
                total += len(block)
                continue

            # Escolhe subconjunto de linhas
            if layer == "samples":
                sub = df.head(max(1, int(rows_per_sheet)))
            else:  # full
                sub = df.copy()

            # Renderiza no formato desejado
            if fmt == "csv":
                try:
                    data_str = sub.to_csv(index=False)
                except Exception:
                    # Fallback simples
                    data_str = "\n".join([",".join(map(lambda x: str(x) if x is not None else "", sub.columns))] + [
                        ",".join(map(lambda x: str(x) if x is not None else "", row)) for row in sub.to_numpy()
                    ])
            else:  # jsonl
                try:
                    recs = sub.to_dict(orient="records")
                except Exception:
                    recs = []
                import json as _json
                data_str = "\n".join(_json.dumps(r, ensure_ascii=False) for r in recs)

            block_header = f"BEGIN_SHEET key={key} rows={n_rows} format={fmt}\n"
            block_footer = "\nEND_SHEET\n\n"
            block = block_header + data_str + block_footer

            if total + len(block) > max_chars:
                # Se for camada full, tenta reduzir para um sample antes de truncar
                if layer == "full":
                    sub2 = df.head(max(1, int(rows_per_sheet)))
                    if fmt == "csv":
                        data_str2 = sub2.to_csv(index=False)
                    else:
                        import json as _json
                        data_str2 = "\n".join(_json.dumps(r, ensure_ascii=False) for r in sub2.to_dict(orient="records"))
                    block2 = block_header + data_str2 + block_footer
                    if total + len(block2) <= max_chars:
                        out_parts.append(block2)
                        total += len(block2)
                        continue
                out_parts.append("...TRUNCATED DUE TO SIZE LIMIT...")
                break

            out_parts.append(block)
            total += len(block)

        return "".join(out_parts)

    # ---------------- Métodos auxiliares (stubs) para compatibilidade com main.py ----------------
    def base_summary(self, top_n: int = 3) -> Dict[str, Any]:
        """Resumo de base com preview dos maiores datasets."""
        if not self._norm_cache:
            return {"found": False}
        sizes = [(k, int(df.shape[0])) for k, df in self._norm_cache.items()]
        sizes.sort(key=lambda x: x[1], reverse=True)
        months = self._available_months()
        # Totais por mês (receita)
        df_all = self._concat_norm()
        totals_by_month = []
        if not df_all.empty and "revenue" in df_all.columns:
            grp = (
                df_all.groupby(["year", "month_num"], as_index=False)["revenue"]
                .sum()
                .sort_values(["year", "month_num"])
            )
            for _, r in grp.iterrows():
                totals_by_month.append({
                    "year": str(r["year"]),
                    "month": self._pt_month_name(str(r["month_num"])) if r["month_num"] else "",
                    "revenue": float(r["revenue"] or 0),
                })
        return {"found": True, "top": sizes[:top_n], "months": months, "totals_by_month": totals_by_month[-12:]}

    def search_advanced(self, query: str, top_k: int = 5) -> list:
        """Busca simples por produto contendo o termo."""
        rows = []
        if not query:
            return rows
        q = self._norm(query)
        for key, df in self._norm_cache.items():
            if "product_norm" not in df.columns and "identifier_norm" not in df.columns and "transaction_id" not in df.columns:
                continue
            masks = []
            if "product_norm" in df.columns:
                masks.append(df["product_norm"].str.contains(q, na=False))
            if "identifier_norm" in df.columns:
                masks.append(df["identifier_norm"].str.contains(q, na=False))
            if "transaction_id" in df.columns:
                masks.append(df["transaction_id"].astype(str).str.lower().str.Contains(q, na=False) if hasattr(df["transaction_id"].astype(str).str, 'Contains') else df["transaction_id"].astype(str).str.lower().str.contains(q, na=False))
            if not masks:
                continue
            mask = masks[0]
            for m in masks[1:]:
                mask = mask | m
            if mask.any():
                sub = df[mask].copy()
                for _, r in sub.head(top_k).iterrows():
                    rows.append({
                        "sheet": key,
                        "product": r.get("product"),
                        "quantity": float(r.get("quantity") or 0),
                        "revenue": float(r.get("revenue") or 0),
                        "year": str(r.get("year") or ""),
                        "month": str(r.get("month") or ""),
                    })
        return rows[:top_k]

    def build_context_snippet(self, rows: list) -> str:
        """Gera um snippet de contexto em texto a partir de linhas encontradas."""
        if not rows:
            return ""
        lines = []
        for r in rows:
            lines.append(
                f"Produto: {r.get('product')} | Qtd: {int(r.get('quantity') or 0)} | "
                f"Receita: {float(r.get('revenue') or 0):.2f} | {r.get('month')}/{r.get('year')}"
            )
        return "\n".join(lines)

    def parse_month_year(self, text: str):
        """Extrai (year, month_num) de um texto em PT-BR."""
        if not text:
            return None
        t = self._norm(text)
        months = self._pt_months()
        # tenta capturar "setembro 2024" etc.
        for num, names in months.items():
            for name in names:
                if name in t:
                    m = re.search(r"(19\d{2}|20\d{2})", t)
                    year = m.group(1) if m else None
                    # Retorna mesmo se só houver mês; ano pode ser resolvido depois
                    return (str(year) if year else None), num
        # fallback: só ano
        m = re.search(r"(19\d{2}|20\d{2})", t)
        if m:
            return str(m.group(1)), None
        return None

    def top_products(self, month_name: str, year: str, top_n: int = 3) -> Dict[str, Any]:
        """Top produtos por mês (nome em PT-BR) e ano."""
        if not self._norm_cache:
            return {"found": False}
        months = self._pt_months()
        month_num = None
        nm = self._norm(month_name or "")
        for num, names in months.items():
            if nm in names:
                month_num = num
                break
        if not (year and month_num):
            return {"found": False}

        df_all = self._concat_norm()
        if df_all.empty:
            return {"found": False}
        sub = df_all[(df_all["year"] == str(year)) & (df_all["month_num"] == month_num)].copy()
        if sub.empty:
            return {"found": False}
        grp_q = sub.groupby("product", as_index=False)["quantity"].sum().sort_values("quantity", ascending=False).head(top_n)
        grp_r = sub.groupby("product", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False).head(top_n)
        return {
            "found": True,
            "year": str(year),
            "month": self._pt_month_name(month_num),
            "by_quantity": grp_q.to_dict(orient="records"),
            "by_revenue": grp_r.to_dict(orient="records"),
        }

    def top_products_by_month_all(self, top_n: int = 3) -> Dict[str, Any]:
        """Top produtos para todos os meses disponíveis."""
        if not self._norm_cache:
            return {"found": False}
        df_all = self._concat_norm()
        if df_all.empty:
            return {"found": False}
        out: Dict[str, Any] = {"found": True, "months": []}
        for (yr, mnum), sub in df_all.groupby(["year", "month_num"]):
            grp_q = sub.groupby("product", as_index=False)["quantity"].sum().sort_values("quantity", ascending=False).head(top_n)
            grp_r = sub.groupby("product", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False).head(top_n)
            out["months"].append({
                "year": str(yr),
                "month": self._pt_month_name(mnum),
                "by_quantity": grp_q.to_dict(orient="records"),
                "by_revenue": grp_r.to_dict(orient="records"),
            })
        return out

    def revenue_total(self, year: str, month_num: str) -> Dict[str, Any]:
        """Receita total para um mês/ano específico."""
        df_all = self._concat_norm()
        if df_all.empty:
            return {"found": False}
        sub = df_all[(df_all["year"] == str(year)) & (df_all["month_num"] == str(month_num))]
        if sub.empty or "revenue" not in sub.columns:
            return {"found": False}
        total = float(sub["revenue"].sum())
        return {"found": True, "year": str(year), "month": self._pt_month_name(str(month_num)), "revenue": total, "rows": int(sub.shape[0])}

    def revenue_total_latest(self) -> Dict[str, Any]:
        """Receita total do período mais recente detectado."""
        lm = self.latest_period()
        if not lm:
            return {"found": False}
        year, month_num = lm
        return self.revenue_total(year, month_num)

    def latest_year_for_month(self, month_num: str) -> Optional[str]:
        """Retorna o ano mais recente disponível para um determinado mês ("01".."12")."""
        if not month_num:
            return None
        df = self._concat_norm()
        if df.empty:
            return None
        sub = df[df["month_num"] == str(month_num)].copy()
        if sub.empty:
            return None
        sub["year_int"] = pd.to_numeric(sub["year"], errors="coerce")
        sub = sub.dropna(subset=["year_int"])  # remove anos vazios
        if sub.empty:
            return None
        latest_year = int(sub["year_int"].max())
        return str(latest_year)

    def build_raw_context_filtered(
        self,
        year: Optional[str] = None,
        month_num: Optional[str] = None,
        fmt: str = "jsonl",
        max_chars: int = 60000,
    ) -> str:
        """
        Constrói um contexto bruto contendo TODAS as linhas normalizadas do período indicado.
        Útil para permitir que a LLM compute totais de forma exata.

        - Se apenas month_num for informado, usa o ano mais recente disponível para esse mês.
        - Se nada for informado, usa o período mais recente disponível.
        - Campos incluídos: source_sheet, product, quantity, revenue, year, month_num, month, transaction_id
        - Formato: jsonl (recomendado) ou csv
        """
        df = self._concat_norm()
        if df.empty:
            return ""

        # Resolve período
        y, m = year, month_num
        if m and not y:
            y = self.latest_year_for_month(m)
        if not (y and m):
            lm = self.latest_period()
            if lm:
                y, m = lm
            else:
                return ""

        # Filtra
        sub = df[(df["year"] == str(y)) & (df["month_num"] == str(m))].copy()
        if sub.empty:
            return ""

        # Inclui coluna de origem se disponível
        # Como _concat_norm perde a chave original, tentamos aproveitar index; caso não haja, omite
        # Para garantir, adicionamos um marcador genérico
        sub = sub.copy()
        if "source_sheet" not in sub.columns:
            sub["source_sheet"] = "unknown"

        cols = [c for c in ["source_sheet", "product", "quantity", "revenue", "year", "month_num", "month", "transaction_id"] if c in sub.columns]
        sub = sub[cols]

        header = f"BEGIN_DATA period={y}-{m} format={fmt}\n"
        footer = "\nEND_DATA\n"

        if fmt == "csv":
            data_str = sub.to_csv(index=False)
        else:
            import json as _json
            data_str = "\n".join(_json.dumps(r, ensure_ascii=False) for r in sub.to_dict(orient="records"))

        out = header + data_str + footer
        if len(out) > max_chars:
            # Se exceder, limita por linhas mantendo cabeçalho e rodapé
            if fmt == "csv":
                # Conta linhas: primeira é header CSV
                lines = data_str.splitlines()
                head = lines[:1]
                body = lines[1:]
                trimmed = []
                total = len(header) + len(footer) + sum(len(l) + 1 for l in head)
                for l in body:
                    if total + len(l) + 1 > max_chars:
                        break
                    trimmed.append(l)
                    total += len(l) + 1
                data_str2 = "\n".join(head + trimmed)
            else:
                lines = data_str.splitlines()
                trimmed = []
                total = len(header) + len(footer)
                for l in lines:
                    if total + len(l) + 1 > max_chars:
                        break
                    trimmed.append(l)
                    total += len(l) + 1
                data_str2 = "\n".join(trimmed)
            out = header + data_str2 + footer + "\n...TRUNCATED DUE TO SIZE LIMIT...\n"

        return out

    # ---------------- Internals ----------------
    def _load_google_sheet(self, spreadsheet_id: str, file_name: str) -> Tuple[Dict[str, pd.DataFrame], Dict[str, pd.DataFrame]]:
        """Carrega todas as abas de um arquivo Google Sheets e retorna mapas (raw, norm).

        Implementa range dinâmico via gridProperties e tentativas com backoff para maior robustez.
        """
        raw_map: Dict[str, pd.DataFrame] = {}
        norm_map: Dict[str, pd.DataFrame] = {}

        _, sheets_service = get_google_apis_services()

        # Obter metadados com retries
        meta = None
        for attempt in range(3):
            try:
                meta = sheets_service.spreadsheets().get(
                    spreadsheetId=spreadsheet_id,
                    fields="sheets(properties(title,gridProperties(columnCount,rowCount)))"
                ).execute()
                break
            except Exception as e:
                if attempt == 2:
                    raise
                time.sleep(1.5 * (attempt + 1))

        sheets = meta.get("sheets", []) if meta else []
        for s in sheets:
            props = s.get("properties", {})
            title = props.get("title") or "Sheet1"
            grid = props.get("gridProperties", {}) or {}
            col_count = int(grid.get("columnCount") or 26)
            # Constrói range dinâmico: A:{last_col}
            last_col = self._num_to_col_letters(max(1, col_count))
            rng = f"'{title}'!A:{last_col}"

            # Buscar valores com retries
            values = []
            for attempt in range(3):
                try:
                    result = sheets_service.spreadsheets().values().get(
                        spreadsheetId=spreadsheet_id,
                        range=rng,
                        valueRenderOption="UNFORMATTED_VALUE",
                        dateTimeRenderOption="FORMATTED_STRING",
                    ).execute()
                    values = result.get("values", [])
                    break
                except Exception:
                    if attempt == 2:
                        values = []
                        break
                    time.sleep(1.5 * (attempt + 1))

            if not values:
                continue
            # Detecta header (primeira linha não vazia)
            header = None
            data_rows = []
            for row in values:
                if header is None:
                    if any(str(c).strip() for c in row):
                        header = [str(c).strip() for c in row]
                    continue
                data_rows.append(row)
            if header is None or not data_rows:
                continue
            # Ajusta comprimento
            max_len = max(len(header), max((len(r) for r in data_rows), default=0))
            header = [(header[i] if i < len(header) else f"col_{i}") for i in range(max_len)]
            fixed = [[r[i] if i < len(r) else None for i in range(max_len)] for r in data_rows]
            df = pd.DataFrame(fixed, columns=header)

            key = f"{spreadsheet_id}::{title}"
            raw_map[key] = df
            norm_map[key] = self._normalize_dataframe(df, file_name, source_key=key)

        return raw_map, norm_map

    def _resolve_spreadsheet_meta(self, drive_service, file_id: str) -> Optional[Dict[str, Any]]:
        """Resolve um ID para metadados de uma planilha Google (segue shortcuts)."""
        try:
            meta = drive_service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, modifiedTime, shortcutDetails",
                supportsAllDrives=True,
            ).execute()
            mime = meta.get("mimeType")
            if mime == "application/vnd.google-apps.spreadsheet":
                return meta
            if mime == "application/vnd.google-apps.shortcut":
                details = meta.get("shortcutDetails", {}) or {}
                target_id = details.get("targetId")
                if target_id:
                    meta2 = drive_service.files().get(
                        fileId=target_id,
                        fields="id, name, mimeType, modifiedTime",
                        supportsAllDrives=True,
                    ).execute()
                    if meta2.get("mimeType") == "application/vnd.google-apps.spreadsheet":
                        return meta2
            return None
        except Exception:
            return None

    def load_by_ids(self, ids: List[str]) -> Tuple[int, int]:
        """Carrega (e mescla) dados apenas das planilhas especificadas por ID."""
        if not ids:
            return self._last_counts.get("sheets", 0), self._last_counts.get("rows", 0)
        try:
            drive_service, sheets_service = get_google_apis_services()
            files: List[Dict[str, Any]] = []
            for sid in ids:
                meta = self._resolve_spreadsheet_meta(drive_service, sid)
                if meta:
                    files.append(meta)
                else:
                    self._last_errors.append(f"ID {sid} não resolvido como planilha Google")

            if not files:
                return self._last_counts.get("sheets", 0), self._last_counts.get("rows", 0)

            # Carrega e mescla
            new_cache: Dict[str, pd.DataFrame] = dict(self._cache)
            new_norm_cache: Dict[str, pd.DataFrame] = dict(self._norm_cache)
            files_meta = {f.get("id"): f for f in files}
            for f in files:
                fid = f.get("id")
                name = f.get("name") or ""
                if f.get("mimeType") != "application/vnd.google-apps.spreadsheet":
                    continue
                try:
                    raw_map, norm_map = self._load_google_sheet(fid, name)
                    new_cache.update(raw_map)
                    new_norm_cache.update(norm_map)
                    if getattr(self, "_store", None) and self._store and self._store.available():
                        for k, df_n in norm_map.items():
                            ws_title = k.split("::")[1] if "::" in k else ""
                            meta = files_meta.get(fid, {})
                            self._store.save_norm(k, df_n, file_id=fid, worksheet=ws_title, file_modified_time=meta.get("modifiedTime"))
                except Exception as e:
                    self._last_errors.append(f"Load by id {name}: {e}")

            self._cache = new_cache
            self._norm_cache = new_norm_cache
            loaded_map = {k: int(v.shape[0]) for k, v in self._cache.items()}
            total_rows = sum(loaded_map.values())
            self._last_counts = {"sheets": len(loaded_map), "rows": total_rows}
            return self._last_counts["sheets"], self._last_counts["rows"]
        except Exception as e:
            self._last_errors.append(f"Load by ids error: {e}")
            raise

    @staticmethod
    def _num_to_col_letters(n: int) -> str:
        """Converte 1->A, 26->Z, 27->AA, etc."""
        s = ""
        while n > 0:
            n, rem = divmod(n - 1, 26)
            s = chr(65 + rem) + s
        return s

    def _normalize_dataframe(self, df: pd.DataFrame, file_name: str, source_key: Optional[str] = None) -> pd.DataFrame:
        cols = [str(c).strip() for c in df.columns]
        df = df.copy()
        df.columns = cols
        # Cria versão normalizada dos headers (minúsculo sem acento)
        norm_cols = [self._norm(c) for c in cols]
        col_map = dict(zip(norm_cols, cols))

        # Resolve colunas principais por sinônimos
        def pick(syns: List[str]) -> Optional[str]:
            for s in syns:
                if s in col_map:
                    return col_map[s]
            return None

        product_col = pick([
            "produto", "produtos", "product", "item", "nome", "descricao", "descrição", "sku",
            "codigo", "código", "cod", "referencia", "referência"
        ])
        quantity_col = pick([
            "quantidade", "qtd", "qtde", "volume", "unidades", "qty"
        ])
        revenue_col = pick([
            "receita", "faturamento", "valor_total", "valor", "total", "vendas", "revenue", "amount"
        ])
        date_col = pick([
            "data", "data_venda", "dia", "date"
        ])
        trans_col = pick([
            "id_transacao", "id da transacao", "id_transação", "id da transação", "transaction_id", "transacao", "transacao_id", "pedido", "order_id", "id"
        ])

        out = pd.DataFrame()
        if product_col:
            out["product"] = df[product_col].astype(str).str.strip()
        # Se não existe product e houver coluna de transação, usa-a como product
        if "product" not in out.columns and trans_col and trans_col in df.columns:
            out["product"] = df[trans_col].astype(str).str.strip()
        # Heurística: se ainda não há product, tenta achar coluna com maioria de valores "ID-like" (ex.: T-YYYYMM-NNNN)
        if "product" not in out.columns:
            id_like_cols = []
            pattern = re.compile(r"^[A-Za-z]+-\d{6}-\d{1,6}$")
            for c in df.columns:
                series = df[c].astype(str).str.strip()
                if series.empty:
                    continue
                matches = series.map(lambda x: bool(pattern.match(x)))
                ratio = matches.mean() if len(series) else 0
                if ratio >= 0.5:  # maioria da coluna parece ID
                    id_like_cols.append((c, ratio))
            if id_like_cols:
                id_like_cols.sort(key=lambda x: x[1], reverse=True)
                col = id_like_cols[0][0]
                out["product"] = df[col].astype(str).str.strip()
        if quantity_col and quantity_col in df.columns:
            out["quantity"] = pd.to_numeric(df[quantity_col].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False), errors="coerce").fillna(0)
        else:
            out["quantity"] = 0
        if revenue_col and revenue_col in df.columns:
            out["revenue"] = pd.to_numeric(df[revenue_col].astype(str).str.replace("R$", "", regex=False).str.replace(".", "", regex=False).str.replace(",", ".", regex=False), errors="coerce").fillna(0)
        else:
            out["revenue"] = 0.0

        # Data -> ano/mês; se não houver, tenta inferir pelo nome do arquivo
        if date_col and date_col in df.columns:
            try:
                dts = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
                out["year"] = dts.dt.year.astype("Int64").astype(str)
                out["month_num"] = dts.dt.month.astype("Int64").map(lambda x: f"{int(x):02d}" if pd.notna(x) else None)
            except Exception:
                pass
        if "year" not in out.columns or out["year"].isna().all():
            yr, mn = self._infer_period_from_title(file_name)
            out["year"] = str(yr) if yr else ""
            out["month_num"] = mn if mn else ""

        out["month"] = out["month_num"].map(lambda m: self._pt_month_name(m) if m else "")
        out["product_norm"] = out.get("product", pd.Series(dtype=str)).map(lambda x: self._norm(str(x)))
        if trans_col and trans_col in df.columns:
            out["transaction_id"] = df[trans_col].astype(str).str.strip()

        # Identificador unificado: product -> transaction_id -> None
        if "product" in out.columns:
            out["identifier"] = out["product"].astype(str)
        elif "transaction_id" in out.columns:
            out["identifier"] = out["transaction_id"].astype(str)
        else:
            out["identifier"] = None
        out["identifier_norm"] = out.get("identifier", pd.Series(dtype=str)).map(lambda x: self._norm(str(x)))

        # Coluna de origem
        if source_key:
            out["source_sheet"] = source_key

        # Reordena colunas
        cols_order = [c for c in ["product", "quantity", "revenue", "year", "month_num", "month", "transaction_id", "identifier", "product_norm", "identifier_norm", "source_sheet"] if c in out.columns]
        return out[cols_order]

    def _infer_period_from_title(self, title: str) -> Tuple[Optional[str], Optional[str]]:
        t = self._norm(title or "")
        months = self._pt_months()
        for num, names in months.items():
            for n in names:
                if n in t:
                    m = re.search(r"(19\d{2}|20\d{2})", t)
                    return (m.group(1) if m else None, num)
        m = re.search(r"(19\d{2}|20\d{2})", t)
        return (m.group(1) if m else None, None)

    def _concat_norm(self) -> pd.DataFrame:
        if not self._norm_cache:
            return pd.DataFrame(columns=["product", "quantity", "revenue", "year", "month_num", "month", "transaction_id"])
        return pd.concat(self._norm_cache.values(), ignore_index=True)

    @staticmethod
    def _norm(s: str) -> str:
        if s is None:
            return ""
        s = str(s).lower().strip()
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
        return s

    @staticmethod
    def _pt_months() -> Dict[str, List[str]]:
        return {
            "01": ["janeiro", "jan"],
            "02": ["fevereiro", "fev", "fevereiro"],
            "03": ["marco", "março", "mar"],
            "04": ["abril", "abr"],
            "05": ["maio", "mai"],
            "06": ["junho", "jun"],
            "07": ["julho", "jul"],
            "08": ["agosto", "ago"],
            "09": ["setembro", "set"],
            "10": ["outubro", "out"],
            "11": ["novembro", "nov"],
            "12": ["dezembro", "dez"],
        }

    def _available_months(self) -> List[Tuple[str, str]]:
        df_all = self._concat_norm()
        if df_all.empty:
            return []
        months = df_all[["year", "month_num"]].dropna().drop_duplicates()
        months = months.sort_values(["year", "month_num"]) if not months.empty else months
        out = []
        for _, r in months.iterrows():
            out.append((str(r["year"]), str(r["month_num"])) )
        return out

    def _pt_month_name(self, month_num: Optional[str]) -> str:
        if not month_num:
            return ""
        mapping = {
            "01": "janeiro", "02": "fevereiro", "03": "março", "04": "abril",
            "05": "maio", "06": "junho", "07": "julho", "08": "agosto",
            "09": "setembro", "10": "outubro", "11": "novembro", "12": "dezembro",
        }
        return mapping.get(month_num, month_num)

    # --------- APIs públicas adicionais para o app ---------
    def latest_period(self) -> Optional[Tuple[str, str]]:
        """Retorna (year, month_num) mais recente disponível."""
        df = self._concat_norm()
        if df.empty:
            return None
        sub = df[["year", "month_num"]].dropna()
        if sub.empty:
            return None
        sub["year_int"] = pd.to_numeric(sub["year"], errors="coerce")
        sub["month_int"] = pd.to_numeric(sub["month_num"], errors="coerce")
        sub = sub.dropna()
        if sub.empty:
            return None
        sub = sub.sort_values(["year_int", "month_int"], ascending=[True, True])
        last = sub.iloc[-1]
        return str(int(last["year_int"])), f"{int(last['month_int']):02d}"

    def top_products_default(self, top_n: int = 3) -> Dict[str, Any]:
        """Top produtos para o período mais recente quando o usuário não especifica mês/ano."""
        lm = self.latest_period()
        if not lm:
            return {"found": False}
        year, month_num = lm
        month_name = self._pt_month_name(month_num)
        return self.top_products(month_name, year, top_n=top_n)

    def revenue_by_transaction(self, trans_id: str, year: Optional[str] = None, month_num: Optional[str] = None) -> Dict[str, Any]:
        """Soma a receita por ID de transação. Se (year, month_num) fornecidos, filtra o período."""
        if not trans_id:
            return {"found": False}
        df = self._concat_norm()
        if df.empty:
            return {"found": False}
        trans_id_str = str(trans_id).strip()
        # Tenta casar em transaction_id; senão, tenta em product e identifier
        if "transaction_id" in df.columns:
            sub = df[df["transaction_id"].astype(str).str.strip() == trans_id_str].copy()
        else:
            sub = pd.DataFrame()
        if sub.empty and "product" in df.columns:
            sub = df[df["product"].astype(str).str.strip() == trans_id_str].copy()
        if sub.empty and "identifier" in df.columns:
            sub = df[df["identifier"].astype(str).str.strip() == trans_id_str].copy()
        if year:
            sub = sub[sub["year"] == str(year)]
        if month_num:
            sub = sub[sub["month_num"] == str(month_num)]
        if sub.empty:
            return {"found": False}
        total = float(sub["revenue"].sum()) if "revenue" in sub.columns else 0.0
        return {"found": True, "transaction_id": trans_id, "year": str(year) if year else None, "month": self._pt_month_name(month_num) if month_num else None, "revenue": total}