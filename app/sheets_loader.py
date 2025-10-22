# app/sheets_loader.py

import pandas as pd
from typing import List, Dict, Any, Optional, Tuple

from app.config import get_google_apis_services, get_sheets_folder_id


class SheetsLoader:
    """Carregador simplificado baseado no projeto funcionando."""

    def __init__(self):
        self.sheet_folder_id = get_sheets_folder_id() or ""
        self._cache: Dict[str, pd.DataFrame] = {}
        self._last_errors: List[str] = []
        self._debug: Dict[str, Any] = {}
        self._last_counts: Dict[str, int] = {"sheets": 0, "rows": 0}

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
        """Carrega todas as planilhas da pasta (listagem robusta, com Shared Drives)."""
        if not self.is_configured():
            raise RuntimeError("SheetsLoader não está configurado")
        
        try:
            drive_service, sheets_service = get_google_apis_services()
            
            # 1) Metadados da pasta — detecta Shared Drive
            folder_meta = drive_service.files().get(
                fileId=self.sheet_folder_id,
                fields="id, name, mimeType, driveId, parents"
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
            
            # Para esta versão simplificada, apenas conta os arquivos
            # A implementação completa carregaria os dados reais aqui
            self._last_counts = {"sheets": len(files), "rows": total_rows}
            return self._last_counts["sheets"], self._last_counts["rows"]
            
        except Exception as e:
            self._last_errors.append(f"Load error: {e}")
            raise

    def status(self) -> Dict[str, Any]:
        """Retorna status do loader."""
        return {
            "configured": self.is_configured(),
            "sheets_folder_id": self.sheet_folder_id,
            "sheets_count": self._last_counts.get("sheets", 0),
            "worksheets_count": len(self._cache),
            "loaded": {},
            "debug": {
                "last_errors": self._last_errors[-3:],
                **self._debug,
            },
        }

    # ---------------- Métodos auxiliares (stubs) para compatibilidade com main.py ----------------
    def base_summary(self, top_n: int = 3) -> Dict[str, Any]:
        """Resumo básico (stub)."""
        return {"found": False, "top": []}

    def search_advanced(self, query: str, top_k: int = 5) -> list:
        """Busca avançada (stub)."""
        return []

    def build_context_snippet(self, rows: list) -> str:
        """Constrói um snippet de contexto (stub)."""
        return ""

    def parse_month_year(self, text: str):
        """Extrai (ano, mês) do texto (stub)."""
        return None

    def top_products(self, month_name: str, year: str, top_n: int = 3) -> Dict[str, Any]:
        """Top produtos por mês/ano (stub)."""
        return {"found": False, "by_quantity": [], "by_revenue": []}

    def top_products_by_month_all(self, top_n: int = 3) -> Dict[str, Any]:
        """Top produtos para todos os meses (stub)."""
        return {"found": False}