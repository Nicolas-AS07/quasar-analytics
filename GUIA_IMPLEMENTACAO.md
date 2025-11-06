# 🚀 Guia de Implementação - RAG para Quasar Analytics

Este guia detalha como implementar as melhorias de RAG (Retrieval-Augmented Generation) no Quasar Analytics.

---

## 📋 Pré-requisitos

Antes de começar, certifique-se de ter:
- ✅ Python 3.8+
- ✅ Git instalado
- ✅ Acesso às planilhas do Google Drive configurado
- ✅ API Key da Abacus válida

---

## 🔧 Passo 1: Instalar Dependências

### 1.1 Atualizar `requirements.txt`

Adicione as seguintes linhas ao final do arquivo `requirements.txt`:

```txt
# RAG Dependencies
chromadb==0.4.22
sentence-transformers==2.2.2
```

### 1.2 Instalar pacotes

```powershell
pip install -r requirements.txt
```

**Tempo estimado:** 2-5 minutos (dependendo da conexão)

**Atenção:** `sentence-transformers` baixará modelos (~80MB) na primeira execução.

---

## 🛠️ Passo 2: Configurar Variáveis de Ambiente

### 2.1 Criar arquivo `.env`

Copie `.env.example` para `.env`:

```powershell
Copy-Item .env.example .env
```

### 2.2 Editar `.env`

Abra `.env` e configure:

```env
# Habilitar RAG
ENABLE_RAG=True

# Aumentar tokens e resultados
MAX_TOKENS=4096
TOP_K_RESULTS=15

# Temperatura mais baixa para precisão
TEMPERATURE=0.3

# Usar prompt V2 otimizado
USE_SYSTEM_PROMPT_V2=True

# Smart cache
ENABLE_SMART_CACHE=True
```

---

## 📝 Passo 3: Atualizar `main.py`

### 3.1 Adicionar imports no início do arquivo

Localize a seção de imports (linha ~1-20) e adicione:

```python
import os
from dotenv import load_dotenv

# ... imports existentes ...

# Novos imports para RAG
from app.prompts import get_system_prompt
from app.cache_manager import CacheManager

# Import condicional do RAG Engine
try:
    from app.rag_engine import RAGEngine
    HAS_RAG = True
except ImportError:
    HAS_RAG = False
    print("⚠️ RAG Engine não disponível. Instale: pip install chromadb sentence-transformers")
```

### 3.2 Modificar função `initialize_session()`

Localize a função `initialize_session()` (linha ~90) e adicione após a seção de carregamento de planilhas:

```python
def initialize_session() -> None:
    """Inicializa variáveis de sessão e carrega planilhas com TTL."""
    # ... código existente ...
    
    # Carrega planilhas se configurado e se precisa recarregar
    if loader.is_configured():
        try:
            if should_reload:
                n_sheets, n_rows = loader.load_all()
                st.session_state.sheets = loader
                st.session_state.sheets_status = {"sheets": n_sheets, "rows": n_rows}
                st.session_state.sheets_last_loaded = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state.sheets_last_loaded_ts = time.time()
                
                # ===== NOVO: Indexar com RAG =====
                if HAS_RAG and os.getenv("ENABLE_RAG", "True").lower() == "true":
                    _initialize_rag(loader)
                # =================================
                
            else:
                st.session_state.sheets = loader
                st.session_state.setdefault("sheets_status", {"sheets": 0, "rows": 0})
        except Exception as e:
            st.session_state.sheets = st.session_state.get("sheets")
            st.session_state.setdefault("sheets_status", {"sheets": 0, "rows": 0})
            st.warning(f"Falha ao carregar planilhas (mantendo cache anterior): {e}")
    else:
        st.session_state.sheets = None
        st.session_state.sheets_status = {"sheets": 0, "rows": 0}
```

### 3.3 Adicionar função `_initialize_rag()`

Adicione esta função ANTES de `main()`:

```python
def _initialize_rag(loader: SheetsLoader) -> None:
    """Inicializa o motor RAG e indexa dados se necessário."""
    try:
        # Configurações
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")
        embedding_model = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        enable_smart_cache = os.getenv("ENABLE_SMART_CACHE", "True").lower() == "true"
        
        # Inicializa RAG Engine
        if "rag_engine" not in st.session_state:
            with st.spinner("🔄 Inicializando motor RAG..."):
                st.session_state.rag_engine = RAGEngine(
                    persist_dir=persist_dir,
                    embedding_model=embedding_model
                )
        
        rag: RAGEngine = st.session_state.rag_engine
        
        # Cache Manager para smart reindexing
        cache_mgr = CacheManager()
        current_hash = cache_mgr.get_data_hash(loader._cache)
        
        # Verifica se precisa reindexar
        if enable_smart_cache and not cache_mgr.needs_reindex(current_hash):
            print("✅ Cache RAG válido, pulando reindexação")
            return
        
        # Reindexação
        with st.spinner("🔄 Indexando dados com RAG (pode levar alguns segundos)..."):
            # Limpa índice antigo
            rag.clear()
            
            # Indexa novo
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
```

### 3.4 Modificar seção de processamento da mensagem do usuário

Localize a seção que processa a última mensagem (linha ~470) e substitua por:

```python
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

    # ===== NOVO: Busca com RAG ou fallback =====
    sheets_ctx = ""
    loader = st.session_state.get("sheets")
    rag_engine = st.session_state.get("rag_engine")
    
    # Tenta usar RAG primeiro
    if rag_engine and os.getenv("ENABLE_RAG", "True").lower() == "true":
        try:
            top_k = int(os.getenv("TOP_K_RESULTS", "15"))
            results = rag_engine.search(last_user_msg, top_k=top_k)
            sheets_ctx = rag_engine.build_context(results, max_chars=4000)
            print(f"✅ RAG: {len(results)} resultados encontrados")
        except Exception as e:
            print(f"⚠️ Erro no RAG, fallback para busca tradicional: {e}")
            rag_engine = None  # Força fallback
    
    # Fallback para busca tradicional
    if not sheets_ctx and loader:
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
                        sheets_ctx = (
                            sheets_ctx
                            + "\n\nContexto (dados agregados):\n"
                            + json.dumps(agg_ctx, ensure_ascii=False)
                        ).strip()

        # Busca genérica quando não há agregação
        if not sheets_ctx:
            top_k = int(os.getenv("TOP_K_RESULTS", "5"))
            rows = loader.search_advanced(last_user_msg, top_k=top_k)
            sheets_ctx = loader.build_context_snippet(rows)
    # ===========================================

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
```

---

## 🎨 Passo 4: Atualizar `abacus_client.py`

### 4.1 Modificar importação de prompts

No início de `app/abacus_client.py`, adicione:

```python
from app.prompts import get_system_prompt
```

### 4.2 Atualizar método `send_message()`

Localize o método `send_message()` e modifique a seção de system prompt:

```python
def send_message(self, message: str, conversation_history: Optional[list] = None) -> Dict[str, Any]:
    """Envia uma mensagem para a API e retorna a resposta."""
    try:
        messages = []
        
        # ===== NOVO: Usa prompt otimizado =====
        use_v2 = os.getenv("USE_SYSTEM_PROMPT_V2", "True").lower() == "true"
        system_text = get_system_prompt(use_v2=use_v2)
        
        # Permite override via arquivo externo
        if self.system_prompt_path and os.path.isfile(self.system_prompt_path):
            try:
                with open(self.system_prompt_path, "r", encoding="utf-8") as f:
                    system_text = f.read()
            except Exception:
                pass  # Mantém o prompt padrão
        # ======================================
        
        messages.append({"role": "system", "content": system_text})
        
        # ... resto do código permanece igual ...
```

---

## 🧪 Passo 5: Testar a Implementação

### 5.1 Executar aplicação

```powershell
streamlit run main.py
```

### 5.2 Verificar logs no terminal

Você deve ver:

```
🔄 Carregando modelo de embeddings: all-MiniLM-L6-v2
✅ Modelo carregado com sucesso
🔄 Indexando 3 planilhas...
  ✅ 100 documentos indexados...
  ✅ 200 documentos indexados...
✅ Total de 250 documentos indexados e salvos em ./data/chroma_db
💾 Hash salvo: a1b2c3d4e5f6...
✅ Cache válido (hash: a1b2c3d4e5f6...)
```

### 5.3 Testar perguntas

**Pergunta 1 (simples):**
```
Quanto vendemos de Laptop X1 em março?
```

**Resultado esperado:**
- ✅ RAG encontra TODAS as transações de Laptop X1 em março
- ✅ Resposta com tabela formatada
- ✅ Números precisos do contexto

**Pergunta 2 (complexa):**
```
Qual produto teve melhor performance na região Sul?
```

**Resultado esperado:**
- ✅ RAG busca semanticamente por "performance" e "região Sul"
- ✅ Responde com dados agregados
- ✅ Sugere análises complementares

---

## 🐛 Troubleshooting

### Erro: "ModuleNotFoundError: No module named 'chromadb'"

**Solução:**
```powershell
pip install chromadb sentence-transformers
```

### Erro: "CUDA not available" (aviso)

**Causa:** `sentence-transformers` tenta usar GPU mas não encontra.

**Solução:** Ignorar (usará CPU, um pouco mais lento mas funcional).

### RAG muito lento (>10s por query)

**Soluções:**
1. Reduzir `TOP_K_RESULTS` de 15 para 10
2. Usar modelo menor: `EMBEDDING_MODEL=all-MiniLM-L6-v2`
3. Reduzir `INDEXING_BATCH_SIZE` de 100 para 50

### Cache não invalida quando dados mudam

**Solução:**
```powershell
# Limpar cache manualmente
Remove-Item -Recurse -Force .\data\chroma_db
Remove-Item -Recurse -Force .\data\cache
```

---

## 📊 Métricas de Validação

Após implementação, valide:

| Métrica | Como Verificar | Meta |
|---------|---------------|------|
| **Indexação** | Verificar logs no terminal | <30s para 1000 linhas |
| **Busca** | Tempo de resposta do chat | <3s por query |
| **Precisão** | Testar 10 perguntas reais | >8 respostas corretas |
| **Persistência** | Recarregar página e verificar cache | Hash válido, sem reindexação |

---

## 🎯 Próximos Passos

Após implementação básica:

1. **Ajustar parâmetros** (`TOP_K_RESULTS`, `TEMPERATURE`)
2. **Testar com dados reais** e coletar feedback
3. **Implementar persistência de conversas** (Fase 2)
4. **Adicionar reranking** (opcional, para melhorar relevância)
5. **Monitorar custos** de API e uso de tokens

---

## 📞 Suporte

Problemas? Revise:
- ✅ Logs no terminal
- ✅ Arquivo `.env` configurado corretamente
- ✅ Dependências instaladas (`pip list | grep chroma`)
- ✅ Análise Completa (`ANALISE_COMPLETA.md`)

---

**Boa implementação! 🚀**
