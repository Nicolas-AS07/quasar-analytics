# 🚀 Guia de Deploy - ChatBot Inteligente

## 📋 Pré-requisitos para Deploy

- ✅ Código configurado para ler variáveis de ambiente (.env)
- ✅ API Key da Abacus funcionando
- ✅ Aplicação testada localmente
- ✅ Dependências no requirements.txt

## 🌐 Opções de Deploy

### 1. 🎈 Streamlit Community Cloud (RECOMENDADO)

**Vantagens:** Gratuito, integração com GitHub, específico para Streamlit

**Passos:**

1. **Suba para GitHub:**
   ```bash
   git init
   git add .
   git commit -m "ChatBot Inteligente com Gemini 2.5 Flash"
   git remote add origin https://github.com/SEU_USUARIO/chatbot-gemini
   git push -u origin main
   ```

2. **Configure no Streamlit Cloud:**
   - Acesse: https://share.streamlit.io/
   - Conecte com GitHub
   - Selecione seu repositório
   - Arquivo principal: `main.py`

3. **Secrets (Configurar em Settings → Secrets):**
   - Cole o conteúdo abaixo (edite os valores):
   ```toml
   # API do modelo
   ABACUS_API_KEY = "sua_api_key_aqui"
   MODEL_NAME = "gemini-2.5-pro"

   # Google Service Account (duas opções; use apenas uma)
   # Opção A) JSON em string
   GOOGLE_SERVICE_ACCOUNT_JSON = "{""type"": ""service_account"", ""project_id"": ""..."", ...}"
   
   # Opção B) JSON estruturado (mais seguro)
   [google_service_account]
   type = "service_account"
   project_id = "..."
   private_key_id = "..."
   private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
   client_email = "...@....iam.gserviceaccount.com"
   client_id = "..."
   token_uri = "https://oauth2.googleapis.com/token"

   # Descoberta automática de planilhas por pasta
   SHEETS_FOLDER_ID = "<id_da_pasta_no_drive>"
   # Se preferir IDs pontuais, use SHEETS_IDS (separados por vírgula)
   # SHEETS_IDS = "<id1>,<id2>"
   SHEET_RANGE = "A:Z"
   ```

   Como funciona no código:
   - Em ambiente local, se `GOOGLE_APPLICATION_CREDENTIALS` apontar para o arquivo JSON, ele será usado.
   - No Streamlit Cloud, usamos `st.secrets` para montar as credenciais via `config_utils.get_credentials()`.
   - É obrigatório compartilhar a pasta/planilhas com o email da Service Account (`client_email`).

   Observações importantes:
   - Compartilhe a pasta/planilhas do Drive com o email da Service Account (client_email) como Viewer.
   - Não suba o arquivo .env nem o JSON ao repositório público.

4. **Deploy:** Clique em "Deploy!" 🚀

---

### 2. 🚂 Railway

**Vantagens:** Rápido, suporte a Python, domínio customizado

**Passos:**

1. **Instale Railway CLI:**
   ```bash
   npm install -g @railway/cli
   ```

2. **Login e Deploy:**
   ```bash
   railway login
   railway init
   railway add
   ```

3. **Variáveis de Ambiente:**
   ```bash
   railway variables set ABACUS_API_KEY=xxxx
   railway variables set MODEL_NAME=gemini-2.5-pro
   railway variables set SHEETS_FOLDER_ID=<id_da_pasta>
   # Cole o JSON completo da service account (aspas simples para preservar quebras):
   railway variables set GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
   railway variables set SHEET_RANGE=A:Z
   ```

4. **Deploy:**
   ```bash
   railway up
   ```

---

### 3. 🟣 Heroku

**Passos:**

1. **Crie Procfile:**
   ```
   web: streamlit run main.py --server.port=$PORT --server.address=0.0.0.0
   ```

2. **Deploy:**
   ```bash
   heroku login
   heroku create seu-chatbot-gemini
   heroku config:set ABACUS_API_KEY=xxxx
   heroku config:set MODEL_NAME=gemini-2.5-pro
   heroku config:set SHEETS_FOLDER_ID=<id_da_pasta>
   heroku config:set SHEET_RANGE=A:Z
   # Cole o JSON completo em uma variável
   heroku config:set GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
   git push heroku main
   ```

---

### 4. ☁️ Google Cloud Run

**Passos:**

1. **Crie Dockerfile:**
   ```dockerfile
   FROM python:3.10-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   COPY . .
   EXPOSE 8080
   CMD streamlit run main.py --server.port=8080 --server.address=0.0.0.0
   ```

2. **Deploy:**
   ```bash
   gcloud run deploy chatbot-gemini --source . \
     --set-env-vars ABACUS_API_KEY=s2_7ec8cf43a89443bf91d9954336134bf0,MODEL_NAME=gemini-2.5-flash
   ```

## 🔒 Segurança

### ⚠️ NUNCA faça:
- ❌ Commit do arquivo .env
- ❌ Hard-code da API key no código
- ❌ API key em repositórios públicos

### ✅ SEMPRE faça:
- ✅ Use variáveis de ambiente
- ✅ Arquivo .env no .gitignore
- ✅ Configure secrets no serviço de deploy
- ✅ Teste localmente antes do deploy

## 🧪 Teste Pós-Deploy

1. **Acesse a URL do deploy**
2. **Verifique a barra lateral:**
   - 🟢 API Conectada
   - 🔑 Configurado via .env
   - ✅ Modelo: gemini-2.5-flash

3. **Teste uma conversa simples**
4. **Verifique logs se houver problemas**

## 🔧 Troubleshooting

### Problema: "API Key Não Encontrada"
**Solução:** Configure a variável de ambiente `ABACUS_API_KEY`

### Problema: "Erro na Conexão"
**Solução:** Verifique se a API key está correta e ativa

### Problema: App não inicia
**Solução:** Verifique logs e dependências no requirements.txt

## 📊 Monitoramento

### Logs importantes:
- Status da conexão com API
- Erros de autenticação
- Tempo de resposta das requisições
- Uso de tokens

### Métricas a acompanhar:
- Número de conversas
- Tempo médio de resposta
- Taxa de erro da API
- Uso de recursos

## 🎯 URL de Exemplo

Após o deploy, sua aplicação estará disponível em URLs como:
- **Streamlit Cloud:** `https://seu-usuario-chatbot-gemini-main.streamlit.app`
- **Railway:** `https://chatbot-gemini-production.up.railway.app`
- **Heroku:** `https://seu-chatbot-gemini.herokuapp.com`

**🎉 Pronto! Seu ChatBot Inteligente está online e acessível globalmente!**