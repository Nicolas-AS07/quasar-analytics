# ✅ Checklist de Implementação - RAG para Quasar Analytics

Use esta checklist para acompanhar o progresso da implementação.

---

## 📚 FASE 0: Preparação e Revisão (Tempo: 1 hora)

### Revisão da Documentação
- [ ] Ler `RELATORIO_FINAL.md` (10 min)
- [ ] Ler `SUMARIO_EXECUTIVO.md` (10 min)
- [ ] Revisar `ANALISE_COMPLETA.md` (20 min)
- [ ] Revisar `ARQUITETURA.md` (10 min)
- [ ] Abrir `GUIA_IMPLEMENTACAO.md` para referência (5 min)

### Backup e Segurança
- [ ] Fazer backup do projeto atual
  ```powershell
  $date = Get-Date -Format "yyyyMMdd_HHmmss"
  Compress-Archive -Path . -DestinationPath "../quasar_backup_$date.zip"
  ```
- [ ] Verificar que `.env` está no `.gitignore`
  ```powershell
  Select-String -Path .gitignore -Pattern "\.env$"
  ```
- [ ] Commitar estado atual
  ```powershell
  git add -A
  git commit -m "chore: backup antes da implementação RAG"
  git push
  ```

---

## 🔧 FASE 1: Instalação e Configuração (Tempo: 30 min)

### Instalar Dependências
- [ ] Verificar versão do Python (deve ser 3.8+)
  ```powershell
  python --version
  ```
- [ ] Atualizar `requirements.txt`
  - [ ] Adicionar `chromadb==0.4.22`
  - [ ] Adicionar `sentence-transformers==2.2.2`
- [ ] Instalar novas dependências
  ```powershell
  pip install chromadb sentence-transformers
  ```
- [ ] Verificar instalação
  ```powershell
  pip list | Select-String "chroma|sentence"
  ```

### Configurar Ambiente
- [ ] Copiar `.env.example` para `.env`
  ```powershell
  Copy-Item .env.example .env
  ```
- [ ] Editar `.env` com configurações:
  - [ ] `ENABLE_RAG=True`
  - [ ] `MAX_TOKENS=4096`
  - [ ] `TOP_K_RESULTS=15`
  - [ ] `TEMPERATURE=0.3`
  - [ ] `USE_SYSTEM_PROMPT_V2=True`
  - [ ] `ENABLE_SMART_CACHE=True`
  - [ ] `CHROMA_PERSIST_DIR=./data/chroma_db`
  - [ ] `EMBEDDING_MODEL=all-MiniLM-L6-v2`

### Testar Importações
- [ ] Testar import do ChromaDB
  ```powershell
  python -c "import chromadb; print('ChromaDB OK')"
  ```
- [ ] Testar import do Sentence Transformers
  ```powershell
  python -c "from sentence_transformers import SentenceTransformer; print('Sentence Transformers OK')"
  ```

---

## 📝 FASE 2: Atualizar Código Existente (Tempo: 2-3 horas)

### Atualizar `main.py`

#### 2.1 Adicionar Imports (linha ~1-20)
- [ ] Adicionar import `from app.prompts import get_system_prompt`
- [ ] Adicionar import `from app.cache_manager import CacheManager`
- [ ] Adicionar import condicional do RAGEngine:
  ```python
  try:
      from app.rag_engine import RAGEngine
      HAS_RAG = True
  except ImportError:
      HAS_RAG = False
  ```

#### 2.2 Criar função `_initialize_rag()` (antes de `main()`)
- [ ] Copiar código da função do `GUIA_IMPLEMENTACAO.md`
- [ ] Verificar indentação e imports
- [ ] Testar sintaxe:
  ```powershell
  python -m py_compile main.py
  ```

#### 2.3 Modificar `initialize_session()` (linha ~90)
- [ ] Localizar seção de carregamento de planilhas
- [ ] Adicionar chamada para `_initialize_rag(loader)` após `load_all()`
- [ ] Verificar condicional: `if HAS_RAG and os.getenv("ENABLE_RAG", "True").lower() == "true"`

#### 2.4 Modificar processamento de mensagens (linha ~470)
- [ ] Localizar seção que processa última mensagem do usuário
- [ ] Substituir busca tradicional por lógica RAG + fallback
- [ ] Copiar código atualizado do `GUIA_IMPLEMENTACAO.md`
- [ ] Ajustar indentação
- [ ] Verificar que fallback ainda funciona se RAG falhar

### Atualizar `app/abacus_client.py`

#### 2.5 Adicionar Import de Prompts (linha ~1-10)
- [ ] Adicionar `from app.prompts import get_system_prompt`

#### 2.6 Modificar `send_message()` (linha ~40)
- [ ] Localizar seção de system prompt
- [ ] Substituir por chamada `get_system_prompt(use_v2=True)`
- [ ] Manter lógica de override via arquivo externo
- [ ] Verificar que `.env` controla qual prompt usar

### Testar Sintaxe
- [ ] Verificar `main.py`:
  ```powershell
  python -m py_compile main.py
  ```
- [ ] Verificar `app/abacus_client.py`:
  ```powershell
  python -m py_compile app/abacus_client.py
  ```

---

## 🧪 FASE 3: Testes Iniciais (Tempo: 1-2 horas)

### Testes de Componentes Standalone

#### 3.1 Testar RAG Engine
- [ ] Executar teste standalone:
  ```powershell
  python -m app.rag_engine
  ```
- [ ] Verificar saída:
  - [ ] "✅ Modelo carregado com sucesso"
  - [ ] "✅ Indexados X documentos"
  - [ ] "🔍 Resultados da busca: ..."

#### 3.2 Testar Cache Manager
- [ ] Executar teste standalone:
  ```powershell
  python -m app.cache_manager
  ```
- [ ] Verificar saída:
  - [ ] Hash gerado
  - [ ] "Precisa reindexar? True" (primeira vez)
  - [ ] "Precisa reindexar? False" (segunda vez)

#### 3.3 Testar Prompts
- [ ] Testar import:
  ```powershell
  python -c "from app.prompts import get_system_prompt; print(get_system_prompt(use_v2=True)[:100])"
  ```
- [ ] Verificar que retorna texto do Prompt V2

### Testes de Integração

#### 3.4 Primeira Execução Completa
- [ ] Executar aplicação:
  ```powershell
  streamlit run main.py
  ```
- [ ] Monitorar logs no terminal:
  - [ ] "🔄 Carregando modelo de embeddings..."
  - [ ] "✅ Modelo carregado com sucesso"
  - [ ] "🔄 Indexando X planilhas..."
  - [ ] "✅ X documentos indexados e salvos"
  - [ ] "💾 Hash salvo: ..."

#### 3.5 Verificar Interface
- [ ] App abre no navegador (http://localhost:8501)
- [ ] Sidebar exibe status das planilhas
- [ ] Chat input aparece na parte inferior
- [ ] Sem erros visíveis na UI

#### 3.6 Verificar Persistência
- [ ] Parar aplicação (Ctrl+C)
- [ ] Reiniciar:
  ```powershell
  streamlit run main.py
  ```
- [ ] Verificar logs:
  - [ ] "✅ Cache RAG válido, pulando reindexação"
  - [ ] Não deve reindexar (rápido)

---

## 🎯 FASE 4: Testes Funcionais (Tempo: 2-3 horas)

### 4.1 Perguntas Simples
- [ ] Pergunta: "Quantas vendas tivemos em março?"
  - [ ] Resposta contém números específicos
  - [ ] Formato de tabela (se aplicável)
  - [ ] Sem erro "contexto insuficiente"

- [ ] Pergunta: "Quais produtos vendemos?"
  - [ ] Lista produtos reais das planilhas
  - [ ] Sem produtos inventados

- [ ] Pergunta: "Qual foi a receita total?"
  - [ ] Número preciso e correto
  - [ ] Formato BR (1.234,56)

### 4.2 Perguntas Complexas
- [ ] Pergunta: "Qual produto teve melhor desempenho na região Sul?"
  - [ ] Identifica região corretamente
  - [ ] Retorna produto com maior receita/quantidade
  - [ ] Inclui números de suporte

- [ ] Pergunta: "Compare vendas de laptops entre março e abril"
  - [ ] Retorna dados de ambos os meses
  - [ ] Tabela comparativa (se possível)
  - [ ] Cálculos corretos

- [ ] Pergunta: "Mostre tendência de vendas por mês"
  - [ ] Agrupa por mês
  - [ ] Formato tabular
  - [ ] Dados precisos

### 4.3 Perguntas com Sinônimos (Teste de Busca Semântica)
- [ ] Pergunta: "Quanto faturamos?" (sinônimo de "receita")
  - [ ] Entende e responde corretamente
  
- [ ] Pergunta: "Vendemos notebooks?" (sinônimo de "laptops")
  - [ ] Busca semântica encontra "Laptop X1"

- [ ] Pergunta: "Performance de vendas" (sinônimo de "desempenho")
  - [ ] Retorna métricas relevantes

### 4.4 Perguntas Ambíguas
- [ ] Pergunta: "Como estão as vendas?"
  - [ ] Pede esclarecimento (período, produto, região)
  - [ ] Ou fornece visão geral se contexto for claro

- [ ] Pergunta: "Mostre os dados"
  - [ ] Pede especificação (quais dados?)

### 4.5 Validar Precisão
- [ ] Escolher 5 transações conhecidas das planilhas
- [ ] Fazer perguntas específicas sobre elas
- [ ] Verificar que respostas batem 100% com os dados

### 4.6 Medir Performance
- [ ] Cronometrar 10 perguntas
- [ ] Tempo médio deve ser < 3s
- [ ] Se > 5s: investigar (ver Troubleshooting)

---

## 🔍 FASE 5: Validação e Ajustes (Tempo: 1-2 dias)

### 5.1 Coletar Feedback
- [ ] Testar com usuários reais (se possível)
- [ ] Documentar perguntas que falharam
- [ ] Documentar perguntas que tiveram sucesso

### 5.2 Ajustar Parâmetros
- [ ] Se respostas muito lentas (>5s):
  - [ ] Reduzir `TOP_K_RESULTS` para 10
  - [ ] Considerar modelo menor (já é MiniLM)

- [ ] Se respostas imprecisas:
  - [ ] Aumentar `TOP_K_RESULTS` para 20
  - [ ] Revisar Prompt V2 (adicionar exemplos)
  - [ ] Ajustar `TEMPERATURE` (baixar para 0.2)

- [ ] Se contexto estourando tokens:
  - [ ] Reduzir `max_chars` em `build_context()` (4000 → 3000)

### 5.3 Otimizações
- [ ] Implementar cache de embeddings de queries frequentes
- [ ] Adicionar métricas de relevância (logging)
- [ ] Configurar backups automáticos do ChromaDB

### 5.4 Documentação de Uso
- [ ] Criar lista de perguntas exemplo para usuários
- [ ] Documentar limitações conhecidas
- [ ] Criar FAQ baseado em testes

---

## 📊 FASE 6: Monitoramento e Métricas (Contínuo)

### 6.1 Configurar Logs
- [ ] Adicionar logging para:
  - [ ] Tempo de indexação
  - [ ] Tempo de busca
  - [ ] Número de resultados retornados
  - [ ] Scores de similaridade

### 6.2 Métricas de Sucesso
- [ ] Taxa de respostas corretas: Meta >85%
  - [ ] Atual: _____% (preencher após 100 perguntas teste)

- [ ] Tempo médio de resposta: Meta <3s
  - [ ] Atual: _____s (preencher após 50 perguntas)

- [ ] Taxa de reindexação: Meta <10% das sessões
  - [ ] Atual: _____% (monitorar por 1 semana)

### 6.3 Saúde do Sistema
- [ ] Monitorar tamanho do ChromaDB (não deve crescer descontroladamente)
- [ ] Verificar uso de RAM (deve ser < 2GB)
- [ ] Verificar uso de disco (< 500MB para ChromaDB)

---

## 🚀 FASE 7: Deploy (Opcional, se aplicável)

### 7.1 Preparar para Streamlit Cloud
- [ ] Verificar `requirements.txt` completo
- [ ] Confirmar que `.env` está no `.gitignore`
- [ ] Commitar código final:
  ```powershell
  git add -A
  git commit -m "feat: implementa RAG com ChromaDB e prompts V2"
  git push
  ```

### 7.2 Configurar Secrets no Streamlit Cloud
- [ ] Acessar https://share.streamlit.io/deploy
- [ ] Configurar secrets:
  - [ ] `ABACUS_API_KEY`
  - [ ] `MODEL_NAME`
  - [ ] `SHEETS_FOLDER_ID`
  - [ ] `google_service_account` (JSON completo)
  - [ ] Todas as variáveis do `.env` relevantes

### 7.3 Testar Deploy
- [ ] Deploy e aguardar build
- [ ] Verificar logs de inicialização
- [ ] Testar 5 perguntas básicas
- [ ] Verificar persistência após restart

---

## ✅ FASE 8: Conclusão e Handoff

### 8.1 Documentação Final
- [ ] Atualizar README.md com instruções de RAG
- [ ] Documentar perguntas exemplo testadas
- [ ] Criar guia para novos usuários

### 8.2 Treinamento
- [ ] Demonstrar funcionamento para stakeholders
- [ ] Explicar limitações conhecidas
- [ ] Ensinar como reindexar manualmente (se necessário)

### 8.3 Handoff
- [ ] Transferir conhecimento para mantenedor
- [ ] Documentar processos de manutenção
- [ ] Configurar alertas (se aplicável)

---

## 📋 CHECKLIST DE VERIFICAÇÃO FINAL

Antes de considerar completo, verificar:

- [ ] ✅ Todos os testes da Fase 4 passaram
- [ ] ✅ Taxa de acerto > 85%
- [ ] ✅ Tempo médio de resposta < 3s
- [ ] ✅ Persistência funciona (cache válido após restart)
- [ ] ✅ Reindexação só acontece quando dados mudam
- [ ] ✅ Sem erros no console/logs
- [ ] ✅ Documentação completa
- [ ] ✅ Backup do sistema feito
- [ ] ✅ Código commitado e pushed
- [ ] ✅ Deploy testado (se aplicável)

---

## 🎓 NOTAS E OBSERVAÇÕES

### Problemas Encontrados:
```
[Espaço para documentar problemas durante implementação]

1. 

2. 

3. 
```

### Soluções Aplicadas:
```
[Espaço para documentar soluções]

1. 

2. 

3. 
```

### Melhorias Futuras:
```
[Ideias para próximas iterações]

1. 

2. 

3. 
```

---

**Bom trabalho na implementação! 🚀**

Use `COMANDOS_RAPIDOS.md` para atalhos durante desenvolvimento.
