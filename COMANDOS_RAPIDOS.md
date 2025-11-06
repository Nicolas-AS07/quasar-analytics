# 🚀 Comandos Rápidos - Quasar Analytics RAG

Atalhos para executar tarefas comuns durante desenvolvimento e manutenção.

---

## 📦 Instalação e Setup

### Instalar dependências base
```powershell
pip install -r requirements.txt
```

### Instalar apenas RAG (se já tem outras deps)
```powershell
pip install chromadb sentence-transformers
```

### Verificar instalação
```powershell
pip list | Select-String "chroma|sentence"
```

### Criar arquivo .env
```powershell
Copy-Item .env.example .env
notepad .env
```

---

## 🔧 Desenvolvimento

### Executar aplicação
```powershell
streamlit run main.py
```

### Executar com logs detalhados
```powershell
$env:LOG_LEVEL="DEBUG"; streamlit run main.py
```

### Executar em porta específica
```powershell
streamlit run main.py --server.port 8502
```

### Limpar cache do Streamlit
```powershell
streamlit cache clear
```

---

## 🧹 Limpeza de Cache

### Limpar ChromaDB (força reindexação)
```powershell
Remove-Item -Recurse -Force .\data\chroma_db -ErrorAction SilentlyContinue
```

### Limpar cache manager
```powershell
Remove-Item -Recurse -Force .\data\cache -ErrorAction SilentlyContinue
```

### Limpar tudo (reset completo)
```powershell
Remove-Item -Recurse -Force .\data\chroma_db -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\data\cache -ErrorAction SilentlyContinue
Write-Host "✅ Cache limpo! Próxima execução será reindexada do zero."
```

---

## 🧪 Testes

### Testar RAG Engine standalone
```powershell
python -m app.rag_engine
```

### Testar Cache Manager standalone
```powershell
python -m app.cache_manager
```

### Verificar estrutura de dados
```powershell
python -c "from app.sheets_loader import SheetsLoader; loader = SheetsLoader(); loader.load_all(); print(loader.status())"
```

---

## 📊 Diagnósticos

### Ver tamanho do ChromaDB
```powershell
Get-ChildItem -Recurse .\data\chroma_db | Measure-Object -Property Length -Sum | Select-Object @{Name='SizeGB';Expression={($_.Sum / 1GB).ToString("F2")}}
```

### Ver último hash do cache
```powershell
Get-Content .\data\cache\last_index_hash.txt -ErrorAction SilentlyContinue
```

### Ver metadados do cache
```powershell
Get-Content .\data\cache\cache_metadata.json -ErrorAction SilentlyContinue | ConvertFrom-Json | ConvertTo-Json -Depth 5
```

### Ver estatísticas do ChromaDB
```powershell
python -c "from app.rag_engine import RAGEngine; rag = RAGEngine(); import json; print(json.dumps(rag.stats(), indent=2))"
```

---

## 🔍 Busca e Debug

### Testar busca RAG
```powershell
python -c "from app.rag_engine import RAGEngine; rag = RAGEngine(); results = rag.search('laptops vendidos em março', top_k=5); print(f'Encontrados: {len(results)} resultados'); [print(f\"{i+1}. {r['text'][:100]}...\") for i, r in enumerate(results)]"
```

### Contar documentos indexados
```powershell
python -c "from app.rag_engine import RAGEngine; rag = RAGEngine(); print(f'Total de documentos: {rag.stats()[\"total_documents\"]}')"
```

### Ver primeiros 5 embeddings
```powershell
python -c "from app.rag_engine import RAGEngine; rag = RAGEngine(); docs = rag.collection.peek(limit=5); [print(f'{i+1}. {d[:80]}...') for i, d in enumerate(docs['documents'])]"
```

---

## 📝 Git e Commits

### Ver status
```powershell
git status
```

### Adicionar novos arquivos
```powershell
git add app/rag_engine.py app/cache_manager.py app/prompts.py
git add ANALISE_COMPLETA.md GUIA_IMPLEMENTACAO.md SUMARIO_EXECUTIVO.md
git add .env.example requirements.txt
```

### Commit das melhorias RAG
```powershell
git commit -m "feat(rag): implementa RAG com ChromaDB

- adiciona RAGEngine com sentence-transformers
- implementa CacheManager para reindexação inteligente
- cria sistema de prompts V2 otimizado
- atualiza .env.example com novas configurações
- documenta análise completa e guia de implementação

BREAKING CHANGE: requer chromadb e sentence-transformers"
```

### Push para remoto
```powershell
git push origin main
```

---

## 🔐 Segurança

### Verificar se .env está no .gitignore
```powershell
Select-String -Path .gitignore -Pattern "\.env$"
```

### Adicionar .env ao .gitignore (se não estiver)
```powershell
Add-Content -Path .gitignore -Value "`n.env"
```

### Verificar segredos expostos
```powershell
git log --all --full-history --source -- .env
# Se aparecer algo: PROBLEMA! .env foi commitado
```

---

## 📦 Deploy

### Preparar para Streamlit Cloud
```powershell
# 1. Commitar tudo
git add -A
git commit -m "prep: prepara para deploy"
git push

# 2. Configurar secrets no Streamlit Cloud
# - Acesse: https://share.streamlit.io/deploy
# - Settings > Secrets
# - Cole conteúdo do .env (SEM a linha GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH)
# - Adicione secret google_service_account (JSON da service account)
```

### Verificar requirements.txt
```powershell
Get-Content requirements.txt
```

### Adicionar dependency ao requirements.txt
```powershell
Add-Content -Path requirements.txt -Value "nome-do-pacote==versao"
```

---

## 🐛 Troubleshooting

### Reinstalar dependências do zero
```powershell
pip uninstall -y chromadb sentence-transformers
pip install chromadb sentence-transformers
```

### Verificar versão do Python
```powershell
python --version
# Deve ser 3.8+
```

### Verificar espaço em disco
```powershell
Get-PSDrive C | Select-Object Used,Free
```

### Limpar cache do pip
```powershell
pip cache purge
```

### Forçar download de modelo de embeddings
```powershell
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

---

## 📊 Benchmarks

### Medir tempo de indexação
```powershell
$start = Get-Date; python -c "from app.rag_engine import RAGEngine; from app.sheets_loader import SheetsLoader; loader = SheetsLoader(); loader.load_all(); rag = RAGEngine(); rag.index_dataframes(loader._cache)"; $end = Get-Date; Write-Host "Tempo: $(($end-$start).TotalSeconds)s"
```

### Medir tempo de busca
```powershell
Measure-Command { python -c "from app.rag_engine import RAGEngine; rag = RAGEngine(); rag.search('laptops', top_k=10)" }
```

### Comparar tamanhos de modelos
```powershell
# MiniLM (recomendado)
python -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('all-MiniLM-L6-v2'); print(f'Dimensões: {m.get_sentence_embedding_dimension()}')"

# MPNet (melhor qualidade)
python -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('all-mpnet-base-v2'); print(f'Dimensões: {m.get_sentence_embedding_dimension()}')"
```

---

## 🎓 Atalhos Úteis

### Criar backup do ChromaDB
```powershell
$date = Get-Date -Format "yyyyMMdd_HHmmss"
Compress-Archive -Path .\data\chroma_db -DestinationPath ".\backups\chroma_backup_$date.zip"
Write-Host "✅ Backup criado: chroma_backup_$date.zip"
```

### Restaurar backup
```powershell
# Listar backups
Get-ChildItem .\backups\chroma_backup_*.zip

# Restaurar (substitua YYYYMMDD_HHMMSS pela data desejada)
Remove-Item -Recurse -Force .\data\chroma_db -ErrorAction SilentlyContinue
Expand-Archive -Path .\backups\chroma_backup_YYYYMMDD_HHMMSS.zip -DestinationPath .\data\
```

### Abrir todos os docs no VSCode
```powershell
code ANALISE_COMPLETA.md GUIA_IMPLEMENTACAO.md SUMARIO_EXECUTIVO.md
```

### Ver uso de RAM do Python
```powershell
Get-Process python | Select-Object ProcessName,@{Name='MemoryMB';Expression={[math]::Round($_.WS/1MB,2)}}
```

---

## 🔗 Links Úteis

- **ChromaDB Docs:** https://docs.trychroma.com/
- **Sentence Transformers:** https://www.sbert.net/
- **Streamlit Docs:** https://docs.streamlit.io/
- **Abacus AI:** https://abacus.ai/

---

**Copie e cole conforme necessário! 📋**
