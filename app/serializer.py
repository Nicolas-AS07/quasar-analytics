from __future__ import annotations
import pandas as pd


def build_raw_block(df: pd.DataFrame, sample_per_month: int) -> str:
    """
    Retorna string:
    Contexto (dados das planilhas)
    mes=03, ano=2024, linhas=400
    2024-03-01,T-000001,Laptop X1,Eletronicos,Sudeste,1,4990.00,4990.00
    ...
    """
    lines: list[str] = ["Contexto (dados das planilhas)"]
    if df is None or df.empty:
        return "\n".join(lines)
    # agrupado por ano/mes
    for (ano, mes), grp in df.groupby(["ano", "mes"], sort=True):
        grp_sorted = grp.sort_values(["Data", "ID_Transacao"]) if sample_per_month <= 0 else grp.sort_values(["Data", "ID_Transacao"]).head(sample_per_month)
        lines.append(f"mes={mes:02d}, ano={ano}, linhas={len(grp_sorted)}")
        for _, row in grp_sorted.iterrows():
            lines.append(
                f"{row['Data'].isoformat()},{row['ID_Transacao']},{row['Produto']},{row['Categoria']},{row['Regiao']},{int(row['Quantidade'])},{float(row['Preco_Unitario']):.2f},{float(row['Receita_Total']):.2f}"
            )
    return "\n".join(lines)
