from dataclasses import dataclass
import os
from dotenv import load_dotenv
from typing import Optional, List


load_dotenv()


def _parse_int_list(val: Optional[str], default: List[int]) -> List[int]:
    if not val:
        return default
    out = []
    for part in val.split(","):
        s = part.strip()
        if not s:
            continue
        try:
            out.append(int(s))
        except ValueError:
            continue
    return out or default


def _parse_str_list(val: Optional[str]) -> List[str]:
    if not val:
        return []
    return [s.strip() for s in val.split(",") if s.strip()]


@dataclass
class Settings:
    GOOGLE_APPLICATION_CREDENTIALS: str
    SHEETS_FOLDER_ID: Optional[str]
    SHEETS_IDS: List[str]
    SHEET_RANGE: str
    YEAR: Optional[int]
    MONTHS: List[int]
    SAMPLE_ROWS_PER_MONTH: int


def get_settings() -> Settings:
    creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    # remover aspas se presentes
    if (creds.startswith('"') and creds.endswith('"')) or (creds.startswith("'") and creds.endswith("'")):
        creds = creds[1:-1]
    if not creds:
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS ausente no .env")
    if not os.path.isabs(creds) or not os.path.isfile(creds):
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS deve ser um caminho ABSOLUTO e existente")

    folder_id = os.getenv("SHEETS_FOLDER_ID", "").strip() or None
    extra_ids = _parse_str_list(os.getenv("SHEETS_IDS", ""))
    sheet_range = os.getenv("SHEET_RANGE", "A:H").strip() or "A:H"
    year_raw = os.getenv("YEAR", "").strip()
    year = int(year_raw) if year_raw else None
    months = _parse_int_list(os.getenv("MONTHS", ""), [])
    sample = int(os.getenv("SAMPLE_ROWS_PER_MONTH", "400").strip())

    return Settings(
        GOOGLE_APPLICATION_CREDENTIALS=creds,
        SHEETS_FOLDER_ID=folder_id,
        SHEETS_IDS=extra_ids,
        SHEET_RANGE=sheet_range,
        YEAR=year,
        MONTHS=months,
        SAMPLE_ROWS_PER_MONTH=sample,
    )
