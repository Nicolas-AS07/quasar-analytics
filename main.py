"""
Quasar Analytics - Assistente Analítico de Vendas
Chatbot com IA para análise de dados de vendas via Google Sheets
"""

import os
import json
import time
from datetime import datetime

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from app.ui_styles import render_css

# --- Config centralizada (Cloud-first)
from app.config import (
    get_abacus_api_key,
    get_model_name,
    get_service_account_email,
)

# --- Loader (Google APIs nativas; sem gspread)
# Importação do loader será feita de forma lazy dentro da inicialização,
# para capturar e exibir erros de import no UI (evita crash no import).

# --- Cliente do modelo
from app.abacus_client import AbacusClient


# -------------------------------------------------------
# Boot
# -------------------------------------------------------
load_dotenv()

st.set_page_config(
    page_title="Quasar Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_css("dark")


# -------------------------------------------------------
# Helpers
# -------------------------------------------------------
def get_env_config() -> tuple[str, str]:
    """Lê API key e modelo via config central (st.secrets/.env)."""
    api_key = get_abacus_api_key() or ""
    model = get_model_name(default="gemini-2.5-pro")
    return api_key, model


def create_client(api_key: str, model: str = "gemini-2.5-pro") -> AbacusClient | None:
    """Cria o cliente do modelo com tratamento de erro."""
    try:
        client = AbacusClient(api_key=api_key, model=model)
        # opcional: validação de conectividade
        try:
            if hasattr(client, "validate_connection") and not client.validate_connection():
                st.warning("Não foi possível validar a conexão com o modelo.")
        except Exception:
            pass
        return client
    except Exception as e:
        st.error(f"Erro ao criar cliente do modelo: {e}")
        return None


def display_chat_messages() -> None:
    """Renderiza o histórico do chat."""
    for m in st.session_state.messages:
        role = "user" if m.get("role") == "user" else "assistant"
        with st.chat_message(role):
            st.markdown(m.get("content", ""))


def initialize_session() -> None:
    """Inicializa variáveis de sessão de forma simplificada."""
    # estado básico
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("client", None)
    st.session_state.setdefault("sheets", None)

    # API key/modelo
    if "api_key" not in st.session_state or "model" not in st.session_state:
        api_key, model = get_env_config()
        st.session_state.api_key = api_key
        st.session_state.model = model
        if api_key:
            st.session_state.client = create_client(api_key, model)

    # TTL
    if "sheets_ttl_enabled" not in st.session_state:
        st.session_state["sheets_ttl_enabled"] = False
    if "sheets_ttl_seconds" not in st.session_state:
        st.session_state["sheets_ttl_seconds"] = 60

    # Preferências de contexto bruto (forçado para FULL conforme solicitado)
    st.session_state.setdefault("raw_layer", "full")
    st.session_state.setdefault("raw_rows_per_sheet", 500)
    st.session_state.setdefault("raw_format", "jsonl")
    st.session_state.setdefault("raw_max_chars", 200000)

    # Carrega planilhas de forma simplificada
    loader = st.session_state.get("sheets")
    if loader is None:
        try:
            from app.sheets_loader import SheetsLoader  # import lazy com tratamento de erro
            loader = SheetsLoader()
        except Exception as e:
            st.error(f"Erro ao importar/carregar SheetsLoader: {e}")
            st.session_state.sheets = None
            st.session_state.sheets_status = {"sheets": 0, "rows": 0}
            return

    if loader.is_configured():
        try:
            n_sheets, n_rows = loader.load_all()
            st.session_state.sheets = loader
            st.session_state.sheets_status = {"sheets": n_sheets, "rows": n_rows}
            st.session_state.sheets_last_loaded = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            st.error(f"❌ Erro ao carregar planilhas: {e}")
            st.session_state.sheets = None
            st.session_state.sheets_status = {"sheets": 0, "rows": 0}
    else:
        st.warning("⚠️ SheetsLoader não configurado - verifique credenciais e SHEETS_FOLDER_ID")
        st.session_state.sheets = None
        st.session_state.sheets_status = {"sheets": 0, "rows": 0}


# -------------------------------------------------------
# App
# -------------------------------------------------------
def main() -> None:
    initialize_session()

    # ---------------- Sidebar ----------------
    with st.sidebar:
        st.markdown("### 📚 Dados carregados")

        loader = st.session_state.get("sheets")
        rows_total = 0
        worksheets_count = 0
        sheets_count = 0
        last_loaded = st.session_state.get("sheets_last_loaded")
        last_loaded_ts = st.session_state.get("sheets_last_loaded_ts")

        if loader:
            try:
                status = loader.status()
                worksheets_count = status.get("worksheets_count", 0)
                sheets_count = status.get("sheets_count", 0)
                loaded_map = status.get("loaded", {}) or {}
                rows_total = sum(int(v) for v in loaded_map.values()) if loaded_map else 0
            except Exception:
                pass

        st.metric("Linhas carregadas", f"{rows_total:,}".replace(",", "."))
        st.caption(f"Planilhas: {sheets_count} · Abas: {worksheets_count}")
        if last_loaded:
            st.caption(f"Última atualização: {last_loaded}")
        st.divider()

        # Diagnóstico rápido (sem botões)
        with st.expander("🔧 Diagnóstico", expanded=False):
            try:
                sa_email = get_service_account_email() or "(não disponível)"
            except Exception:
                sa_email = "(erro ao obter)"
            st.caption(f"Service Account: {sa_email}")
            st.caption(f"Pasta (SHEETS_FOLDER_ID): {st.session_state.get('sheets').sheet_folder_id if loader else ''}")
            try:
                status = loader.status() if loader else {}
                dbg = status.get("debug", {}) if status else {}
                rec_flag = status.get("recursive", False)
                st.caption(f"Listagem recursiva: {'sim' if rec_flag else 'não'}")
                files_found = dbg.get("files_found", [])
                last_errors = dbg.get("last_errors", [])
                if files_found:
                    st.write(f"Arquivos encontrados: {len(files_found)}")
                    st.dataframe(pd.DataFrame(files_found)[:20], use_container_width=True, hide_index=True)
                if last_errors:
                    st.warning("\n".join(map(str, last_errors)))
                # Dica de permissão
                if files_found and len(files_found) <= 1:
                    st.info("Compartilhe a pasta do Drive e as planilhas com o e-mail da Service Account acima para ampliar o acesso.")
            except Exception as e:
                st.caption(f"(diagnóstico indisponível: {e})")

        # TTL controls — sem default value no widget (usa session_state)
        st.markdown("#### ⚙️ Recarga automática (TTL)")
        st.checkbox("Habilitar recarga automática", key="sheets_ttl_enabled")
        st.number_input("TTL (segundos)", min_value=10, max_value=3600, step=10, key="sheets_ttl_seconds")

        if st.session_state["sheets_ttl_enabled"] and last_loaded_ts:
            try:
                ttl_secs = int(st.session_state.get("sheets_ttl_seconds", 60))
                eta = max(0, ttl_secs - int(time.time() - float(last_loaded_ts)))
                st.caption(f"Próxima recarga automática em ~{eta}s")
            except Exception:
                pass

        st.divider()

        # Removido: botão de recarregar manualmente (sem botões na UI)
        st.divider()

        # Prévia das abas
        if loader:
            try:
                status = loader.status()
                loaded_map = status.get("loaded", {}) or {}
                if loaded_map:
                    st.markdown("#### 📄 Abas carregadas")
                    preview = []
                    for key, cnt in loaded_map.items():
                        sheet_id = key.split("::")[0] if "::" in key else "?"
                        ws_title = key.split("::")[1] if "::" in key else key
                        preview.append({"Aba": ws_title, "Planilha (ID)": sheet_id, "Linhas": int(cnt)})
                    preview.sort(key=lambda x: x["Linhas"], reverse=True)
                    st.dataframe(preview, use_container_width=True, hide_index=True)
            except Exception:
                pass

        # Removido: controles de UI para dados brutos (agora automático)

        # Removido: botão de download de snapshot JSON (sem botões na UI)

    # ---------------- Landing / Chat ----------------
    if not st.session_state.messages:
        st.markdown(
            """
            <div class="hero-landing">
                <div class="logo-container">
                    <svg class="logo-icon" viewBox="0 0 24 24" fill="none">
                        <path d="M12 2L2 7v10c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-10-5z"
                              stroke="currentColor" stroke-width="2" stroke-linecap="round"
                              stroke-linejoin="round" fill="none"/>
                        <path d="M12 8v8m-4-4h8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                    <div class="brand-name">Quasar</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="landing-footer">
                Ao usar o Quasar, você concorda com nossos
                <a href="#">termos</a> e <a href="#">política de privacidade</a>.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div class="chat-messages">', unsafe_allow_html=True)
        display_chat_messages()
        st.markdown("</div>", unsafe_allow_html=True)

    # (Removido) Perguntas presetadas acima da caixa de chat

    # Campo de chat
    user_input = st.chat_input("O que você quer saber?")
    if user_input:
        st.session_state.messages.append(
            {"role": "user", "content": user_input, "timestamp": datetime.now().strftime("%H:%M")}
        )
        st.rerun()

    # Processa a última pergunta
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        last_user_msg = st.session_state.messages[-1]["content"]

        with st.chat_message("assistant"):
            ph = st.empty()
            ph.markdown("_Digitando..._")

        conversation_history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[:-1]]

        sheets_ctx = ""
        loader = st.session_state.get("sheets")
        if loader:
            # Detecta se o usuário forneceu links/IDs de planilha e carrega on-demand
            try:
                import re as _re
                # URLs do Google Sheets e IDs puros (>= 20 chars alfanum/ - _)
                ids = []
                for m in _re.finditer(r"https?://docs\.google\.com/spreadsheets/d/([A-Za-z0-9-_]+)", last_user_msg):
                    ids.append(m.group(1))
                for m in _re.finditer(r"\b([A-Za-z0-9-_]{20,})\b", last_user_msg):
                    ids.append(m.group(1))
                ids = list(dict.fromkeys(ids))  # unique, keep order
                if ids:
                    try:
                        loader.load_by_ids(ids)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                base = loader.base_summary(top_n=3)
                extra = {}
                # Inclui lista de planilhas acessíveis (nomes) para evitar confusão do LLM
                try:
                    st_status = loader.status()
                    files_found = st_status.get("debug", {}).get("files_found", [])
                    if files_found:
                        extra["planilhas_acessiveis"] = [f.get("name") for f in files_found if f.get("name")][:50]
                except Exception:
                    pass
                if base.get("found"):
                    merged = dict(base)
                    if extra:
                        merged.update(extra)
                    sheets_ctx = "Contexto (base):\n" + json.dumps(merged, ensure_ascii=False)
            except Exception:
                pass

            text_lower = last_user_msg.lower()
            handled = False

            # 1) Query: top produtos
            if (("top" in text_lower or "mais vendido" in text_lower or "mais vendidos" in text_lower or "top 3" in text_lower)
                    and ("produto" in text_lower)):
                if any(t in text_lower for t in ["todos os meses", "cada mês", "cada mes", "por mês", "por mes"]):
                    res_all = loader.top_products_by_month_all(top_n=3)
                    if res_all.get("found"):
                        sheets_ctx = (sheets_ctx + "\n\n" + "Contexto (dados agregados por mês):\n" + json.dumps(res_all, ensure_ascii=False)).strip()
                        handled = True
                else:
                    ym = loader.parse_month_year(last_user_msg)
                    if ym:
                        year, month_num = ym
                        month_names = {
                            "01": "janeiro", "02": "fevereiro", "03": "março", "04": "abril",
                            "05": "maio", "06": "junho", "07": "julho", "08": "agosto",
                            "09": "setembro", "10": "outubro", "11": "novembro", "12": "dezembro",
                        }
                        month_name = month_names.get(month_num, month_num)
                        res = loader.top_products(month_name, year, top_n=3)
                        if res.get("found"):
                            agg_ctx = {
                                "ano": res.get("year"),
                                "mes": res.get("month"),
                                "top_por_quantidade": res.get("by_quantity", []),
                                "top_por_receita": res.get("by_revenue", []),
                            }
                            sheets_ctx = (sheets_ctx + "\n\n" + "Contexto (dados agregados):\n" + json.dumps(agg_ctx, ensure_ascii=False)).strip()
                            handled = True
                    else:
                        # Sem mês/ano explícitos: usa o período mais recente
                        res_def = loader.top_products_default(top_n=3)
                        if res_def.get("found"):
                            agg_ctx = {
                                "ano": res_def.get("year"),
                                "mes": res_def.get("month"),
                                "top_por_quantidade": res_def.get("by_quantity", []),
                                "top_por_receita": res_def.get("by_revenue", []),
                            }
                            sheets_ctx = (sheets_ctx + "\n\n" + "Contexto (dados agregados):\n" + json.dumps(agg_ctx, ensure_ascii=False)).strip()
                            handled = True

            # 2) Query: receita total por mês/ano ("fatura", "receita total", etc.)
            if not handled and any(w in text_lower for w in ["fatura", "receita", "faturamento", "total"]):
                ym = loader.parse_month_year(last_user_msg)
                year = month_num = None
                if ym:
                    year, month_num = ym
                    if month_num and not year:
                        y_latest = loader.latest_year_for_month(month_num)
                        if y_latest:
                            year = y_latest
                if year and month_num:
                    res_rev = loader.revenue_total(year, month_num)
                else:
                    res_rev = loader.revenue_total_latest()
                if res_rev.get("found"):
                    sheets_ctx = (sheets_ctx + "\n\n" + "Contexto (receita total do mês):\n" + json.dumps(res_rev, ensure_ascii=False)).strip()
                    handled = True

            # 3) Query: receita por ID de transação
            if not handled:
                import re
                m = re.search(r"\b([A-Za-z]-\d{6}-\d+)\b|\b(T-\d{6}-\d+)\b", last_user_msg)
                trans_id = m.group(0) if m else None
                if trans_id and ("receita" in text_lower or "valor" in text_lower or "total" in text_lower):
                    ym = loader.parse_month_year(last_user_msg)
                    year = month_num = None
                    if ym:
                        year, month_num = ym
                    res_tx = loader.revenue_by_transaction(trans_id, year=year, month_num=month_num)
                    if res_tx.get("found"):
                        sheets_ctx = (sheets_ctx + "\n\n" + "Contexto (receita por transação):\n" + json.dumps(res_tx, ensure_ascii=False)).strip()
                        handled = True

            # 4) Fallback: busca por produtos
            if not handled:
                rows = loader.search_advanced(last_user_msg, top_k=5)
                sheets_ctx = loader.build_context_snippet(rows)

        # Dados brutos: SEMPRE enviar FULL (jsonl) como contexto bruto
        raw_ctx = ""
        if loader:
            try:
                max_chars = int(st.session_state.get("raw_max_chars", 200000))
                raw_ctx = loader.build_raw_context(
                    layer="full",
                    rows_per_sheet=int(st.session_state.get("raw_rows_per_sheet", 500)),
                    fmt="jsonl",
                    max_chars=max_chars,
                )
            except Exception as e:
                raw_ctx = f"[falha ao gerar dados brutos: {e}]"

        full_ctx_parts = []
        if sheets_ctx:
            full_ctx_parts.append("Contexto (planilhas/agregações):\n" + sheets_ctx)
        if raw_ctx:
            full_ctx_parts.append("Contexto (dados brutos):\n" + raw_ctx)
        if not full_ctx_parts:
            full_ctx_parts.append("[sem contexto disponível]")

        final_prompt = "\n\n".join(full_ctx_parts) + "\n\nPergunta do usuário: " + last_user_msg

        if st.session_state.client:
            try:
                resp = st.session_state.client.send_message(final_prompt, conversation_history)
                content = resp.get("message", "") if isinstance(resp, dict) else str(resp)
            except Exception as e:
                content = f"Falha ao consultar o modelo: {e}"
        else:
            content = "Não foi possível conectar ao modelo neste momento."

        st.session_state.messages.append({"role": "assistant", "content": content, "timestamp": datetime.now().strftime("%H:%M")})
        st.rerun()

    if st.session_state.messages:
        st.markdown("<script>window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});</script>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
