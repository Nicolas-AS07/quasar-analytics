from typing import List, Dict, Any, Tuple
from collections import defaultdict
from statistics import mean
from .models import Txn, AggCategoriaPeriodo, TopProduto, AuditoriaMes


Period = Tuple[str, List[int]]
P1: Period = ("mar-mai/2024", [3, 4, 5])
P2: Period = ("jun-ago/2024", [6, 7, 8])


def split_periods(txns: List[Txn]) -> Dict[str, List[Txn]]:
    buckets: Dict[str, List[Txn]] = {P1[0]: [], P2[0]: []}
    months_p1 = set(P1[1])
    months_p2 = set(P2[1])
    for t in txns:
        if t.mes in months_p1:
            buckets[P1[0]].append(t)
        elif t.mes in months_p2:
            buckets[P2[0]].append(t)
    return buckets


def aggregate_by_category(txns: List[Txn]) -> List[AggCategoriaPeriodo]:
    buckets = split_periods(txns)
    out: List[AggCategoriaPeriodo] = []
    for periodo, lst in buckets.items():
        by_cat: Dict[str, Dict[str, float]] = defaultdict(lambda: {"receita": 0.0, "qtd": 0.0})
        for t in lst:
            by_cat[t.Categoria]["receita"] += t.Receita_Total
            by_cat[t.Categoria]["qtd"] += t.Quantidade
        for cat, vals in by_cat.items():
            qtd = int(vals["qtd"]) if vals["qtd"] is not None else 0
            receita = float(vals["receita"]) if vals["receita"] is not None else 0.0
            ticket = receita / max(qtd, 1)
            out.append(AggCategoriaPeriodo(periodo=periodo, categoria=cat, receita_total=receita, qtd_total=qtd, ticket_medio=ticket))
    return out


def top3_by_revenue(txns: List[Txn]) -> List[TopProduto]:
    buckets = split_periods(txns)
    out: List[TopProduto] = []
    for periodo, lst in buckets.items():
        # Por categoria
        cats: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for t in lst:
            cats[t.Categoria][t.Produto] += t.Receita_Total
        for cat, m in cats.items():
            ranked = sorted(m.items(), key=lambda kv: kv[1], reverse=True)[:3]
            produtos = [{"produto": p, "receita_total": float(r)} for p, r in ranked]
            out.append(TopProduto(periodo=periodo, categoria=cat, produtos=produtos))
    return out


def audit_months(txns: List[Txn]) -> Dict[str, Any]:
    # Auditoria por mês: pct_ok e até 5 inconsistências
    months = {3: "marco", 4: "abril", 5: "maio", 6: "junho", 7: "julho", 8: "agosto"}
    out: Dict[str, Any] = {}
    by_month: Dict[int, List[Txn]] = defaultdict(list)
    for t in txns:
        if t.mes in months:
            by_month[t.mes].append(t)
    for m, lst in by_month.items():
        checks = []
        bad_ids: List[str] = []
        for t in lst:
            ok = abs(t.Receita_Total - (t.Quantidade * t.Preco_Unitario)) < 0.01
            checks.append(1.0 if ok else 0.0)
            if not ok and len(bad_ids) < 5:
                bad_ids.append(t.ID_Transacao)
        pct_ok = mean(checks) if checks else 1.0
        out[months[m]] = {"pct_ok": round(pct_ok, 3), "erros": bad_ids}
    return {"auditoria": out}
