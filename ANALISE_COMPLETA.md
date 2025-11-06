# 📊 Análise Completa - Quasar Analytics

**Data da Análise:** 6 de novembro de 2025  
**Analista:** GitHub Copilot  
**Escopo:** Arquitetura, fluxo de contexto, persistência e viabilidade de RAG

---

## 🔍 DIAGNÓSTICO ATUAL

### ✅ Pontos Fortes

1. **Carregamento de Dados Robusto**
   - ✅ `SheetsLoader` carrega múltiplas planilhas do Google Drive
   - ✅ Suporte a pastas e IDs individuais
   - ✅ Cache em memória (`_cache: Dict[str, pd.DataFrame]`)
   - ✅ TTL configurável para recarga automática
   - ✅ Busca avançada com extração de IDs e tokens de mês/ano

2. **Agregações Determinísticas**
   - ✅ `top_products()` - Top produtos por mês específico
   - ✅ `top_products_by_month_all()` - Top produtos para todos os meses
   - ✅ `base_summary()` - Resumo estrutural das planilhas
   - ✅ Parsing de datas, números BR e detecção automática de meses

3. **Interface Streamlit Polida**
   - ✅ Design moderno com tema dark
   - ✅ Chat nativo do Streamlit
   - ✅ Sidebar com diagnósticos detalhados
   - ✅ Botão para download do snapshot JSON

4. **Integração com Abacus AI**
   - ✅ Cliente funcional para Gemini via Route-LLM
   - ✅ Configuração via `st.secrets` (Cloud) e `.env` (local)
   - ✅ Tratamento de erros HTTP
   - ✅ Timeout configurado (30s)

---

## ❌ PROBLEMAS CRÍTICOS IDENTIFICADOS

### 🚨 1. **CONTEXTO NÃO PERSISTE ENTRE SESSÕES**

**Problema:**
- O cache `_cache` do `SheetsLoader` é armazenado **apenas em memória** (`st.session_state`)
- Quando o usuário recarrega a página ou a sessão expira, **todo o contexto é perdido**
- Sem embeddings ou vector store, o bot não "aprende" ou "lembra" de conversas anteriores

**Impacto:**
- ❌ O bot não consegue responder perguntas específicas sobre dados já processados após reload
- ❌ Recarga das planilhas a cada nova sessão (lento e ineficiente)
- ❌ Sem memória de longo prazo

---

### 🚨 2. **CONTEXTO LIMITADO POR TOKENS (MAX_TOKENS=1000)**

**Problema no `abacus_client.py`:**
```python
self.max_tokens = int(os.getenv("MAX_TOKENS", "1000"))
```

**Problema no `main.py` (linha ~485):**
```python
# Busca genérica quando não há agregação
if not sheets_ctx:
    rows = loader.search_advanced(last_user_msg, top_k=5)
    sheets_ctx = loader.build_context_snippet(rows)
```

**Limitações:**
- ❌ Apenas **5 linhas** (`top_k=5`) são enviadas ao modelo
- ❌ `MAX_TOKENS=1000` é **muito baixo** para respostas elaboradas
- ❌ O contexto é **reconstruído do zero** a cada pergunta (sem cache semântico)
- ❌ Busca por **keywords simples** (não semântica)

**Exemplo:**
Se o usuário pergunta _"Qual foi o produto mais vendido em março?"_, o sistema:
1. Detecta "março" no texto
2. Usa `search_advanced()` para encontrar 5 linhas com "março"
3. Envia essas 5 linhas + pergunta para o modelo
4. **Se a resposta precisa de mais dados, o modelo não tem acesso**

---

### 🚨 3. **SEM RECUPERAÇÃO SEMÂNTICA (RAG)**

**O que falta:**
- ❌ **Embeddings** (vetorização semântica dos dados)
- ❌ **Vector Store** (Chroma, FAISS, Pinecone, Weaviate)
- ❌ **Similarity Search** (busca por similaridade, não keywords)
- ❌ **Reranking** (melhoria da relevância dos resultados)

**Consequências:**
- O bot não entende sinônimos: _"receita"_ vs _"faturamento"_ vs _"valor total"_
- Busca falha com perguntas vagas: _"Me mostre os dados de vendas"_ (muito genérico)
- Não consegue conectar informações de múltiplas linhas/abas semanticamente

---

### 🚨 4. **HISTÓRICO DE CONVERSA É VOLÁTIL**

**Problema em `main.py` (linha ~470):**
```python
conversation_history = [
    {"role": m["role"], "content": m["content"]}
    for m in st.session_state.messages[:-1]
]
```

**Limitações:**
- ❌ Histórico só existe em `st.session_state.messages` (RAM)
- ❌ Reload da página = **histórico perdido**
- ❌ Sem persistência em banco de dados ou arquivo
- ❌ Sem compressão/sumarização de conversas longas (pode estourar limite de tokens)

---

### 🚨 5. **SISTEMA PROMPT GENÉRICO E LIMITADO**

**Prompt atual em `abacus_client.py`:**
```python
system_text = (
    "Você responde em português e usa a seção 'Contexto' quando disponível.\n"
    "Siga este protocolo ao responder: 1) entenda a tarefa; 2) localize sinais/dados relevantes no Contexto; 3) calcule/extraia números; 4) redija resposta clara e objetiva com tabela/lista quando fizer sentido.\n"
    "Apenas apresente a resposta final para o usuário; não mostre raciocínio intermediário."
)
```

**Problemas:**
- ❌ Muito vago (não explica estrutura dos dados)
- ❌ Não menciona colunas disponíveis (Data, Produto, Quantidade, Receita_Total, etc.)
- ❌ Não instrui o modelo a pedir mais contexto quando necessário
- ❌ Não ensina o modelo a lidar com perguntas ambíguas

---

## 🛠️ SOLUÇÕES PROPOSTAS

### 🎯 Solução 1: **Implementar RAG com Vector Store**

#### **Tecnologias Recomendadas:**

| Opção | Prós | Contras | Custo |
|-------|------|---------|-------|
| **ChromaDB** | ✅ Simples, local, open-source<br>✅ Fácil integração com Streamlit | ⚠️ Não escala para milhões de docs | 🆓 Grátis |
| **FAISS** | ✅ Muito rápido, otimizado<br>✅ Usado pelo Meta/Facebook | ⚠️ Requer mais código manual | 🆓 Grátis |
| **Pinecone** | ✅ Cloud, escalável, gerenciado<br>✅ Alta performance | 💰 Pago após cota grátis | 💵 ~$70/mês |
| **Weaviate** | ✅ Open-source, cloud ou local<br>✅ Suporte a filtros complexos | ⚠️ Curva de aprendizado | 🆓/💵 Grátis/Pago |

#### **Recomendação: ChromaDB** (melhor custo-benefício para este projeto)

**Arquitetura proposta:**
```
1. Carregamento (SheetsLoader)
   ↓
2. Chunking (dividir dados em blocos semânticos)
   ↓
3. Embedding (converter texto → vetores com OpenAI/Gemini/local)
   ↓
4. Armazenamento (ChromaDB persist_directory)
   ↓
5. Retrieval (similarity search)
   ↓
6. Prompt Engineering (injetar resultados no contexto)
   ↓
7. Geração (Abacus/Gemini)
```

#### **Implementação:**

**Nova dependência em `requirements.txt`:**
```txt
chromadb==0.4.22
sentence-transformers==2.2.2  # Para embeddings locais
```

**Novo arquivo `app/rag_engine.py`:**
```python
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import pandas as pd
from typing import List, Dict, Any

class RAGEngine:
    """Motor de Retrieval-Augmented Generation para o Quasar."""
    
    def __init__(self, persist_dir: str = "./data/chroma_db"):
        # Cliente ChromaDB com persistência
        self.client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=persist_dir
        ))
        
        # Modelo de embeddings (pode ser substituído por OpenAI/Gemini)
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')  # Leve e eficiente
        
        # Coleção de vendas
        self.collection = self.client.get_or_create_collection(
            name="vendas",
            metadata={"description": "Dados de vendas do Quasar Analytics"}
        )
    
    def index_dataframes(self, cache: Dict[str, pd.DataFrame]) -> int:
        """Indexa todos os DataFrames do cache em ChromaDB."""
        indexed = 0
        for key, df in cache.items():
            if df.empty:
                continue
            
            sheet_id, ws_title = (key.split("::", 1) + [""])[:2]
            
            for idx, row in df.iterrows():
                # Texto semântico: combina colunas relevantes
                text = self._row_to_text(row, ws_title)
                
                # Metadados para filtros
                metadata = {
                    "sheet_id": sheet_id,
                    "worksheet": ws_title,
                    "row_index": int(idx)
                }
                
                # Adiciona colunas numéricas/categóricas aos metadados
                for col in ["Data", "Produto", "Categoria", "Região"]:
                    if col in row:
                        metadata[col.lower()] = str(row[col])
                
                # ID único
                doc_id = f"{key}::{idx}"
                
                # Embeddings
                embedding = self.embedder.encode(text).tolist()
                
                # Adiciona ao ChromaDB
                self.collection.add(
                    documents=[text],
                    embeddings=[embedding],
                    metadatas=[metadata],
                    ids=[doc_id]
                )
                indexed += 1
        
        self.client.persist()  # Salva no disco
        return indexed
    
    def _row_to_text(self, row: pd.Series, ws_title: str) -> str:
        """Converte uma linha do DataFrame em texto semântico."""
        parts = [f"Aba: {ws_title}"]
        for col, val in row.items():
            if col.startswith("_"):
                continue
            if pd.notna(val) and str(val).strip():
                parts.append(f"{col}: {val}")
        return " | ".join(parts)
    
    def search(self, query: str, top_k: int = 10, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Busca semântica por similaridade."""
        query_embedding = self.embedder.encode(query).tolist()
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filters  # Ex: {"produto": "Laptop X1"}
        )
        
        # Formata resultados
        formatted = []
        for i, doc in enumerate(results["documents"][0]):
            formatted.append({
                "text": doc,
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if "distances" in results else None
            })
        return formatted
    
    def clear(self):
        """Limpa o índice."""
        self.client.delete_collection("vendas")
        self.collection = self.client.get_or_create_collection(name="vendas")
```

---

### 🎯 Solução 2: **Persistir Histórico de Conversa**

**Opções:**

1. **SQLite Local** (simples, rápido)
   ```python
   import sqlite3
   
   def save_message(user_id, role, content):
       conn = sqlite3.connect("data/conversations.db")
       cursor = conn.cursor()
       cursor.execute(
           "INSERT INTO messages (user_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
           (user_id, role, content, datetime.now())
       )
       conn.commit()
       conn.close()
   ```

2. **JSON Files** (mais portátil)
   ```python
   import json
   from pathlib import Path
   
   def save_conversation(session_id, messages):
       Path("data/conversations").mkdir(exist_ok=True)
       with open(f"data/conversations/{session_id}.json", "w") as f:
           json.dump(messages, f, ensure_ascii=False, indent=2)
   ```

3. **Cloud Storage** (Firebase, Supabase, PostgreSQL)
   - Melhor para produção
   - Suporte a múltiplos usuários
   - Sincronização automática

---

### 🎯 Solução 3: **Melhorar Sistema Prompt**

**Novo prompt em `app/prompts.py`:**
```python
SYSTEM_PROMPT_V2 = """
# Quasar Analytics - Assistente de Vendas

Você é um assistente especializado em análise de dados de vendas. Seus dados vêm de planilhas do Google Sheets com a seguinte estrutura:

## Colunas Disponíveis:
- **Data**: Formato YYYY-MM-DD (ex: 2024-03-15)
- **ID_Transação**: Formato X-YYYYMM-NNNN (ex: T-202403-0001)
- **Produto**: Nome do produto (ex: Laptop X1, Mouse Óptico)
- **Categoria**: Eletrônicos, Acessórios, Mobiliário, Periféricos
- **Região**: Norte, Nordeste, Sul, Sudeste, Centro-Oeste
- **Quantidade**: Número de unidades vendidas
- **Preço_Unitário**: Valor em R$ (formato BR: 1.234,56)
- **Receita_Total**: Quantidade × Preço_Unitário

## Suas Responsabilidades:
1. **Analisar o contexto fornecido** na seção "Contexto (planilhas/agregações)"
2. **Calcular métricas** quando necessário (totais, médias, percentuais)
3. **Formatar respostas** com tabelas Markdown quando apropriado
4. **Ser preciso** com números (usar formato BR: 1.234,56)
5. **Indicar limitações** se o contexto for insuficiente

## Exemplos de Boas Respostas:

### Pergunta: "Quais foram os top 3 produtos em março de 2024?"
**Resposta:**
| Produto | Quantidade Vendida | Receita Total |
|---------|-------------------|---------------|
| Laptop X1 | 45 unidades | R$ 215.340,50 |
| Monitor 4K | 32 unidades | R$ 58.920,00 |
| Smartphone ProMax | 28 unidades | R$ 110.450,00 |

### Pergunta: "Como está a performance de vendas?"
**Resposta (quando contexto insuficiente):**
Para fornecer uma análise de performance, preciso saber:
- Qual período você gostaria de analisar? (mês, trimestre, ano)
- Quer comparar com algum período anterior?
- Alguma região ou produto específico?

## Protocolo de Resposta:
1. Leia a seção "Contexto" cuidadosamente
2. Se houver dados agregados, use-os prioritariamente
3. Se o contexto for insuficiente, peça mais detalhes ao usuário
4. Sempre cite números reais dos dados (nunca invente)
5. Use tabelas Markdown para comparações
6. Responda em português brasileiro claro e objetivo

Agora, analise o contexto e responda à pergunta do usuário.
"""
```

---

### 🎯 Solução 4: **Aumentar MAX_TOKENS e Otimizar Contexto**

**Mudanças em `.env.example` e configuração:**
```env
# Aumentar limite de tokens
MAX_TOKENS=4096  # Era 1000

# Permitir mais linhas no contexto
TOP_K_RESULTS=15  # Era 5

# Configurar temperatura para respostas mais precisas
TEMPERATURE=0.3  # Era 0.7 (menor = mais determinístico)
```

**Atualizar `main.py` para usar configuração:**
```python
# Linha ~485 (busca genérica)
top_k = int(os.getenv("TOP_K_RESULTS", "15"))  # Aumentado de 5 para 15
rows = loader.search_advanced(last_user_msg, top_k=top_k)
```

---

### 🎯 Solução 5: **Cache Inteligente de Embeddings**

**Problema:** Recomputar embeddings a cada sessão é custoso.

**Solução:** Persistir ChromaDB e só reindexar quando planilhas mudarem.

```python
# Novo arquivo app/cache_manager.py
import hashlib
import json
from pathlib import Path

class CacheManager:
    """Gerencia cache de embeddings baseado em hash dos dados."""
    
    def __init__(self, cache_dir: str = "./data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_data_hash(self, cache: Dict[str, pd.DataFrame]) -> str:
        """Gera hash MD5 do cache atual."""
        # Concatena shapes e colunas de todos os DataFrames
        signature = []
        for key, df in sorted(cache.items()):
            signature.append(f"{key}:{df.shape}:{list(df.columns)}")
        
        combined = "|".join(signature)
        return hashlib.md5(combined.encode()).hexdigest()
    
    def needs_reindex(self, current_hash: str) -> bool:
        """Verifica se precisa reindexar comparando hashes."""
        hash_file = self.cache_dir / "last_index_hash.txt"
        if not hash_file.exists():
            return True
        
        with open(hash_file, "r") as f:
            last_hash = f.read().strip()
        
        return current_hash != last_hash
    
    def save_hash(self, current_hash: str):
        """Salva hash do índice atual."""
        hash_file = self.cache_dir / "last_index_hash.txt"
        with open(hash_file, "w") as f:
            f.write(current_hash)
```

---

## 📋 PLANO DE IMPLEMENTAÇÃO

### Fase 1: RAG Básico (1-2 dias)
- [ ] Adicionar `chromadb` e `sentence-transformers` ao `requirements.txt`
- [ ] Criar `app/rag_engine.py`
- [ ] Integrar `RAGEngine` no `main.py`
- [ ] Testar indexação e busca semântica

### Fase 2: Persistência (1 dia)
- [ ] Criar `app/cache_manager.py`
- [ ] Implementar hash-based reindexing
- [ ] Adicionar persistência de histórico (SQLite ou JSON)

### Fase 3: Melhorias de Prompt (meio dia)
- [ ] Criar `app/prompts.py` com `SYSTEM_PROMPT_V2`
- [ ] Atualizar `abacus_client.py` para usar novo prompt
- [ ] Testar respostas com contexto enriquecido

### Fase 4: Otimizações (1 dia)
- [ ] Aumentar `MAX_TOKENS` para 4096
- [ ] Aumentar `TOP_K_RESULTS` para 15
- [ ] Implementar compressão de histórico longo (sumarização)
- [ ] Adicionar reranking (opcional, com `cohere` ou `sentence-transformers`)

### Fase 5: Testes e Validação (1 dia)
- [ ] Testes end-to-end com perguntas reais
- [ ] Medir latência (tempo de resposta)
- [ ] Validar acurácia das respostas
- [ ] Ajustar parâmetros de embedding/busca

---

## 🚀 EXEMPLO DE USO PÓS-IMPLEMENTAÇÃO

### Antes (Sistema Atual):
**Usuário:** _"Quanto vendemos de Laptop X1?"_  
**Bot:** _"Desculpe, não encontrei informações suficientes."_  
❌ **Falha:** Busca por keywords encontrou apenas 5 linhas aleatórias

### Depois (Com RAG):
**Usuário:** _"Quanto vendemos de Laptop X1?"_  
**Bot (com RAG):**
```
Com base nos dados disponíveis, as vendas de **Laptop X1** foram:

| Mês | Quantidade | Receita Total |
|-----|-----------|---------------|
| Jan/2024 | 42 unidades | R$ 201.340,50 |
| Fev/2024 | 38 unidades | R$ 182.920,00 |
| Mar/2024 | 45 unidades | R$ 215.450,00 |
| **Total** | **125 unidades** | **R$ 599.710,50** |

Posso detalhar por região ou comparar com outros produtos?
```
✅ **Sucesso:** Busca semântica encontrou TODAS as transações de Laptop X1

---

## 💰 ESTIMATIVA DE CUSTOS

### Opção 1: ChromaDB Local (Recomendado)
- **Custo:** R$ 0,00
- **Armazenamento:** ~100MB para 10k linhas
- **Performance:** 50-100ms por query
- **Limitações:** Não escala para milhões de documentos

### Opção 2: Pinecone Cloud
- **Custo:** ~R$ 350/mês (plano Starter)
- **Armazenamento:** Ilimitado (dentro do plano)
- **Performance:** 10-30ms por query
- **Vantagens:** Escalabilidade, backups automáticos

### Opção 3: FAISS + S3 (Híbrido)
- **Custo:** ~R$ 20/mês (S3 storage)
- **Performance:** 20-50ms por query
- **Complexidade:** Média/Alta

---

## 🎯 MÉTRICAS DE SUCESSO

| Métrica | Antes | Meta Pós-RAG |
|---------|-------|--------------|
| Taxa de respostas corretas | ~40% | >85% |
| Tempo de resposta | 3-5s | <3s |
| Contexto recuperado | 5 linhas | 15-30 linhas |
| Persistência entre sessões | ❌ Não | ✅ Sim |
| Busca semântica | ❌ Keywords | ✅ Embeddings |

---

## ⚠️ RISCOS E MITIGAÇÕES

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Embeddings lentos | Média | Médio | Usar modelo leve (`all-MiniLM-L6-v2`) |
| ChromaDB corrompido | Baixa | Alto | Backups automáticos diários |
| MAX_TOKENS excedido | Alta | Médio | Implementar chunking/sumarização |
| Custos de API | Média | Baixo | Monitorar usage, cache agressivo |

---

## 📚 RECURSOS E REFERÊNCIAS

- [ChromaDB Docs](https://docs.trychroma.com/)
- [Sentence Transformers](https://www.sbert.net/)
- [LangChain RAG Tutorial](https://python.langchain.com/docs/use_cases/question_answering/)
- [Streamlit Session State](https://docs.streamlit.io/library/api-reference/session-state)

---

## 📞 PRÓXIMOS PASSOS

1. **Revisar este relatório** com a equipe
2. **Aprovar tecnologias** (ChromaDB vs alternativas)
3. **Priorizar fases** de implementação
4. **Definir cronograma** e responsáveis
5. **Iniciar Fase 1** (RAG Básico)

---

**Conclusão:**  
O sistema atual funciona para consultas simples e agregações pré-definidas, mas **não escala para perguntas complexas ou dados volumosos**. A implementação de **RAG com ChromaDB** é a solução mais viável para transformar o Quasar em um verdadeiro assistente analítico inteligente.
