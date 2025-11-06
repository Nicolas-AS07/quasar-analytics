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

# Import condicional do RAG Engine (silencioso se não disponível)
try:
    from app.rag_engine import RAGEngine
    HAS_RAG = True
except ImportError:
    HAS_RAG = False
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
    model = get_model_name(default="gemini-2.0-flash-exp")
    
    # Debug: verifica se API key foi carregada
    if api_key:
        print(f"✅ Google Gemini API Key carregada (primeiros 10 chars): {api_key[:10]}...")
    else:
        print("⚠️ ERRO: API Key não encontrada! Verifique .env ou Streamlit Secrets")
        print("   Procurando por: GEMINI_API_KEY, ABACUS_API_KEY, API_KEY ou [abacus].API_KEY")
        print("   Obtenha sua chave em: https://aistudio.google.com/app/apikey")
    
    print(f"📋 Modelo Gemini selecionado: {model}")
    
    return api_key, model


def create_client(api_key: str, model: str = "gemini-2.0-flash-exp") -> AbacusClient | None:
    """Cria o cliente do modelo com tratamento de erro."""
    if not api_key or api_key.strip() == "":
        print("⚠️ API Key vazia - cliente não será criado")
        return None
        
    try:
        print(f"🔄 Criando cliente Abacus com modelo: {model}")
        client = AbacusClient(api_key=api_key, model=model)
        print("✅ Cliente Abacus criado com sucesso")
        return client
    except Exception as e:
        print(f"❌ Erro ao criar cliente do modelo: {e}")
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
    st.session_state.setdefault("sheets_status", {"sheets": 0, "rows": 0})

    # API key e modelo
    if "api_key" not in st.session_state or "model" not in st.session_state:
        api_key, model = get_env_config()
        st.session_state.api_key = api_key
        st.session_state.model = model
        if api_key:
            st.session_state.client = create_client(api_key, model)

    # ===== SIMPLIFICAÇÃO: Loader sempre reutiliza =====
    if st.session_state.sheets is None:
        st.session_state.sheets = SheetsLoader()
    
    loader: SheetsLoader = st.session_state.sheets
    
    # Carrega planilhas apenas se configurado E ainda não carregou
    if loader.is_configured() and not st.session_state.get("sheets_loaded", False):
        try:
            n_sheets, n_rows = loader.load_all()
            st.session_state.sheets_status = {"sheets": n_sheets, "rows": n_rows}
            st.session_state.sheets_loaded = True
            st.session_state.sheets_last_loaded = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"✅ Planilhas carregadas: {n_sheets} planilhas, {n_rows} linhas")
        except Exception as e:
            st.warning(f"Erro ao carregar planilhas: {e}")
            st.session_state.sheets_loaded = False


# -------------------------------------------------------
# RAG Initialization (NOVO)
# -------------------------------------------------------
# ===== RAG DESATIVADO TEMPORARIAMENTE (simplificação) =====
# def _initialize_rag(loader: SheetsLoader) -> None:
#     ... (código comentado para simplificar)
# ==========================================================


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

        # Rodapé (sem perguntas prontas)
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
        
        if loader and hasattr(loader, '_cache') and loader._cache:
            # ===== FILTRO INTELIGENTE POR MÊS =====
            text_lower = last_user_msg.lower()
            
            # DEBUG: Mostra o que tem carregado
            print(f"📊 DEBUG - Planilhas disponíveis:")
            for key in loader._cache.keys():
                print(f"  - {key}")
            
            # Detecta mês na pergunta
            meses = {
                'janeiro': '01', 'jan': '01',
                'fevereiro': '02', 'fev': '02',
                'março': '03', 'mar': '03',
                'abril': '04', 'abr': '04',
                'maio': '05', 'mai': '05',
                'junho': '06', 'jun': '06',
                'julho': '07', 'jul': '07',
                'agosto': '08', 'ago': '08',
                'setembro': '09', 'set': '09',
                'outubro': '10', 'out': '10',
                'novembro': '11', 'nov': '11',
                'dezembro': '12', 'dez': '12'
            }
            
            mes_filtro = None
            ano_filtro = None
            
            # Busca mês
            for nome_mes, num_mes in meses.items():
                if nome_mes in text_lower:
                    mes_filtro = num_mes
                    break
            
            # Busca ano (2024, 2023, etc)
            import re
            ano_match = re.search(r'20\d{2}', last_user_msg)
            if ano_match:
                ano_filtro = ano_match.group()
            else:
                ano_filtro = "2024"  # Padrão
            
            print(f"🔍 DEBUG - Filtro detectado: mês={mes_filtro}, ano={ano_filtro}")
            
            # Coleta dados filtrados ou todos
            all_data = []
            
            for sheet_key, df in loader._cache.items():
                if df is not None and not df.empty:
                    # Se detectou mês, filtra de forma FLEXÍVEL
                    if mes_filtro and ano_filtro:
                        # Tenta vários padrões de match:
                        # 1. _2024_01_
                        # 2. janeiro
                        # 3. _01_
                        # 4. _2024_janeiro_
                        # 5. _2024-01_ (hífen)
                        
                        key_lower = sheet_key.lower()
                        matches = (
                            f"_{ano_filtro}_{mes_filtro}_" in key_lower or
                            f"_{ano_filtro}-{mes_filtro}_" in key_lower or
                            f"_{ano_filtro}_{mes_filtro}" in key_lower or
                            f"{ano_filtro}_{mes_filtro}" in key_lower or
                            any(nome in key_lower for nome, num in meses.items() if num == mes_filtro)
                        )
                        
                        if matches:
                            print(f"✅ DEBUG - Match encontrado: {sheet_key} ({len(df)} linhas)")
                            # Pega TODAS as linhas da planilha do mês específico
                            all_data.extend(df.to_dict(orient='records'))
                        else:
                            print(f"❌ DEBUG - Ignorado: {sheet_key}")
                    else:
                        # Sem filtro: pega amostra de cada planilha
                        sample_df = df.head(50) if len(df) > 50 else df
                        all_data.extend(sample_df.to_dict(orient='records'))
            
            # Limita a 50 linhas totais (reduzido para evitar timeout)
            if len(all_data) > 50:
                all_data = all_data[:50]
            
            if all_data:
                sheets_ctx = json.dumps(all_data, ensure_ascii=False, indent=2)
            else:
                sheets_ctx = json.dumps({"aviso": f"Nenhum dado encontrado para o período solicitado (mês {mes_filtro}, ano {ano_filtro})"}, ensure_ascii=False)


        # Monta prompt final
        if sheets_ctx:
            final_prompt = f"""Dados disponíveis (amostra das planilhas):
{sheets_ctx}

Pergunta do usuário: {last_user_msg}

INSTRUÇÕES:
- Use os dados acima para responder
- Se precisar calcular totais, some os valores
- Responda em português de forma clara e objetiva
- Se não encontrar os dados, diga claramente"""
        else:
            final_prompt = f"""Pergunta do usuário: {last_user_msg}

AVISO: Nenhum dado de planilha está disponível no momento."""

        # Faz chamada ao modelo
        if st.session_state.client:
            try:
                print(f"🚀 DEBUG - Enviando prompt para API (tamanho: {len(final_prompt)} chars)")
                resp = st.session_state.client.send_message(final_prompt, conversation_history)
                print(f"✅ DEBUG - Resposta recebida da API")
                
                # Verifica se a resposta indica sucesso
                if isinstance(resp, dict):
                    if resp.get("success"):
                        content = resp.get("message", "")
                    else:
                        # Erro retornado pela API
                        error_msg = resp.get("message", "Erro desconhecido")
                        error_details = resp.get("error", "")
                        content = f"⚠️ {error_msg}"
                        
                        # Log do erro (aparece nos logs do Streamlit)
                        print(f"Erro API Abacus: {error_details}")
                else:
                    content = str(resp)
                    
            except Exception as e:
                content = f"⚠️ Falha ao consultar o modelo: {str(e)}"
                print(f"Exception em send_message: {e}")
        else:
            # Cliente não inicializado (falta API key ou erro na inicialização)
            api_key = st.session_state.get("api_key", "")
            if not api_key:
                content = "⚠️ API Key não configurada. Configure em Secrets ou arquivo .env"
            else:
                content = "⚠️ Erro ao inicializar cliente do modelo. Verifique sua API Key e conexão."

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
