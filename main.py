"""
Quasar Analytics - Assistente Analítico de Vendas
Chatbot com IA para análise de dados de vendas via Google Sheets
"""
import streamlit as st
import os
from datetime import datetime
from dotenv import load_dotenv
from abacus_client import AbacusClient
from sheets_loader import SheetsLoader
from ui_styles import render_css
import json
import time

# Carrega variáveis do arquivo .env
load_dotenv()

# Configuração da página
st.set_page_config(
    page_title="Quasar Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Aplica estilos customizados
render_css("dark")


# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def get_env_config():
    """Obtém configurações do arquivo .env."""
    api_key = os.getenv("ABACUS_API_KEY", "")
    model = os.getenv("MODEL_NAME", "gemini-2.5-pro")
    return api_key, model




def initialize_session():
    """Inicializa as variáveis de sessão."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "client" not in st.session_state:
        st.session_state.client = None
    
    if "sheets" not in st.session_state:
        st.session_state.sheets = None
    
    if "api_key" not in st.session_state:
        # Carrega automaticamente do .env
        api_key, model = get_env_config()
        st.session_state.api_key = api_key
        st.session_state.model = model
        
        # Se há uma API key no .env, conecta automaticamente
        if api_key:
            try:
                client = create_client(api_key, model)
                if client and client.validate_connection():
                    st.session_state.client = client
            except Exception:
                pass  # Falha silenciosa
    
    # Inicializa ou recarrega o loader de Sheets se configurado (a cada rerun) com TTL opcional
    prev_loader = st.session_state.get("sheets")
    loader = prev_loader or SheetsLoader()
    ttl_enabled = bool(st.session_state.get("sheets_ttl_enabled", False))
    ttl_seconds = int(st.session_state.get("sheets_ttl_seconds", 60)) if str(st.session_state.get("sheets_ttl_seconds", "")).strip() else 60
    last_loaded_ts = st.session_state.get("sheets_last_loaded_ts")
    now_ts = time.time()
    should_reload = True
    if ttl_enabled and prev_loader is not None and last_loaded_ts:
        try:
            age = now_ts - float(last_loaded_ts)
            if age < ttl_seconds:
                should_reload = False
        except Exception:
            should_reload = True

    if loader.is_configured():
        try:
            if should_reload:
                n_sheets, n_rows = loader.load_all()  # recarrega do Drive
                # Substitui somente após sucesso
                st.session_state.sheets = loader
                st.session_state.sheets_status = {"sheets": n_sheets, "rows": n_rows}
                st.session_state.sheets_last_loaded = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state.sheets_last_loaded_ts = now_ts
            else:
                # Mantém dados atuais
                st.session_state.sheets = loader
                if "sheets_status" not in st.session_state:
                    st.session_state.sheets_status = {"sheets": 0, "rows": 0}
        except Exception:
            # Mantém cache anterior se existir, evitando contexto vazio
            if prev_loader is not None:
                st.session_state.sheets = prev_loader
                # status permanece o anterior
            else:
                st.session_state.sheets = None
                st.session_state.sheets_status = {"sheets": 0, "rows": 0}
    else:
        st.session_state.sheets = None
        st.session_state.sheets_status = {"sheets": 0, "rows": 0}


def create_client(api_key: str, model: str = "gemini-2.5-pro"):
    """Cria e valida o cliente da API."""
    try:
        client = AbacusClient(api_key=api_key, model=model)
        return client
    except Exception as e:
        st.error(f"Erro ao criar cliente: {str(e)}")
        return None


def display_chat_messages():
    """Exibe todas as mensagens do chat usando componentes nativos."""
    for message in st.session_state.messages:
        role = "user" if message.get("role") == "user" else "assistant"
        with st.chat_message(role):
            st.markdown(message.get("content", ""))


# ============================================
# FUNÇÃO PRINCIPAL
# ============================================

def main():
    # Inicializar sessão (somente loader local por SHEETS_IDS)
    initialize_session()

    # Sidebar com status dos dados carregados
    with st.sidebar:
        st.markdown("### 📚 Dados carregados")
        loader = st.session_state.get("sheets")
        rows_total = 0
        worksheets_count = 0
        sheets_count = 0
        last_loaded = st.session_state.get("sheets_last_loaded")
        last_loaded_ts = st.session_state.get("sheets_last_loaded_ts")
        if loader is not None:
            try:
                status = loader.status()
                worksheets_count = status.get("worksheets_count", 0)
                sheets_count = status.get("sheets_count", 0)
                loaded_map = status.get("loaded", {})
                rows_total = sum(int(v) for v in loaded_map.values()) if loaded_map else 0
            except Exception:
                pass
        st.metric(label="Linhas carregadas", value=f"{rows_total:,}".replace(",", "."))
        st.caption(f"Planilhas: {sheets_count} · Abas: {worksheets_count}")
        if last_loaded:
            st.caption(f"Última atualização: {last_loaded}")
        st.divider()
        # Modo básico: sem Context Builder na UI
        # TTL: controles de recarga automática
        st.markdown("#### ⚙️ Recarga automática (TTL)")
        ttl_enabled_ui = st.checkbox("Habilitar recarga automática", value=st.session_state.get("sheets_ttl_enabled", False), key="sheets_ttl_enabled")
        ttl_seconds_ui = st.number_input("TTL (segundos)", min_value=10, max_value=3600, value=int(st.session_state.get("sheets_ttl_seconds", 60)), step=10, key="sheets_ttl_seconds")
        if ttl_enabled_ui and last_loaded_ts:
            try:
                eta = max(0, int(int(st.session_state.get("sheets_ttl_seconds", 60)) - (time.time() - float(last_loaded_ts))))
                st.caption(f"Próxima recarga automática em ~{eta}s")
            except Exception:
                pass
        st.divider()
        # Botão de recarga manual (útil se quiser forçar agora)
        if loader is not None and st.button("Recarregar planilhas agora"):
            try:
                n_sheets, n_rows = loader.load_all()
                st.session_state.sheets_status = {"sheets": n_sheets, "rows": n_rows}
                st.session_state.sheets_last_loaded = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state.sheets_last_loaded_ts = time.time()
                st.success("Planilhas recarregadas.")
                st.rerun()
            except Exception as e:
                st.error(f"Falha ao recarregar: {e}")
        # Prévia por aba (nome e número de linhas)
        if loader is not None:
            try:
                status = loader.status()
                loaded_map = status.get("loaded", {}) or {}
                if loaded_map:
                    st.markdown("#### 📄 Abas carregadas")
                    preview = []
                    for key, count in loaded_map.items():
                        sheet_id = key.split("::")[0] if "::" in key else "?"
                        ws_title = key.split("::")[1] if "::" in key else key
                        preview.append({"Aba": ws_title, "Planilha (ID)": sheet_id, "Linhas": int(count)})
                    # Ordena por Linhas desc
                    preview = sorted(preview, key=lambda x: x["Linhas"], reverse=True)
                    st.dataframe(preview, use_container_width=True, hide_index=True)
            except Exception:
                pass
        # Download do contexto (snapshot JSON)
        if loader is not None:
            try:
                loader_status = loader.status()
                loaded_map = loader_status.get("loaded", {}) or {}
                snapshot = {
                    "sheets_ids": loader_status.get("resolved_sheet_ids", getattr(loader, "sheet_ids", [])),
                    "worksheets": [
                        {
                            "sheet_id": key.split("::")[0] if "::" in key else key,
                            "worksheet": key.split("::")[1] if "::" in key else "",
                            "rows": int(cnt),
                            "columns": list(loader._cache.get(key).columns) if key in loader._cache else []
                        }
                        for key, cnt in loaded_map.items()
                    ],
                    "totals": {
                        "worksheets": len(loaded_map),
                        "rows": sum(int(v) for v in loaded_map.values()) if loaded_map else 0
                    },
                    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                json_bytes = json.dumps(snapshot, ensure_ascii=False, indent=2).encode("utf-8")
                st.download_button(
                    label="⬇️ Baixar contexto (JSON)",
                    data=json_bytes,
                    file_name="quasar_context_snapshot.json",
                    mime="application/json"
                )
            except Exception:
                pass
    
    # Se não há mensagens, mostra landing page estilo Grok
    if not st.session_state.messages:
        st.markdown("""
        <div class="hero-landing">
            <div class="logo-container">
                <svg class="logo-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2L2 7v10c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-10-5z" 
                          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
                    <path d="M12 8v8m-4-4h8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
                <div class="brand-name">Quasar</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Espaçamento antes dos chips
        st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)
        
        # Chips de funcionalidades (estilo Grok)
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("🔍 Análise Completa", use_container_width=True, key="chip1"):
                st.session_state.messages.append({
                    "role": "user",
                    "content": "Mostre uma análise de vendas do último mês",
                    "timestamp": datetime.now().strftime("%H:%M")
                })
                st.rerun()
        
        with col2:
            if st.button("📊 Top Produtos", use_container_width=True, key="chip2"):
                st.session_state.messages.append({
                    "role": "user", 
                    "content": "Quais foram os produtos mais vendidos?",
                    "timestamp": datetime.now().strftime("%H:%M")
                })
                st.rerun()
        
        with col3:
            if st.button("💰 Performance", use_container_width=True, key="chip3"):
                st.session_state.messages.append({
                    "role": "user",
                    "content": "Como está a performance de vendas este ano?",
                    "timestamp": datetime.now().strftime("%H:%M")
                })
                st.rerun()
        
        # Rodapé com disclaimers (estilo Grok)
        st.markdown("""
        <div class="landing-footer">
            Ao usar o Quasar, você concorda com nossos 
            <a href="#">termos</a> e 
            <a href="#">política de privacidade</a>.
        </div>
        """, unsafe_allow_html=True)
    
    # Se já há conversa, mostra chat normal
    else:
        # Container para mensagens
        st.markdown('<div class="chat-messages">', unsafe_allow_html=True)
        display_chat_messages()
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Campo nativo de chat (sempre visível no rodapé)
    user_input = st.chat_input("O que você quer saber?")
    
    if user_input:
        # Adiciona mensagem do usuário IMEDIATAMENTE
        st.session_state.messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().strftime("%H:%M")
        })
        
        # Rerun para mostrar a mensagem do usuário primeiro
        st.rerun()
    
    # Processar resposta se a última mensagem é do usuário
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        last_user_msg = st.session_state.messages[-1]["content"]
        
        # Mostra indicador de digitação
        with st.chat_message("assistant"):
            typing_placeholder = st.empty()
            typing_placeholder.markdown("_Digitando..._")
        
        # Histórico de conversa
        conversation_history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[:-1]
        ]

        # Buscar contexto: usar loader local (SHEETS_IDS)
        sheets_ctx = ""
        if st.session_state.get("sheets"):
            # Contexto base: resumo determinístico para não ficar vazio
            try:
                base = st.session_state.sheets.base_summary(top_n=3)
                if base.get("found"):
                    sheets_ctx = "Contexto (base):\n" + json.dumps(base, ensure_ascii=False)
            except Exception:
                pass
            text_lower = last_user_msg.lower()
            
            # Detecção de consultas de top produtos
            if (("top" in text_lower or "mais vendido" in text_lower or 
                 "mais vendidos" in text_lower or "top 3" in text_lower) and
                ("produto" in text_lower)):
                # Caso "todos os meses" ou "cada mês": agregação para todos os meses disponíveis
                if ("todos os meses" in text_lower) or ("cada mês" in text_lower) or ("cada mes" in text_lower) or ("por mês" in text_lower) or ("por mes" in text_lower):
                    res_all = st.session_state.sheets.top_products_by_month_all(top_n=3)
                    if res_all.get("found"):
                        extra_ctx = "Contexto (dados agregados por mês):\n" + json.dumps(res_all, ensure_ascii=False)
                        sheets_ctx = (sheets_ctx + "\n\n" + extra_ctx).strip()
                # Caso contrário, tentar mês/ano específico
                if not sheets_ctx:
                    ym = st.session_state.sheets.parse_month_year(last_user_msg)
                    if ym:
                        year, month_num = ym
                        month_names = {
                            "01": "janeiro", "02": "fevereiro", "03": "março",
                            "04": "abril", "05": "maio", "06": "junho",
                            "07": "julho", "08": "agosto", "09": "setembro",
                            "10": "outubro", "11": "novembro", "12": "dezembro"
                        }
                        month_name = month_names.get(month_num, month_num)
                        res = st.session_state.sheets.top_products(month_name, year, top_n=3)
                        if res.get("found"):
                            agg_ctx = {
                                "ano": res.get("year"),
                                "mes": res.get("month"),
                                "top_por_quantidade": res.get("by_quantity", []),
                                "top_por_receita": res.get("by_revenue", []),
                            }
                            extra_ctx = "Contexto (dados agregados):\n" + json.dumps(agg_ctx, ensure_ascii=False)
                            sheets_ctx = (sheets_ctx + "\n\n" + extra_ctx).strip()
            
            # Busca genérica se não encontrou agregação
            if not sheets_ctx:
                rows = st.session_state.sheets.search_advanced(last_user_msg, top_k=5)
                sheets_ctx = st.session_state.sheets.build_context_snippet(rows)
        
        # Monta prompt final com seção Contexto sempre presente
        if sheets_ctx:
            final_prompt = (
                "Contexto (planilhas/agregações):\n" + sheets_ctx + "\n\n" +
                "Pergunta do usuário: " + last_user_msg
            )
        else:
            # Sem contexto: envia apenas a marcação vazia para o modelo decidir como proceder
            final_prompt = (
                "Contexto (planilhas/agregações):\n[sem contexto disponível]\n\n" +
                "Pergunta do usuário: " + last_user_msg
            )

        # Envia para API
        if st.session_state.client:
            response = st.session_state.client.send_message(
                final_prompt, 
                conversation_history
            )
            content = response.get("message", "")
        else:
            content = "Não foi possível conectar ao modelo neste momento."

        # Adiciona resposta do assistente
        st.session_state.messages.append({
            "role": "assistant",
            "content": content,
            "timestamp": datetime.now().strftime("%H:%M")
        })

        # Recarrega para exibir nova mensagem
        st.rerun()
    
    # Script para rolar para baixo automaticamente
    if st.session_state.messages:
        st.markdown("""
        <script>
            window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});
        </script>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
