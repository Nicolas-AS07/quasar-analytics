"""
UI Styles - Sistema de design moderno para Streamlit
Tokens de tema + CSS limpo e consistente
"""
import streamlit as st


def render_css(theme: str = "dark"):
    """
    Injeta CSS customizado baseado no tema escolhido.
    
    Args:
        theme: "light" ou "dark"
    """
    themes = {
        "light": {
            "bg_page": "#f7f9fc",
            "text_primary": "#0f172a",
            "text_secondary": "#475569",
            "surface": "#ffffff",
            "surface_alt": "#f1f5f9",
            "border": "#e2e8f0",
            "primary": "#2563eb",
            "primary_700": "#1d4ed8",
            "accent": "#06b6d4",
            "success": "#16a34a",
            "warn": "#f59e0b",
            "error": "#ef4444",
        },
        "dark": {
            "bg_page": "#0f0f0f",
            "text_primary": "#e5e7eb",
            "text_secondary": "#94a3b8",
            "surface": "#1a1a1a",
            "surface_alt": "#1f1f1f",
            "border": "#2a2a2a",
            "primary": "#3b82f6",
            "primary_700": "#2563eb",
            "accent": "#22d3ee",
            "success": "#22c55e",
            "warn": "#f59e0b",
            "error": "#ef4444",
        },
    }

    t = themes.get(theme, themes["dark"])
    
    css = f"""
    <style>
    /* ============================================
       TOKENS DE DESIGN
       ============================================ */
    :root {{
      --bg-page: {t['bg_page']};
      --text-primary: {t['text_primary']};
      --text-secondary: {t['text_secondary']};
      --surface: {t['surface']};
      --surface-alt: {t['surface_alt']};
      --border: {t['border']};
      --primary: {t['primary']};
      --primary-700: {t['primary_700']};
      --accent: {t['accent']};
      --success: {t['success']};
      --warn: {t['warn']};
      --error: {t['error']};
      --radius-sm: 10px;
      --radius-md: 14px;
      --radius-lg: 18px;
      --shadow: 0 8px 28px rgba(2,6,23,.12);
      --shadow-strong: 0 12px 48px rgba(2,6,23,.18);
    }}

    /* ============================================
       BASE & LAYOUT
       ============================================ */
    html, body {{
        background: var(--bg-page) !important;
        height: 100%;
        margin: 0;
        padding: 0;
        overflow-x: hidden;
    }}

    body, .main, .block-container {{
      background: var(--bg-page) !important;
      color: var(--text-primary) !important;
      font-family: Inter, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
      letter-spacing: 0.01rem;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }}
    
    .main {{
        padding-bottom: 160px !important;
        min-height: 100vh !important;
    }}

    .block-container {{
        max-width: 900px !important;
        width: 100% !important;
        padding: 2rem 1.5rem 1rem !important;
        margin: 0 auto !important;
        box-sizing: border-box;
    }}
    
    /* Scroll suave */
    html {{
        scroll-behavior: smooth;
    }}

    /* ============================================
       HERO & HEADER - ESTILO GROK
       ============================================ */
    .hero-landing {{
        min-height: 70vh;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        padding: 2rem 1rem;
    }}
    
    .logo-container {{
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-bottom: 3rem;
    }}
    
    .logo-icon {{
        width: 3.5rem;
        height: 3.5rem;
        color: var(--primary);
    }}
    
    .brand-name {{
        font-size: 3.5rem;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: -0.02em;
    }}
    
    .landing-footer {{
        position: fixed;
        bottom: 1.5rem;
        left: 50%;
        transform: translateX(-50%);
        font-size: 0.85rem;
        color: var(--text-secondary);
        text-align: center;
    }}
    
    .landing-footer a {{
        color: var(--text-secondary);
        text-decoration: none;
        border-bottom: 1px solid transparent;
        transition: border-color 0.2s;
    }}
    
    .landing-footer a:hover {{
        border-bottom-color: var(--text-secondary);
    }}

    /* ============================================
       CHAT - COMPONENTES NATIVOS
       ============================================ */
    /* Container de mensagens */
    .chat-messages {{
        margin-bottom: 2rem;
        padding-bottom: 1rem;
    }}
    
    /* Mensagens do chat - estilo polido */
    [data-testid="stChatMessage"] {{
        background: transparent !important;
        color: var(--text-primary) !important;
        padding: 1.25rem 1rem !important;
        margin-bottom: 1.5rem !important;
        border-radius: 0 !important;
        border: none !important;
        display: flex !important;
        gap: 1rem !important;
    }}
    
    [data-testid="stChatMessage"] p,
    [data-testid="stChatMessage"] span,
    [data-testid="stChatMessage"] div {{
        color: var(--text-primary) !important;
        line-height: 1.6 !important;
    }}

    /* Avatar do usuário - círculo vermelho */
    [data-testid="stChatMessage"] .stChatMessageAvatar {{
        width: 36px !important;
        height: 36px !important;
        border-radius: 50% !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 1.1rem !important;
        flex-shrink: 0 !important;
    }}
    
    /* Avatar do usuário */
    [data-testid="stChatMessage"]:has([aria-label*="user"]) .stChatMessageAvatar,
    [data-testid="stChatMessage"][data-testid*="user"] .stChatMessageAvatar {{
        background: linear-gradient(135deg, #ef4444, #dc2626) !important;
    }}

    /* Avatar do assistente - círculo laranja */
    [data-testid="stChatMessage"]:has([aria-label*="assistant"]) .stChatMessageAvatar,
    [data-testid="stChatMessage"][data-testid*="assistant"] .stChatMessageAvatar {{
        background: linear-gradient(135deg, #f59e0b, #d97706) !important;
    }}
    
    /* Conteúdo da mensagem */
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {{
        max-width: none !important;
        padding: 0 !important;
    }}
    
    /* Indicador de digitação */
    [data-testid="stChatMessage"] em {{
        color: var(--text-secondary) !important;
        font-style: italic !important;
        animation: pulse 1.5s ease-in-out infinite;
    }}
    
    @keyframes pulse {{
        0%, 100% {{ opacity: 0.5; }}
        50% {{ opacity: 1; }}
    }}
    
    /* Tabelas dentro das mensagens */
    [data-testid="stChatMessage"] table {{
        border-collapse: collapse !important;
        width: 100% !important;
        margin: 1rem 0 !important;
        font-size: 0.9rem !important;
    }}
    
    [data-testid="stChatMessage"] table th {{
        background: rgba(255, 255, 255, 0.05) !important;
        padding: 0.75rem 1rem !important;
        text-align: left !important;
        font-weight: 600 !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important;
    }}
    
    [data-testid="stChatMessage"] table td {{
        padding: 0.75rem 1rem !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05) !important;
    }}

    /* ============================================
       CHAT INPUT - FIXO NA PÁGINA (sem box de rodapé)
       ============================================ */
    /* Deixa o rodapé do Streamlit totalmente transparente e neutro */
    [data-testid="stBottomBar"],
    [data-testid="stBottomBlockContainer"],
    [data-testid="stBottomBar"] > div,
    [data-testid="stBottomBlockContainer"] > div {{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        position: static !important;
        inset: auto !important;
        border-radius: 0 !important;
        overflow: visible !important;
    }}
    
    .stVerticalBlock,
    .stElementContainer {{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }}

    /* Input integrado e FIXO no viewport */
    [data-testid="stChatInput"],
    [data-testid="stChatMessageInput"] {{
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
        margin: 0 !important;
        box-shadow: none !important;
        position: fixed !important;
        bottom: 18px !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        width: min(900px, 92vw) !important;
        z-index: 200 !important;
    }}

    /* Container interno do input */
    [data-testid="stChatInput"] > div,
    [data-testid="stChatMessageInput"] > div {{
        background: transparent !important;
        border: none !important;
        max-width: 700px !important;
        margin: 0 auto !important;
        position: relative !important;
        overflow: visible !important;
    }}

    /* Campo de texto - fundo polido */
    [data-testid="stChatInputTextArea"] {{
        background: rgba(30, 30, 30, 0.95) !important;
        color: var(--text-primary) !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 28px !important;
        padding: 1rem 3.5rem 1rem 1.5rem !important;
        font-size: 0.95rem !important;
        min-height: 56px !important;
        backdrop-filter: blur(12px) !important;
        resize: none !important;
    }}
    
    [data-testid="stChatInputTextArea"]:focus {{
        border-color: rgba(255, 255, 255, 0.25) !important;
        box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.1) !important;
        outline: none !important;
    }}

    [data-testid="stChatInputTextArea"]::placeholder {{
        color: rgba(255, 255, 255, 0.4) !important;
        opacity: 1 !important;
    }}

    /* Botão de enviar - alinhado corretamente */
    [data-testid="stChatInputSubmitButton"] {{
        background: var(--primary) !important;
        color: #fff !important;
        border: none !important;
        border-radius: 50% !important;
        width: 40px !important;
        height: 40px !important;
        min-width: 40px !important;
        min-height: 40px !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        position: absolute !important;
        right: 8px !important;
        top: 50% !important;
        transform: translateY(-50%) !important;
        transition: all 0.15s ease !important;
        flex-shrink: 0 !important;
    }}
    
    [data-testid="stChatInputSubmitButton"]:hover:not(:disabled) {{
        background: var(--primary-700) !important;
        transform: translateY(-50%) scale(1.05) !important;
    }}
    
    [data-testid="stChatInputSubmitButton"]:disabled {{
        opacity: 0.5 !important;
        cursor: not-allowed !important;
        transform: translateY(-50%) !important;
    }}
    
    [data-testid="stChatInputSubmitButton"] svg {{
        width: 20px !important;
        height: 20px !important;
        flex-shrink: 0 !important;
    }}

    /* Zera qualquer decoração/pseudo-elemento do BaseWeb que cria "arcos" */
    [data-baseweb="base-input"],
    [data-baseweb="textarea"] {{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
        border-radius: 28px !important;
        overflow: visible !important;
    }}
    [data-baseweb="base-input"]::before,
    [data-baseweb="base-input"]::after,
    [data-baseweb="textarea"]::before,
    [data-baseweb="textarea"]::after {{
        content: none !important;
        display: none !important;
    }}
    
    /* Evita bordas/sombras residuais em wrappers do Emotion */
    [data-testid="stChatInput"] [class*="st-emotion-cache"] {{
        border: none !important;
        box-shadow: none !important;
        background: transparent !important;
    }}
    
    /* Mantém o visual do input durante carregamento */
    [data-testid="stChatInput"] form {{
        position: relative !important;
    }}
    
    [data-testid="stChatInput"] [data-baseweb="textarea"] {{
        position: relative !important;
    }}

    /* ============================================
       COMPONENTES STREAMLIT
       ============================================ */
    /* Botões - estilo chip/tag minimalista */
    .stButton > button {{
        background: rgba(255, 255, 255, 0.05) !important;
        color: var(--text-primary) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 999px !important;
        padding: 0.8rem 1.5rem !important;
        font-weight: 500 !important;
        font-size: 0.9rem !important;
        box-shadow: none !important;
        transition: all 0.15s ease !important;
        white-space: nowrap !important;
    }}
    
    .stButton > button:hover {{
        background: rgba(255, 255, 255, 0.1) !important;
        border-color: rgba(255, 255, 255, 0.25) !important;
        transform: translateY(-2px);
    }}
    
    .stButton > button:active {{
        transform: translateY(0);
    }}
    
    /* Container de colunas para chips */
    [data-testid="column"] {{
        padding: 0 0.5rem !important;
    }}

    /* Text Input & Textarea */
    .stTextInput > div > div > input,
    .stTextArea textarea {{
        border-radius: 12px !important;
        border: 1px solid var(--border) !important;
        padding: 0.8rem 1rem !important;
        font-size: 1rem !important;
        background: var(--surface) !important;
        color: var(--text-primary) !important;
        transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
    }}
    
    .stTextInput > div > div > input::placeholder,
    .stTextArea textarea::placeholder {{
        color: var(--text-secondary);
        opacity: 0.85;
    }}
    
    .stTextInput > div > div > input:focus,
    .stTextArea textarea:focus {{
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 3px rgba(37,99,235,.18) !important;
        outline: none !important;
    }}

    /* DataFrames & Tabelas */
    .stDataFrame, .stTable {{
        border-radius: var(--radius-sm);
        overflow: hidden;
        border: 1px solid var(--border);
        background: var(--surface);
    }}

    /* Alertas */
    .stSuccess {{
        background: {'#ecfdf5' if theme=='light' else '#052e16'} !important;
        border-left: 4px solid var(--success) !important;
        border-radius: var(--radius-sm) !important;
    }}
    
    .stWarning {{
        background: {'#fffbeb' if theme=='light' else '#3b2f00'} !important;
        border-left: 4px solid var(--warn) !important;
        border-radius: var(--radius-sm) !important;
    }}
    
    .stError {{
        background: {'#fef2f2' if theme=='light' else '#3f1d1d'} !important;
        border-left: 4px solid var(--error) !important;
        border-radius: var(--radius-sm) !important;
    }}

    /* ============================================
       CHROME DO STREAMLIT
       ============================================ */
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="block-container"],
    [data-testid="stMain"],
    [data-testid="stHeader"],
    [data-testid="stToolbar"] {{
        background: var(--bg-page) !important;
        box-shadow: none !important;
        border: none !important;
    }}

    /* Esconde menu e rodapé */
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}

    /* ============================================
       SCROLLBAR
       ============================================ */
    ::-webkit-scrollbar {{
        height: 10px;
        width: 10px;
    }}
    
    ::-webkit-scrollbar-track {{
        background: {'rgba(2,6,23,.06)' if theme=='light' else 'rgba(255,255,255,.04)'};
    }}
    
    ::-webkit-scrollbar-thumb {{
        background: rgba(0,0,0,.18);
        border-radius: 999px;
        border: 2px solid transparent;
        background-clip: padding-box;
    }}
    
    ::-webkit-scrollbar-thumb:hover {{
        background: rgba(0,0,0,.28);
    }}

    /* ============================================
       ACESSIBILIDADE
       ============================================ */
    :focus-visible {{
        outline: 3px solid rgba(37,99,235,.35);
        outline-offset: 2px;
        border-radius: 8px;
    }}
    
    @media (prefers-reduced-motion: reduce) {{
        * {{
            transition: none !important;
            animation: none !important;
        }}
    }}
    </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)
