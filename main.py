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

from app.ui_styles import render_css

# --- Config centralizada do projeto (Cloud-first)
from app.config import (
    get_abacus_api_key,
    get_model_name,
    get_service_account_email,
)

# --- Loader novo (Google APIs nativas; sem gspread)
from app.sheets_loader import SheetsLoader

# --- Cliente do modelo
from app.abacus_client import AbacusClient

# ===== NOVO: Imports para RAG =====
from app.prompts import get_system_prompt
from app.cache_manager import CacheManager

# Import condicional do RAG Engine
try:
    from app.rag_engine import RAGEngine
    HAS_RAG = True
except ImportError:
    HAS_RAG = False
    print("⚠️ RAG Engine não disponível. Instale: pip install chromadb sentence-transformers")
# ===================================


# -------------------------------------------------------
# Boot
# -------------------------------------------------------
# Carrega as variáveis de ambiente do arquivo .env, caso exista.
load_dotenv()

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Quasar Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Aplica estilo customizado (tema dark) carregado via ui_styles
render_css("dark")


# -------------------------------------------------------
# Helpers
# -------------------------------------------------------
def get_env_config() -> tuple[str, str]:
    """Lê API key e modelo via config central (st.secrets ou .env)."""
    api_key = get_abacus_api_key() or ""
    model = get_model_name(default="gemini-2.5-pro")
    return api_key, model


def create_client(api_key: str, model: str = "gemini-2.5-pro") -> AbacusClient | None:
    """Cria o cliente do modelo com tratamento de erro."""
    try:
        client = AbacusClient(api_key=api_key, model=model)
        # Validação opcional se a biblioteca oferecer esse método
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
    """Renderiza o histórico de mensagens do chat na interface."""
    for message in st.session_state.messages:
        role = "user" if message.get("role") == "user" else "assistant"
        with st.chat_message(role):
            st.markdown(message.get("content", ""))


def initialize_session() -> None:
    """Inicializa variáveis de sessão e carrega planilhas com TTL."""
    # Estado básico
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("client", None)
    st.session_state.setdefault("sheets", None)

    # API key e modelo
    if "api_key" not in st.session_state or "model" not in st.session_state:
        api_key, model = get_env_config()
        st.session_state.api_key = api_key
        st.session_state.model = model
        if api_key:
            st.session_state.client = create_client(api_key, model)

    # TTL de recarga
    # Definições padrão de TTL, que serão usadas pelo widget se o valor não existir ainda
    st.session_state.setdefault("sheets_ttl_enabled", False)
    st.session_state.setdefault("sheets_ttl_seconds", 60)

    last_loaded_ts = st.session_state.get("sheets_last_loaded_ts")
    loader: SheetsLoader = st.session_state.get("sheets") or SheetsLoader()

    # Determina se deve recarregar com base no TTL
    should_reload = True
    if st.session_state["sheets_ttl_enabled"] and last_loaded_ts:
        try:
            age = time.time() - float(last_loaded_ts)
            if age < int(st.session_state["sheets_ttl_seconds"]):
                should_reload = False
        except Exception:
            should_reload = True

    # Carrega planilhas se configurado e se precisa recarregar
    if loader.is_configured():
        try:
            if should_reload:
                n_sheets, n_rows = loader.load_all()
                st.session_state.sheets = loader
                st.session_state.sheets_status = {"sheets": n_sheets, "rows": n_rows}
                st.session_state.sheets_last_loaded = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state.sheets_last_loaded_ts = time.time()
                
                # ========== INICIALIZAÇÃO RAG (NOVO) ==========
                # Inicializa RAG Engine após carregamento bem-sucedido
                if HAS_RAG and os.getenv("ENABLE_RAG", "True").lower() == "true":
                    try:
                        _initialize_rag(loader)
                    except Exception as e_rag:
                        st.warning(f"⚠️ RAG não pôde ser inicializado (continuando com busca tradicional): {e_rag}")
            else:
                # Se não recarrega, mantém o loader atual
                st.session_state.sheets = loader
                st.session_state.setdefault("sheets_status", {"sheets": 0, "rows": 0})
        except Exception as e:
            # Em caso de falha no carregamento, mantém o loader anterior
            st.session_state.sheets = st.session_state.get("sheets")
            st.session_state.setdefault("sheets_status", {"sheets": 0, "rows": 0})
            st.warning(f"Falha ao carregar planilhas (mantendo cache anterior): {e}")
    else:
        st.session_state.sheets = None
        st.session_state.sheets_status = {"sheets": 0, "rows": 0}


# -------------------------------------------------------
# RAG Initialization (NOVO)
# -------------------------------------------------------
def _initialize_rag(loader: SheetsLoader) -> None:
    """
    Inicializa o motor RAG e indexa dados se necessário.
    Resolve problema: ❌ Sem persistência + ❌ Busca por keywords
    """
    try:
        # Configurações do .env
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")
        embedding_model = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        enable_smart_cache = os.getenv("ENABLE_SMART_CACHE", "True").lower() == "true"
        
        # Inicializa RAG Engine (singleton em session_state)
        if "rag_engine" not in st.session_state:
            with st.spinner("🔄 Inicializando motor RAG (primeira vez)..."):
                st.session_state.rag_engine = RAGEngine(
                    persist_dir=persist_dir,
                    embedding_model=embedding_model
                )
        
        rag: RAGEngine = st.session_state.rag_engine
        
        # Cache Manager para smart reindexing
        cache_mgr = CacheManager()
        current_hash = cache_mgr.get_data_hash(loader._cache)
        
        # Verifica se precisa reindexar (baseado em hash)
        if enable_smart_cache and not cache_mgr.needs_reindex(current_hash):
            print("✅ Cache RAG válido, pulando reindexação")
            return
        
        # Reindexação necessária
        with st.spinner("🔄 Indexando dados com RAG (pode levar alguns segundos)..."):
            # Limpa índice antigo
            rag.clear()
            
            # Indexa novos dados
            batch_size = int(os.getenv("INDEXING_BATCH_SIZE", "100"))
            indexed = rag.index_dataframes(loader._cache, batch_size=batch_size)
            
            # Salva hash e metadados
            cache_mgr.save_hash(current_hash)
            cache_mgr.save_metadata({
                "timestamp": time.time(),
                "total_docs": indexed,
                "sheets_count": len(loader._cache),
                "embedding_model": embedding_model
            })
            
            st.success(f"✅ {indexed} documentos indexados com RAG!")
    
    except Exception as e:
        st.warning(f"⚠️ Erro ao inicializar RAG (fallback para busca tradicional): {e}")
        st.session_state.rag_engine = None


# -------------------------------------------------------
# App principal
# -------------------------------------------------------
def main() -> None:
    # Inicializa sessão e possivelmente recarrega dados
    initialize_session()

    # ---------------------------------------------------
    # Barra lateral: status, TTL e diagnósticos
    # ---------------------------------------------------
    with st.sidebar:
        st.markdown("### 📚 Dados carregados")

        loader: SheetsLoader | None = st.session_state.get("sheets")
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

        # Instruções sobre a Service Account
        sa_email = get_service_account_email()
        if sa_email:
            st.info(
                "No Streamlit Cloud, compartilhe a pasta do Drive (SHEETS_FOLDER_ID) "
                f"com a Service Account: **{sa_email}**",
                icon="ℹ️",
            )
        else:
            st.info(
                "Defina os segredos da Service Account no Streamlit (chave `google_service_account`).",
                icon="ℹ️",
            )

        # Controles de TTL
        st.markdown("#### ⚙️ Recarga automática (TTL)")
        st.checkbox(
            "Habilitar recarga automática",
            key="sheets_ttl_enabled",
        )
        st.number_input(
            "TTL (segundos)",
            min_value=10,
            max_value=3600,
            step=10,
            key="sheets_ttl_seconds",
        )
        # Mostra tempo estimado para a próxima recarga
        if st.session_state["sheets_ttl_enabled"] and last_loaded_ts:
            try:
                ttl_secs = int(st.session_state.get("sheets_ttl_seconds", 60))
                eta = max(0, ttl_secs - int(time.time() - float(last_loaded_ts)))
                st.caption(f"Próxima recarga automática em ~{eta}s")
            except Exception:
                pass

        st.divider()

        # Botão para recarregar planilhas manualmente
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

        # Diagnóstico detalhado
        with st.expander("Diagnóstico (detalhes)"):
            try:
                diag_status = loader.status() if loader else SheetsLoader().status()
            except Exception as diag_e:
                diag_status = {"configured": False, "debug": {"exception": str(diag_e)}}

            def presence_snapshot() -> dict[str, bool]:
                """Retorna quais chaves estão presentes em secrets/env (sem vazar valores)."""
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
                # Verifica env vars
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
                    "configured": diag_status.get("configured", False),
                    "sheets_folder_id": diag_status.get("sheets_folder_id", ""),
                    "resolved_sheet_ids_preview": (
                        (diag_status.get("resolved_sheet_ids", []) or [])[:5]
                    ),
                    "debug": diag_status.get("debug", {}),
                    "presence": presence_snapshot(),
                }
            )

        # Prévia de abas carregadas
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
                            {
                                "Aba": ws_title,
                                "Planilha (ID)": sheet_id,
                                "Linhas": int(cnt),
                            }
                        )
                    preview.sort(key=lambda x: x["Linhas"], reverse=True)
                    st.dataframe(preview, use_container_width=True, hide_index=True)
            except Exception:
                pass

        # Snapshot JSON do contexto
        if loader:
            try:
                status = loader.status()
                loaded_map = status.get("loaded", {}) or {}
                snapshot = {
                    "sheets_ids": status.get(
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
                        "rows": sum(int(v) for v in loaded_map.values()) if loaded_map else 0,
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

    # ---------------------------------------------------
    # Corpo: Landing page ou Chat
    # ---------------------------------------------------
    if not st.session_state.messages:
        # Página inicial sem perguntas
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

        # Três botões para perguntas rápidas (landing chips)
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔍 Análise Completa", use_container_width=True, key="chip1"):
                st.session_state.messages.append(
                    {
                        "role": "user",
                        "content": "Mostre uma análise de vendas do último mês",
                        "timestamp": datetime.now().strftime("%H:%M"),
                    }
                )
                st.rerun()
        with col2:
            if st.button("📊 Top Produtos", use_container_width=True, key="chip2"):
                st.session_state.messages.append(
                    {
                        "role": "user",
                        "content": "Quais foram os produtos mais vendidos?",
                        "timestamp": datetime.now().strftime("%H:%M"),
                    }
                )
                st.rerun()
        with col3:
            if st.button("💰 Performance", use_container_width=True, key="chip3"):
                st.session_state.messages.append(
                    {
                        "role": "user",
                        "content": "Como está a performance de vendas este ano?",
                        "timestamp": datetime.now().strftime("%H:%M"),
                    }
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
        # Chat em andamento
        st.markdown('<div class="chat-messages">', unsafe_allow_html=True)
        display_chat_messages()
        st.markdown('</div>', unsafe_allow_html=True)

    # Campo de chat para nova pergunta
    user_input = st.chat_input("O que você quer saber?")
    if user_input:
        st.session_state.messages.append(
            {
                "role": "user",
                "content": user_input,
                "timestamp": datetime.now().strftime("%H:%M"),
            }
        )
        st.rerun()

    # Processamento da última mensagem do usuário para gerar resposta
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        last_user_msg = st.session_state.messages[-1]["content"]
        # Placeholder de "digitando..."
        with st.chat_message("assistant"):
            ph = st.empty()
            ph.markdown("_Digitando..._")

        # Histórico de conversa (todas menos a última)
        conversation_history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[:-1]
        ]

        # Monta contexto baseado nas planilhas
        sheets_ctx = ""
        loader = st.session_state.get("sheets")
        if loader:
            # Resumo determinístico
            try:
                base = loader.base_summary(top_n=3)
                if base.get("found"):
                    sheets_ctx = "Contexto (base):\n" + json.dumps(base, ensure_ascii=False)
            except Exception:
                pass

            text_lower = last_user_msg.lower()

            # Pergunta sobre top produtos
            if (
                ("top" in text_lower or "mais vendido" in text_lower or "mais vendidos" in text_lower or "top 3" in text_lower)
                and ("produto" in text_lower)
            ):
                # Todos os meses / por mês
                if any(token in text_lower for token in ["todos os meses", "cada mês", "cada mes", "por mês", "por mes"]):
                    res_all = loader.top_products_by_month_all(top_n=3)
                    if res_all.get("found"):
                        sheets_ctx = (
                            sheets_ctx
                            + "\n\nContexto (dados agregados por mês):\n"
                            + json.dumps(res_all, ensure_ascii=False)
                        ).strip()
                # Mês específico
                if not sheets_ctx:
                    ym = loader.parse_month_year(last_user_msg)
                    if ym:
                        year, month_num = ym
                        month_names = {
                            "01": "janeiro",
                            "02": "fevereiro",
                            "03": "março",
                            "04": "abril",
                            "05": "maio",
                            "06": "junho",
                            "07": "julho",
                            "08": "agosto",
                            "09": "setembro",
                            "10": "outubro",
                            "11": "novembro",
                            "12": "dezembro",
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
                            sheets_ctx = (
                                sheets_ctx
                                + "\n\nContexto (dados agregados):\n"
                                + json.dumps(agg_ctx, ensure_ascii=False)
                            ).strip()

            # Busca genérica quando não há agregação
            if not sheets_ctx:
                # ========== BUSCA RAG (NOVO) ==========
                # Tenta usar RAG Engine para busca semântica
                rag_engine = st.session_state.get("rag_engine")
                if HAS_RAG and rag_engine is not None:
                    try:
                        top_k = int(os.getenv("TOP_K", "15"))
                        results = rag_engine.search(last_user_msg, top_k=top_k)
                        sheets_ctx = rag_engine.build_context(results)
                    except Exception as e_rag:
                        st.warning(f"⚠️ Erro na busca RAG, usando busca tradicional: {e_rag}")
                        rows = loader.search_advanced(last_user_msg, top_k=5)
                        sheets_ctx = loader.build_context_snippet(rows)
                else:
                    # Fallback para busca tradicional
                    rows = loader.search_advanced(last_user_msg, top_k=5)
                    sheets_ctx = loader.build_context_snippet(rows)

        # Garante que sempre existe a seção Contexto
        final_prompt = (
            "Contexto (planilhas/agregações):\n"
            + (sheets_ctx if sheets_ctx else "[sem contexto disponível]")
            + "\n\nPergunta do usuário: "
            + last_user_msg
        )

        # Faz chamada ao modelo
        if st.session_state.client:
            try:
                resp = st.session_state.client.send_message(final_prompt, conversation_history)
                content = resp.get("message", "") if isinstance(resp, dict) else str(resp)
            except Exception as e:
                content = f"Falha ao consultar o modelo: {e}"
        else:
            content = "Não foi possível conectar ao modelo neste momento."

        # Adiciona resposta do assistente e rerun
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": content,
                "timestamp": datetime.now().strftime("%H:%M"),
            }
        )
        st.rerun()

    # Rola para baixo automaticamente quando há mensagens
    if st.session_state.messages:
        st.markdown(
            "<script>window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});</script>",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
