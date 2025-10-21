from pydantic import BaseModel, Field
from typing import List, Literal, Dict, Any
from datetime import date


class Txn(BaseModel):
    Data: date
    ID_Transacao: str
    Produto: str
    Categoria: str
    Regiao: str
    Quantidade: int
    Preco_Unitario: float
    Receita_Total: float
    sheet_id: str
    aba: str
    mes: int
    ano: int


class AggCategoriaPeriodo(BaseModel):
    periodo: Literal["mar-mai/2024", "jun-ago/2024"]
    categoria: str
    receita_total: float
    qtd_total: int
    ticket_medio: float


class TopProduto(BaseModel):
    periodo: str
    categoria: str
    produtos: List[Dict[str, Any]]  # {"produto": str, "receita_total": float}


class AuditoriaMes(BaseModel):
    mes: int
    ano: int
    pct_ok: float
    inconsistencias: List[str]
