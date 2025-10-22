"""Carregamento e agregações de planilhas do Google Drive/Sheets.

Este loader:
- Lista arquivos (Google Sheets/CSV/XLSX) em uma pasta do Drive (My Drive ou Shared Drive)
- Carrega planilhas Google Sheets via Sheets API (range configurável)
- Normaliza colunas (produto/quantidade/receita/data) e infere período pelo nome do arquivo
- Expõe agregações úteis (top produtos por mês; todos os meses)
"""

import re
import unicodedata
from datetime import datetime
from collections import defaultdict

import pandas as pd
from typing import List, Dict, Any, Optional, Tuple

from app.config import get_google_apis_services, get_sheets_folder_id, get_sheet_range


class SheetsLoader:
    """Carregador e agregador de planilhas Google."""

    def __init__(self):
        self.sheet_folder_id = get_sheets_folder_id() or ""
        self._cache: Dict[str, pd.DataFrame] = {}
        self._last_errors: List[str] = []
        self._debug: Dict[str, Any] = {}
        self._last_counts: Dict[str, int] = {"sheets": 0, "rows": 0}
        self._sheet_range: str = get_sheet_range("A:Z")
        # Cache normalizado
        self._norm_cache: Dict[str, pd.DataFrame] = {}

    def is_configured(self) -> bool:
        """Verifica se está configurado."""
        try:
            # Testa se consegue obter os serviços Google
            drive_service, sheets_service = get_google_apis_services()
            # Se chegou aqui, as credenciais estão OK
            has_folder = bool(self.sheet_folder_id)
            
            if has_folder:
                return True
            else:
                self._last_errors.append("SHEETS_FOLDER_ID não configurado")
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
            
            # 1) Metadados da pasta — detecta Shared Drive
            folder_meta = drive_service.files().get(
                fileId=self.sheet_folder_id,
                fields="id, name, mimeType, driveId, parents",
                supportsAllDrives=True,
            ).execute()
            self._debug["folder_meta"] = folder_meta

            # 2) Monta consulta robusta
            query = (
                f"'{self.sheet_folder_id}' in parents and ("
                "mimeType='application/vnd.google-apps.spreadsheet' or "
                "mimeType='text/csv' or "
                "mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')"
            )

            params = dict(
                q=query,
                fields="nextPageToken, files(id, name, mimeType)",
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                spaces="drive",
                pageSize=1000,
            )

            drive_id = folder_meta.get("driveId")
            if drive_id:
                # Pasta dentro de um Shared Drive
                params.update(corpora="drive", driveId=drive_id)
            else:
                # Meu Drive do usuário
                params.update(corpora="user")

            # 3) Paginação
            files: List[Dict[str, Any]] = []
            page_token = None
            while True:
                if page_token:
                    params["pageToken"] = page_token
                results = drive_service.files().list(**params).execute()
                files.extend(results.get("files", []))
                page_token = results.get("nextPageToken")
                if not page_token:
                    break

            self._debug["files_found"] = [{"id": f.get("id"), "name": f.get("name"), "mimeType": f.get("mimeType")} for f in files]
            total_rows = 0

            # Limpa caches
            self._cache.clear()
            self._norm_cache.clear()

            for f in files:
                file_id = f.get("id")
                file_name = f.get("name") or ""
                mime = f.get("mimeType") or ""

                # Apenas Google Sheets no primeiro passo
                if mime == "application/vnd.google-apps.spreadsheet":
                    try:
                        self._load_google_sheet(file_id, file_name)
                    except Exception as e:
                        self._last_errors.append(f"Load {file_name}: {e}")
                        continue
                # CSV/XLSX poderiam ser suportados depois com export/download

            # Contagem final
            loaded_map = {k: int(v.shape[0]) for k, v in self._cache.items()}
            total_rows = sum(loaded_map.values())

            self._debug["loaded_map_preview"] = dict(list(loaded_map.items())[:5])
            self._last_counts = {"sheets": len(files), "rows": total_rows}
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
            if "product" not in df.columns:
                continue
            mask = df["product_norm"].str.contains(q, na=False)
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
                    if year:
                        return str(year), num
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

    # ---------------- Internals ----------------
    def _load_google_sheet(self, spreadsheet_id: str, file_name: str) -> None:
        """Carrega todas as abas de um arquivo Google Sheets para o cache e normaliza."""
        _, sheets_service = get_google_apis_services()
        meta = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = meta.get("sheets", [])
        for s in sheets:
            props = s.get("properties", {})
            title = props.get("title") or "Sheet1"
            rng = f"'{title}'!{self._sheet_range}"
            result = sheets_service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=rng).execute()
            values = result.get("values", [])
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
            self._cache[key] = df
            self._norm_cache[key] = self._normalize_dataframe(df, file_name)

    def _normalize_dataframe(self, df: pd.DataFrame, file_name: str) -> pd.DataFrame:
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
            "produto", "produtos", "product", "item", "nome", "descricao", "descrição", "sku"
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

        # Reordena colunas
        cols_order = [c for c in ["product", "quantity", "revenue", "year", "month_num", "month", "transaction_id", "product_norm"] if c in out.columns]
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
        if df.empty or "transaction_id" not in df.columns:
            return {"found": False}
        sub = df[df["transaction_id"].astype(str).str.strip() == str(trans_id).strip()].copy()
        if year:
            sub = sub[sub["year"] == str(year)]
        if month_num:
            sub = sub[sub["month_num"] == str(month_num)]
        if sub.empty:
            return {"found": False}
        total = float(sub["revenue"].sum()) if "revenue" in sub.columns else 0.0
        return {"found": True, "transaction_id": trans_id, "year": str(year) if year else None, "month": self._pt_month_name(month_num) if month_num else None, "revenue": total}