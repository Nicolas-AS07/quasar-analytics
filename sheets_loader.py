import os
import json
from typing import List, Dict, Any, Optional, Tuple
import re

import pandas as pd

from googleapiclient.discovery import build

from app.config import (
    get_google_service_account_credentials,
    get_google_apis_services,
    get_sheets_folder_id,
    get_sheets_ids,
    get_sheet_range,
)



class SheetsLoader:
    """Carrega dados de várias Google Sheets usando Service Account.

    Lê as variáveis de ambiente:
    - GOOGLE_APPLICATION_CREDENTIALS: caminho absoluto do JSON da service account
    - SHEETS_IDS: lista separada por vírgulas de IDs de planilhas
    - SHEET_RANGE: intervalo padrão (ex.: A:Z)
    """

    def __init__(self,
                 creds_path: Optional[str] = None,
                 sheet_ids: Optional[List[str]] = None,
                 sheet_range: str = "A:Z") -> None:
        # Mantém compat com assinatura, mas delega leitura a utils
        self.creds_path = (creds_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()).strip("\"'")
        self.sheet_ids = sheet_ids or get_explicit_sheet_ids()
        self.sheet_folder_id: str = get_folder_id() or ""
        self.sheet_range = get_sheet_range(sheet_range)

        self._gc = None
        self._drive = None
        self._cache: Dict[str, pd.DataFrame] = {}
        # Debug/diagnóstico
        self._auth_source: Optional[str] = None
        self._last_errors: List[str] = []

    def _auth(self):
        """Autentica usando utilitário central (env ou secrets)."""
        try:
            creds = get_credentials()
            # Não sabemos a fonte aqui; deixamos um marcador genérico
            self._auth_source = self._auth_source or "utils:get_credentials"
        except Exception as e:
            self._last_errors.append(f"Credentials error: {e}")
            raise

        self._gc = gspread.authorize(creds)
        try:
            self._drive = build('drive', 'v3', credentials=creds, cache_discovery=False)
        except Exception as e:
            self._drive = None
            self._last_errors.append(f"Drive client init failed: {e}")

    def _ensure_client(self):
        if self._gc is None:
            self._auth()

    def _resolve_sheet_ids(self) -> List[str]:
        """Resolve a lista de sheet IDs.
        Se SHEETS_FOLDER_ID estiver definido, lista todas as planilhas (mimeType spreadsheet) na pasta.
        Caso contrário, usa SHEETS_IDS.
        """
        # Preferência: pasta do Drive
        if getattr(self, "sheet_folder_id", ""):
            # Garantir auth
            self._ensure_client()
            if not self._drive:
                return self.sheet_ids
            folder_id = self.sheet_folder_id
            # Listagem NÃO recursiva; inclui planilhas e atalhos para planilhas
            ids: List[str] = []
            try:
                page_token: Optional[str] = None
                while True:
                    resp = self._drive.files().list(
                        q=(
                            f"'{folder_id}' in parents and trashed=false and "
                            "(mimeType='application/vnd.google-apps.spreadsheet' or "
                            "mimeType='application/vnd.google-apps.shortcut')"
                        ),
                        fields=(
                            "nextPageToken, files(id, name, mimeType, shortcutDetails(targetId, targetMimeType))"
                        ),
                        pageToken=page_token,
                        includeItemsFromAllDrives=True,
                        supportsAllDrives=True,
                        corpora="allDrives",
                        spaces="drive",
                    ).execute()
                    for f in resp.get("files", []):
                        mt = f.get("mimeType")
                        if mt == "application/vnd.google-apps.spreadsheet":
                            ids.append(f.get("id"))
                        elif mt == "application/vnd.google-apps.shortcut":
                            sd = f.get("shortcutDetails", {}) or {}
                            if sd.get("targetMimeType") == "application/vnd.google-apps.spreadsheet":
                                ids.append(sd.get("targetId"))
                    page_token = resp.get("nextPageToken")
                    if not page_token:
                        break
            except Exception as e:
                self._last_errors.append(f"Drive listing error: {e}")
            # adiciona extras
            for x in self.sheet_ids:
                if x and x not in ids:
                    ids.append(x)
            # remove None e duplicados preservando ordem
            ids = [i for i in ids if i]
            return list(dict.fromkeys(ids))
        # Fallback: ids explícitos
        return self.sheet_ids


    def load_all(self) -> Tuple[int, int]:
        """Carrega todas as planilhas e abas configuradas. Retorna (n_planilhas, n_linhas_total)."""
        self._ensure_client()
        # Tornar recarga transacional: só substituir o cache se der certo
        prev_cache = self._cache
        new_cache: Dict[str, pd.DataFrame] = {}
        total_rows = 0
        loaded = 0
        try:
            sheet_ids_to_load = self._resolve_sheet_ids()
            for sheet_id in sheet_ids_to_load:
                try:
                    sh = self._gc.open_by_key(sheet_id)
                    worksheets = sh.worksheets()
                    any_loaded = False
                    for ws in worksheets:
                        try:
                            values = ws.get(self.sheet_range)
                            if not values:
                                df = pd.DataFrame()
                            else:
                                header = values[0]
                                rows = values[1:] if len(values) > 1 else []
                                if all(isinstance(h, str) and len(h) <= 60 for h in header):
                                    df = pd.DataFrame(rows, columns=header).fillna("")
                                else:
                                    df = pd.DataFrame(values).fillna("")
                            # anotar título da aba
                            if not df.empty:
                                df["_ws_title"] = ws.title
                            key = f"{sheet_id}::{ws.title}"
                            new_cache[key] = df
                            total_rows += len(df)
                            any_loaded = True
                        except Exception as e:
                            self._last_errors.append(f"Worksheet read error ({sheet_id}/{ws.title}): {e}")
                            continue
                    if any_loaded:
                        loaded += 1
                except Exception as e:
                    self._last_errors.append(f"Spreadsheet open error ({sheet_id}): {e}")
                    # Em caso de erro em uma planilha, apenas pula e continua
                    continue
            # Substitui o cache somente após completar
            self._cache = new_cache
            return loaded, total_rows
        except Exception as e:
            # Restaura cache anterior em caso de falha inesperada
            self._cache = prev_cache
            self._last_errors.append(f"Unexpected load error: {e}")
            raise

    def _has_any_credentials(self) -> bool:
        """Verifica se há credenciais disponíveis via env, secrets ou arquivo."""
        # Se conseguir criar credenciais, está configurado
        try:
            _ = get_credentials()
            return True
        except Exception:
            return False

    def is_configured(self) -> bool:
        # Considera configurado se houver credenciais e (SHEETS_FOLDER_ID ou SHEETS_IDS)
        return self._has_any_credentials() and (bool(getattr(self, "sheet_folder_id", "")) or bool(self.sheet_ids))

    def status(self) -> Dict[str, Any]:
        resolved_ids = []
        try:
            resolved_ids = self._resolve_sheet_ids()
        except Exception:
            resolved_ids = self.sheet_ids
        return {
            "configured": self.is_configured(),
            "creds_path": self.creds_path,
            "sheets_folder_id": getattr(self, "sheet_folder_id", ""),
            "sheets_count": len(resolved_ids),
            "worksheets_count": len(self._cache),
            "resolved_sheet_ids": resolved_ids,
            "loaded": {k: len(v) for k, v in self._cache.items()},
            "debug": {
                "auth_source": self._auth_source,
                "last_errors": self._last_errors[-8:],
            }
        }

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Busca simples: filtra linhas que contenham o termo em qualquer coluna (case-insensitive)."""
        if not query or not self._cache:
            return []

        q = str(query).strip().lower()
        matches: List[Dict[str, Any]] = []
        for key, df in self._cache.items():
            if df.empty:
                continue
            # Combina todas as colunas de cada linha em uma string para busca simples
            concat_series = df.astype(str).apply(lambda r: " | ".join(r.values.tolist()), axis=1).str.lower()
            idx = concat_series[concat_series.str.contains(q, na=False)].index
            for i in idx[:top_k]:
                row = df.iloc[i].to_dict()
                # key no formato '<sheet_id>::<ws_title>'
                if "::" in key:
                    sheet_id, ws_title = key.split("::", 1)
                else:
                    sheet_id, ws_title = key, df.get("_ws_title", "")
                row["_sheet_id"] = sheet_id
                row["_worksheet"] = ws_title
                matches.append(row)

        # Se houver muitos, corta no total
        return matches[:top_k]

    def build_context_snippet(self, rows: List[Dict[str, Any]]) -> str:
        if not rows:
            return ""
        lines = []
        for r in rows:
            sheet = r.pop("_sheet_id", "")
            ws = r.pop("_worksheet", "")
            kv = ", ".join([f"{k}: {v}" for k, v in r.items() if str(v).strip()])
            label = f"[sheet {sheet} / aba {ws}]" if ws else f"[sheet {sheet}]"
            lines.append(f"{label} {kv}")
        return "\n".join(lines)

    # ------------------ Avançado ------------------
    def _extract_ids(self, text: str) -> List[str]:
        # Padrões comuns: T-202404-0012, A-2023-00001 etc.
        patterns = [r"\b[A-Z]-\d{6}-\d{3,6}\b", r"\b[A-Z]-\d{4}-\d{3,6}\b"]
        found = []
        for pat in patterns:
            found += re.findall(pat, text)
        return list(dict.fromkeys(found))  # únicos, mantendo ordem

    def _extract_month_year(self, text: str) -> Optional[Tuple[str, str]]:
        months = {
            "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03", "abril": "04", "maio": "05",
            "junho": "06", "julho": "07", "agosto": "08", "setembro": "09", "outubro": "10", "novembro": "11", "dezembro": "12"
        }
        t = text.lower()
        year = None
        mnum = None
        mname = None
        for name, num in months.items():
            if name in t:
                mnum = num
                mname = name
                break
        ymatch = re.search(r"\b(20\d{2})\b", t)
        if ymatch:
            year = ymatch.group(1)
        if mnum and year:
            return year, mnum
        return None

    def infer_year_for_month(self, month_num: str) -> Optional[str]:
        """Tenta inferir o ano disponível para um determinado mês com base nos títulos das abas carregadas."""
        # Procura padrões _YYYY_MM_ nas chaves do cache
        pat = re.compile(r"_(20\d{2})_" + re.escape(month_num) + r"_")
        for key in self._cache.keys():
            m = pat.search(key)
            if m:
                return m.group(1)
        # Fallback: se houver apenas um ano nas abas, usa-o
        years = set()
        year_pat = re.compile(r"_(20\d{2})_")
        for key in self._cache.keys():
            m = year_pat.search(key)
            if m:
                years.add(m.group(1))
        if len(years) == 1:
            return next(iter(years))
        # Último recurso: 2024 (compatível com dataset atual)
        return "2024"

    def parse_month_year(self, text: str) -> Optional[Tuple[str, str]]:
        """Extrai (ano, mês) do texto; se o ano não aparecer, tenta inferir a partir das abas."""
        ym = self._extract_month_year(text)
        if ym:
            return ym
        # Tentar extrair apenas o mês e inferir ano
        months = {
            "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03", "abril": "04", "maio": "05",
            "junho": "06", "julho": "07", "agosto": "08", "setembro": "09", "outubro": "10", "novembro": "11", "dezembro": "12"
        }
        t = text.lower()
        for name, num in months.items():
            if name in t:
                year = self.infer_year_for_month(num)
                if year:
                    return year, num
        return None

    def search_advanced(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not query or not self._cache:
            return []
        ids = self._extract_ids(query)
        ym = self._extract_month_year(query)
        # filtrar por worksheets se tiver ano/mes
        filtered_keys = list(self._cache.keys())
        if ym:
            year, month = ym
            token = f"_{year}_{month}_"
            filtered_keys = [k for k in filtered_keys if token in k or token in str(self._cache[k].get("_ws_title", ""))]

        results: List[Dict[str, Any]] = []
        # 1) Se houver IDs, tentar match exato em colunas de ID
        if ids:
            for key in filtered_keys:
                df = self._cache[key]
                if df.empty:
                    continue
                for idv in ids:
                    # tentar por colunas que parecem ID
                    id_cols = [c for c in df.columns if "id" in str(c).lower()]
                    matched = pd.DataFrame()
                    for col in id_cols:
                        try:
                            matched = pd.concat([matched, df[df[col].astype(str) == idv]])
                        except Exception:
                            continue
                    if matched.empty:
                        # fallback: contains na linha inteira
                        concat_series = df.astype(str).apply(lambda r: " | ".join(r.values.tolist()), axis=1).str.lower()
                        idx = concat_series[concat_series.str.contains(idv.lower(), na=False)].index
                        if len(idx) > 0:
                            matched = df.loc[idx]
                    for _, row in matched.head(top_k).iterrows():
                        rec = row.to_dict()
                        if "::" in key:
                            sheet_id, ws_title = key.split("::", 1)
                        else:
                            sheet_id, ws_title = key, row.get("_ws_title", "")
                        rec["_sheet_id"] = sheet_id
                        rec["_worksheet"] = ws_title
                        results.append(rec)
                        if len(results) >= top_k:
                            return results
        # 2) Sem IDs ou sem resultado, tokenizar e buscar termos fortes (>3 chars)
        tokens = [w.strip(".,:;!?()[]{}\"'`").lower() for w in query.split()]
        tokens = [t for t in tokens if len(t) >= 4]
        for key in filtered_keys:
            df = self._cache[key]
            if df.empty:
                continue
            concat_series = df.astype(str).apply(lambda r: " | ".join(r.values.tolist()), axis=1).str.lower()
            # match se todos os tokens aparecerem (ou pelo menos 2, se houver muitos)
            if tokens:
                mask = pd.Series(True, index=concat_series.index)
                for t in tokens[:5]:
                    mask = mask & concat_series.str.contains(t, na=False)
                idx = concat_series[mask].index
            else:
                idx = []
            for i in idx[:top_k]:
                row = df.iloc[i].to_dict()
                if "::" in key:
                    sheet_id, ws_title = key.split("::", 1)
                else:
                    sheet_id, ws_title = key, row.get("_ws_title", "")
                row["_sheet_id"] = sheet_id
                row["_worksheet"] = ws_title
                results.append(row)
                if len(results) >= top_k:
                    return results
        return results[:top_k]

    # ------------------ Agregações determinísticas ------------------
    @staticmethod
    def _parse_number_br(value: Any) -> float:
        if value is None:
            return 0.0
        s = str(value).strip()
        if not s:
            return 0.0
        # remove separador de milhar e troca vírgula por ponto
        s = s.replace(".", "").replace(",", ".")
        try:
            return float(s)
        except Exception:
            try:
                return float(re.sub(r"[^0-9\.-]", "", s))
            except Exception:
                return 0.0

    def month_token(self, year: str, month_num: str) -> str:
        return f"_{year}_{month_num}_"

    def get_month_dataframe(self, year: str, month_num: str) -> pd.DataFrame:
        """Concatena todas as abas que pertençam ao mês/ano indicado."""
        token = self.month_token(year, month_num)
        frames = []
        for key, df in self._cache.items():
            if token in key or token in str(df.get("_ws_title", "")):
                if not df.empty:
                    frames.append(df.copy())
        if not frames:
            return pd.DataFrame()
        out = pd.concat(frames, ignore_index=True)
        return out

    def top_products(self, month_name_or_num: str, year: str, top_n: int = 3) -> Dict[str, Any]:
        """Retorna top-N produtos no mês/ano por quantidade e por receita total (determinístico)."""
        months = {
            "01": "janeiro", "02": "fevereiro", "03": "março", "04": "abril", "05": "maio", "06": "junho",
            "07": "julho", "08": "agosto", "09": "setembro", "10": "outubro", "11": "novembro", "12": "dezembro"
        }
        inv = {v: k for k, v in months.items()}
        m = month_name_or_num.strip().lower()
        if m in inv:
            month_num = inv[m]
        elif re.fullmatch(r"\d{1,2}", m):
            month_num = m.zfill(2)
        else:
            # tentar achar no texto
            month_num = None
            for name, num in inv.items():
                if name in m:
                    month_num = num
                    break
            if month_num is None:
                return {"found": False, "reason": "Mês inválido"}

        df = self.get_month_dataframe(year, month_num)
        if df.empty or "Produto" not in df.columns:
            return {"found": False, "reason": "Sem dados para o mês/ano informado"}

        # Normalizar colunas numéricas
        q = pd.to_numeric(df.get("Quantidade", 0), errors="coerce").fillna(0).astype(float)
        r = df.get("Receita_Total", 0).apply(self._parse_number_br) if "Receita_Total" in df.columns else pd.Series([0]*len(df))
        tmp = pd.DataFrame({"Produto": df["Produto"], "Quantidade": q, "Receita_Total": r})

        # Top por quantidade
        by_qty = (
            tmp.groupby("Produto", as_index=False)["Quantidade"].sum().sort_values(by="Quantidade", ascending=False).head(top_n)
        )
        # Top por receita
        by_rev = (
            tmp.groupby("Produto", as_index=False)["Receita_Total"].sum().sort_values(by="Receita_Total", ascending=False).head(top_n)
        )

        return {
            "found": True,
            "year": year,
            "month": months.get(month_num, month_num),
            "top_n": top_n,
            "by_quantity": by_qty.to_dict(orient="records"),
            "by_revenue": by_rev.to_dict(orient="records"),
        }

    # ------------------ Agregação para todos os meses ------------------
    def _detect_month_tokens(self) -> List[Tuple[str, str]]:
        """Retorna lista única de (year, month_num) detectados nos títulos das abas/keys."""
        pat = re.compile(r"_(20\d{2})_(\d{2})_")
        found: List[Tuple[str, str]] = []
        for key, df in self._cache.items():
            # Busca no key (sheet_id::ws_title)
            m = pat.search(key)
            if m:
                found.append((m.group(1), m.group(2)))
                continue
            # Fallback: busca no _ws_title
            title = str(df.get("_ws_title", ""))
            m2 = pat.search(title)
            if m2:
                found.append((m2.group(1), m2.group(2)))
        # únicos e ordenados por ano, mês
        unique = list(dict.fromkeys(found))
        unique.sort()
        return unique

    def top_products_by_month_all(self, top_n: int = 3) -> Dict[str, Any]:
        """Calcula top produtos por quantidade para todos os meses detectados no cache."""
        months_names = {
            "01": "janeiro", "02": "fevereiro", "03": "março", "04": "abril", "05": "maio", "06": "junho",
            "07": "julho", "08": "agosto", "09": "setembro", "10": "outubro", "11": "novembro", "12": "dezembro"
        }
        tokens = self._detect_month_tokens()
        results: List[Dict[str, Any]] = []
        for year, month_num in tokens:
            df = self.get_month_dataframe(year, month_num)
            if df.empty or "Produto" not in df.columns:
                continue
            q = pd.to_numeric(df.get("Quantidade", 0), errors="coerce").fillna(0).astype(float)
            tmp = pd.DataFrame({"Produto": df["Produto"], "Quantidade": q})
            by_qty = (
                tmp.groupby("Produto", as_index=False)["Quantidade"].sum().sort_values(by="Quantidade", ascending=False).head(top_n)
            )
            results.append({
                "year": year,
                "month": months_names.get(month_num, month_num),
                "top_n": top_n,
                "by_quantity": by_qty.to_dict(orient="records"),
            })
        return {"found": bool(results), "months": results, "top_n": top_n}

    def _top_products_by_month_via_date(self, top_n: int = 3) -> Dict[str, Any]:
        """Fallback: se não houver tokens de mês/ano nas abas, tenta agrupar por coluna 'Data'."""
        months_names = {
            1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril", 5: "maio", 6: "junho",
            7: "julho", 8: "agosto", 9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
        }
        # concatena tudo
        frames = [df for df in self._cache.values() if not df.empty and "Produto" in df.columns]
        if not frames:
            return {"found": False}
        all_df = pd.concat(frames, ignore_index=True)
        if "Data" not in all_df.columns:
            return {"found": False}
        # parse datas
        dt = pd.to_datetime(all_df["Data"], errors="coerce", dayfirst=True, infer_datetime_format=True)
        qty = pd.to_numeric(all_df.get("Quantidade", 0), errors="coerce").fillna(0).astype(float)
        safe = pd.DataFrame({"Produto": all_df.get("Produto"), "Quantidade": qty, "ano": dt.dt.year, "mes": dt.dt.month})
        safe = safe.dropna(subset=["ano", "mes"])
        if safe.empty:
            return {"found": False}
        results: List[Dict[str, Any]] = []
        for (year, month), grp in safe.groupby(["ano", "mes"]):
            by_qty = grp.groupby("Produto", as_index=False)["Quantidade"].sum().sort_values(by="Quantidade", ascending=False).head(top_n)
            results.append({
                "year": int(year),
                "month": months_names.get(int(month), str(month)).lower(),
                "top_n": top_n,
                "by_quantity": by_qty.to_dict(orient="records"),
            })
        results.sort(key=lambda x: (x["year"], list(months_names.values()).index(x["month"]) if x["month"] in months_names.values() else 0))
        return {"found": bool(results), "months": results, "top_n": top_n}

    def schema_preview(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for key, df in self._cache.items():
            sheet_id, ws_title = (key.split("::", 1) + [""])[:2] if "::" in key else (key, "")
            out.append({
                "key": key,
                "sheet_id": sheet_id,
                "worksheet": ws_title,
                "rows": int(len(df)),
                "columns": list(df.columns),
            })
        return out

    def base_summary(self, top_n: int = 3) -> Dict[str, Any]:
        """Resumo compacto: tot linhas, quant abas, esquema e top produtos por mês (tokens ou via Data)."""
        status = self.status()
        loaded_map = status.get("loaded", {}) or {}
        total_rows = sum(int(v) for v in loaded_map.values()) if loaded_map else 0
        schema = self.schema_preview()
        # Tenta por tokens; se vazio, tenta por Data
        res = self.top_products_by_month_all(top_n=top_n)
        if not res.get("found"):
            res = self._top_products_by_month_via_date(top_n=top_n)
        return {
            "found": True,
            "totals": {
                "worksheets": len(loaded_map),
                "rows": total_rows,
            },
            "schema": schema,
            "top_by_month": res if res.get("found") else {"found": False}
        }
