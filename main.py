"""
Quasar Analytics - Assistente Analítico de Vendas
Chatbot com IA para análise de dados de vendas via Google Sheets
"""
import os
import json
import time
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from ui_styles import render_css

# --- Config centralizada do projeto (Cloud-first)
from app.config import (
    get_abacus_api_key,
    get_model_name,
    get_service_account_email,
)

# --- Loader novo (Google APIs nativas; sem gspread)
from app.sheets_loader import SheetsLoader

# --- Cliente do modelo
from abacus_client import AbacusClient


# -------------------------------------------------------
# Boot
# -------------------------------------------------------
load_dotenv()

st.set_page_config(
    page_title="Quasar Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
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
        # validação opcional (se seu AbacusClient não tiver este método, ignora)
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
    """Inicializa variáveis de sessão e carrega planilhas com TTL."""
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

    # TTL de recarga
    st.session_state.setdefault("sheets_ttl_enabled", False)
    st.session_state.setdefault("sheets_ttl_seconds", 60)
    last_loaded_ts = st.session_state.get("sheets_last_loaded_ts")

    loader = st.session_state.get("sheets") or SheetsLoader()
    should_reload = True
    if st.session_state["sheets_ttl_enabled"] and last_loaded_ts:
        try:
            age = time.time() - float(last_loaded_ts)
            if age < int(st.session_state["sheets_ttl_seconds"]):
                should_reload = False
        except Exception:
            should_reload = True

    if loader.is_configured():
        try:
            if should_reload:
                n_sheets, n_rows = loader.load_all()
                st.session_state.sheets = loader
                st.session_state.sheets_status = {"sheets": n_sheets, "rows": n_rows}
                st.session_state.sheets_last_loaded = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state.sheets_last_loaded_ts = time.time()
            else:
                st.session_state.sheets = loader
                st.session_state.setdefault("sheets_status", {"sheets": 0, "rows": 0})
        except Exception as e:
            # mantém cache anterior se existir
            st.session_state.sheets = st.session_state.get("sheets")
            st.session_state.setdefault("sheets_status", {"sheets": 0, "rows": 0})
            st.warning(f"Falha ao carregar planilhas (mantendo cache anterior): {e}")
    else:
        st.session_state.sheets = None
        st.session_state.sheets_status = {"sheets": 0, "rows": 0}


# -------------------------------------------------------
# App
# -------------------------------------------------------
def main() -> None:
    initialize_session()

    # ---------------- Sidebar: status e diagnóstico ----------------
    with st.sidebar:
        st.markdown("### 📚 Dados carregados")

        rows_total = 0
        worksheets_count = 0
        sheets_count = 0
        last_loaded = st.session_state.get("sheets_last_loaded")
        last_loaded_ts = st.session_state.get("sheets_last_loaded_ts")

        loader = st.session_state.get("sheets")
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

        sa_email = get_service_account_email()
        if sa_email:
            st.info(
                "No Streamlit Cloud, compartilhe a pasta do Drive (SHEETS_FOLDER_ID) "
                f"com a Service Account: **{sa_email}**",
                icon="ℹ️",
            )
        else:
            st.info(
                "Defina os segredos da Service Account no Streamlit (chave `google_service_account` no secrets).",
                icon="ℹ️",
            )

        # TTL controls
        st.markdown("#### ⚙️ Recarga automática (TTL)")
        st.checkbox(
            "Habilitar recarga automática",
            value=st.session_state["sheets_ttl_enabled"],
            key="sheets_ttl_enabled",
        )
        st.number_input(
            "TTL (segundos)",
            min_value=10,
            max_value=3600,
            value=int(st.session_state["sheets_ttl_seconds"]),
            step=10,
            key="sheets_ttl_seconds",
        )
        if st.session_state["sheets_ttl_enabled"] and last_loaded_ts:
            try:
                eta = max(0, int(int(st.session_state["sheets_ttl_seconds"]) - (time.time() - float(last_loaded_ts))))
                st.caption(f"Próxima recarga automática em ~{eta}s")
            except Exception:
                pass

        st.divider()

        # Recarregar manualmente
        if loader and st.button("Recarregar planilhas agora"):
            try:
                n_sheets, n_rows = loader.load_all()
                st.session_state.sheets_status = {"sheets": n_sheets, "rows": n_rows}
                st.session_state.sheets_last_loaded = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state.sheets_last_loaded_ts = time.time()
                st.success("Planilhas recarregadas.")
                st.rerun()
            except Exception as e:
                st.error(f"Falha ao recarregar: {e}")

        st.divider()

        # Diagnóstico
        with st.expander("Diagnóstico (detalhes)"):
            try:
                _status = loader.status() if loader else SheetsLoader().status()
            except Exception as _e:
                _status = {"configured": False, "debug": {"exception": str(_e)}}

            def presence():
                keys = {
                    "google_service_account (secrets)": False,
                    "SHEETS_FOLDER_ID": False,
                    "SHEETS_IDS": False,
                    "SHEET_RANGE": False,
                    "ABACUS_API_KEY": False,
                }
                try:
                    sec = st.secrets
                    if isinstance(sec.get("google_service_account", None), dict):
                        keys["google_service_account (secrets)"] = True
                    if str(sec.get("SHEETS_FOLDER_ID", "")).strip():
                        keys["SHEETS_FOLDER_ID"] = True
                    if str(sec.get("SHEETS_IDS", "")).strip():
                        keys["SHEETS_IDS"] = True
                    if str(sec.get("SHEET_RANGE", "")).strip():
                        keys["SHEET_RANGE"] = True
                    if str(sec.get("ABACUS_API_KEY", "")).strip():
                        keys["ABACUS_API_KEY"] = True
                except Exception:
                    pass

                env = os.environ
                if str(env.get("SHEETS_FOLDER_ID", "")).strip():
                    keys["SHEETS_FOLDER_ID"] = True
                if str(env.get("SHEETS_IDS", "")).strip():
                    keys["SHEETS_IDS"] = True
                if str(env.get("SHEET_RANGE", "")).strip():
                    keys["SHEET_RANGE"] = True
                if str(env.get("ABACUS_API_KEY", "")).strip():
                    keys["ABACUS_API_KEY"] = True
                return keys

            st.json(
                {
                    "configured": _status.get("configured", False),
                    "sheets_folder_id": _status.get("sheets_folder_id", ""),
                    "resolved_sheet_ids_preview": (_status.get("resolved_sheet_ids", []) or [])[:5],
                    "debug": _status.get("debug", {}),
                    "presence": presence(),
                }
            )

        # Preview de abas
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
                        preview.append(
                            {"Aba": ws_title, "Planilha (ID)": sheet_id, "Linhas": int(cnt)}
                        )
                    preview = sorted(preview, key=lambda x: x["Linhas"], reverse=True)
                    st.dataframe(preview, use_container_width=True, hide_index=True)
            except Exception:
                pass

        # Snapshot JSON do contexto
        if loader:
            try:
                loader_status = loader.status()
                loaded_map = loader_status.get("loaded", {}) or {}
                snapshot = {
                    "sheets_ids": loader_status.get(
                        "resolved_sheet_ids", getattr(loader, "sheet_ids", [])
                    ),
                    "worksheets": [
                        {
                            "sheet_id": key.split("::")[0] if "::" in key else key,
                            "worksheet": key.split("::")[1] if "::" in key else "",
                            "rows": int(cnt),
                            "columns": list(loader._cache.get(key).columns)
                            if key in loader._cache
                            else [],
                        }
                        for key, cnt in loaded_map.items()
                    ],
                    "totals": {
                        "worksheets": len(loaded_map),
                        "rows": sum(int(v) for v in loaded_map.values())
                        if loaded_map
                        else 0,
                    },
                    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                st.download_button(
                    "⬇️ Baixar contexto (JSON)",
                    data=json.dumps(snapshot, ensure_ascii=False, indent=2).encode("utf-8"),
                    file_name="quasar_context_snapshot.json",
                    mime="application/json",
                )
            except Exception:
                pass

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
        st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("🔍 Análise Completa", use_container_width=True, key="chip1"):
                st.session_state.messages.append(
                    {"role": "user", "content": "Mostre uma análise de vendas do último mês",
                     "timestamp": datetime.now().strftime("%H:%M")}
                )
                st.rerun()
        with c2:
            if st.button("📊 Top Produtos", use_container_width=True, key="chip2"):
                st.session_state.messages.append(
                    {"role": "user", "content": "Quais foram os produtos mais vendidos?",
                     "timestamp": datetime.now().strftime("%H:%M")}
                )
                st.rerun()
        with c3:
            if st.button("💰 Performance", use_container_width=True, key="chip3"):
                st.session_state.messages.append(
                    {"role": "user", "content": "Como está a performance de vendas este ano?",
                     "timestamp": datetime.now().strftime("%H:%M")}
                )
                st.rerun()
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

    # Campo de chat
    user_input = st.chat_input("O que você quer saber?")
    if user_input:
        st.session_state.messages.append(
            {"role": "user", "content": user_input, "timestamp": datetime.now().strftime("%H:%M")}
        )
        st.rerun()

    # Processamento da última mensagem do usuário
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        last_user_msg = st.session_state.messages[-1]["content"]

        with st.chat_message("assistant"):
            ph = st.empty()
            ph.markdown("_Digitando..._")

        conversation_history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[:-1]
        ]

        # --- Monta Contexto com base nas planilhas carregadas
        sheets_ctx = ""
        loader = st.session_state.get("sheets")

        if loader:
            # Base: resumo determinístico
            try:
                base = loader.base_summary(top_n=3)
                if base.get("found"):
                    sheets_ctx = "Contexto (base):\n" + json.dumps(base, ensure_ascii=False)
            except Exception:
                pass

            text_lower = last_user_msg.lower()

            # Top-N por mês (todos ou específico)
            if (("top" in text_lower or "mais vendido" in text_lower or
                 "mais vendidos" in text_lower or "top 3" in text_lower)
                    and ("produto" in text_lower)):
                # todos os meses
                if any(token in text_lower for token in ["todos os meses", "cada mês", "cada mes", "por mês", "por mes"]):
                    res_all = loader.top_products_by_month_all(top_n=3)
                    if res_all.get("found"):
                        sheets_ctx = (sheets_ctx + "\n\n" +
                                      "Contexto (dados agregados por mês):\n" +
                                      json.dumps(res_all, ensure_ascii=False)).strip()
                # mês específico
                if not sheets_ctx:
                    ym = loader.parse_month_year(last_user_msg)
                    if ym:
                        year, month_num = ym
                        month_names = {
                            "01": "janeiro", "02": "fevereiro", "03": "março",
                            "04": "abril", "05": "maio", "06": "junho",
                            "07": "julho", "08": "agosto", "09": "setembro",
                            "10": "outubro", "11": "novembro", "12": "dezembro",
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
                            sheets_ctx = (sheets_ctx + "\n\n" +
                                          "Contexto (dados agregados):\n" +
                                          json.dumps(agg_ctx, ensure_ascii=False)).strip()

            # Busca genérica
            if not sheets_ctx:
                rows = loader.search_advanced(last_user_msg, top_k=5)
                sheets_ctx = loader.build_context_snippet(rows)

        # Prompt final
        final_prompt = (
            "Contexto (planilhas/agregações):\n" +
            (sheets_ctx if sheets_ctx else "[sem contexto disponível]") +
            "\n\nPergunta do usuário: " + last_user_msg
        )

        # Chamada ao modelo
        if st.session_state.client:
            try:
                resp = st.session_state.client.send_message(final_prompt, conversation_history)
                content = resp.get("message", "") if isinstance(resp, dict) else str(resp)
            except Exception as e:
                content = f"Falha ao consultar o modelo: {e}"
        else:
            content = "Não foi possível conectar ao modelo neste momento."

        st.session_state.messages.append(
            {"role": "assistant", "content": content, "timestamp": datetime.now().strftime("%H:%M")}
        )
        st.rerun()

    # Auto-scroll
    if st.session_state.messages:
        st.markdown(
            """
            <script>window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});</script>
            """,
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
