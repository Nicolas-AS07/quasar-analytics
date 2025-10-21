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
        """Carrega todas as planilhas da pasta."""
        if not self.is_configured():
            raise RuntimeError("SheetsLoader não está configurado")
        
        try:
            drive_service, sheets_service = get_google_apis_services()
            
            # Query para buscar planilhas na pasta
            query = (
                f"'{self.sheet_folder_id}' in parents and ("
                "mimeType='application/vnd.google-apps.spreadsheet' or "
                "mimeType='text/csv' or "
                "mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')"
            )
            
            # Lista arquivos
            results = drive_service.files().list(
                q=query,
                fields="files(id, name, mimeType)",
                includeItemsFromAllDrives=True,
                supportsAllDrives=True
            ).execute()
            
            files = results.get('files', [])
            total_rows = 0
            
            # Para esta versão simplificada, apenas conta os arquivos
            # A implementação completa carregaria os dados reais aqui
            
            return len(files), total_rows
            
        except Exception as e:
            self._last_errors.append(f"Load error: {e}")
            raise

    def status(self) -> Dict[str, Any]:
        """Retorna status do loader."""
        return {
            "configured": self.is_configured(),
            "sheets_folder_id": self.sheet_folder_id,
            "sheets_count": 0,  # Implementar quando necessário
            "worksheets_count": len(self._cache),
            "loaded": {},
            "debug": {
                "last_errors": self._last_errors[-3:],
            },
        }