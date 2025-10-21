# 🤖 ChatBot Inteligente

Um chatbot moderno e elegante desenvolvido em Python com Streamlit, integrado à API da Abacus usando o modelo Route-LLM (powered by Gemini).

## ✨ Características

- **Interface Moderna**: Design bonito e responsivo com gradientes e animações
- **IA Avançada**: Integração com Route-LLM da Abacus (powered by Gemini)
- **Conversação Natural**: Entende e responde em linguagem natural
- **Histórico de Chat**: Mantém o contexto da conversa
- **Estatísticas em Tempo Real**: Acompanhe suas interações
- **API Oficial**: Usa endpoint oficial da Abacus AI
- **Fácil Configuração**: Interface intuitiva para configurar a API

## 🚀 Como Usar

### 1. Pré-requisitos

- Python 3.8 ou superior
- Chave da API Abacus: `s2_7ec8cf43a89443bf91d9954336134bf0`

### 2. Instalação

1. Clone ou baixe este projeto
2. Navegue até a pasta do projeto:
   ```bash
   cd bot
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure o arquivo .env:**
   - O arquivo `.env` já está configurado com sua API key
   - Verifique se contém: `ABACUS_API_KEY=s2_7ec8cf43a89443bf91d9954336134bf0`
   - Para deploy, configure as variáveis de ambiente no seu provedor

### 3. Executando o ChatBot

1. Execute o aplicativo:
   ```bash
   streamlit run main.py
   ```

2. O aplicativo abrirá automaticamente no seu navegador (geralmente em `http://localhost:8501`)

3. **Conexão Automática:**
   - ✅ A API key será carregada automaticamente do .env

## 🌐 Deploy no Streamlit Cloud

### Configuração dos Secrets

Para fazer deploy no Streamlit Cloud, configure os seguintes secrets na interface do Streamlit Cloud (Settings → Secrets):

```toml
# --- API KEY DO ABACUS ---
ABACUS_API_KEY = "s2_7ec8cf43a89443bf91d9954336134bf0"

# --- MODELO IA ---
MODEL_NAME = "gemini-2.5-pro"

# --- ID DA PASTA DO GOOGLE DRIVE ---
SHEETS_FOLDER_ID = "1VyxfRqAeh4ecCow3Rm4rQi_BWRD_Ss9G"

# --- INTERVALO DAS PLANILHAS ---
SHEET_RANGE = "A:Z"

# --- IDs DAS PLANILHAS (se necessário) ---
SHEETS_IDS = ""

# --- CREDENCIAIS DO GOOGLE SERVICE ACCOUNT (JSON completo) ---
# IMPORTANTE: Use este método para Streamlit Cloud!
# Substitua pelos valores do SEU arquivo service_account.json:
GOOGLE_SERVICE_ACCOUNT_CREDENTIALS = """
{
  "type": "service_account",
  "project_id": "SEU_PROJECT_ID",
  "private_key_id": "SUA_PRIVATE_KEY_ID",
  "private_key": "-----BEGIN PRIVATE KEY-----\nSUA_CHAVE_PRIVADA_COMPLETA\n-----END PRIVATE KEY-----",
  "client_email": "seu-service-account@seu-projeto.iam.gserviceaccount.com",
  "client_id": "SEU_CLIENT_ID",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/seu-service-account@seu-projeto.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}
"""
```

### ⚠️ IMPORTANTE para Streamlit Cloud:

1. **Use apenas `GOOGLE_SERVICE_ACCOUNT_CREDENTIALS`** (JSON completo), não use `[google_service_account]` no Cloud
2. **Não use** `GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH` no Cloud (caminhos de arquivo não funcionam)
3. **Substitua pelos SEUS valores** do arquivo `service_account.json`
4. **Mantenha a formatação JSON** intacta (chaves, vírgulas, quebras de linha)

### 📝 Onde obter suas credenciais:

- `SHEETS_FOLDER_ID`: ID da sua pasta no Google Drive
- `ABACUS_API_KEY`: sua chave da API Abacus
- Service Account: credenciais do seu projeto Google Cloud

Veja o arquivo `STREAMLIT_CLOUD_SETUP.md` para instruções detalhadas.

### Como configurar:

1. Acesse [share.streamlit.io](https://share.streamlit.io/)
2. Deploy seu app
3. Vá em **Settings** → **Secrets**
4. Cole a configuração acima com seus valores reais
5. **Deploy** novamente
   - ✅ Conexão com a API será estabelecida automaticamente
   - ✅ Status será mostrado na barra lateral
## 🚀 Como Usar

### 1. Pré-requisitos
1. **Configure as variáveis de ambiente:**
 - Python 3.8 ou superior
 - Chave da API Abacus: `s2_7ec8cf43a89443bf91d9954336134bf0`
- **Configure o arquivo .env (local):**
   - Copie `.env.example` para `.env` e preencha:
      - `GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH` (caminho ABSOLUTO para o JSON da Service Account, fora do repositório)
      - `SHEETS_FOLDER_ID` (ID da pasta no Google Drive com as planilhas/arquivos)
      - `SHEETS_IDS` (opcional, CSV de IDs adicionais de planilhas)
      - `SHEET_RANGE` (ex.: `A:ZZZ`)
      - `ABACUS_API_KEY` e `MODEL_NAME`
   - Para deploy, use secrets/variáveis de ambiente do provedor (não commite segredos)
   ```
   ABACUS_API_KEY=s2_7ec8cf43a89443bf91d9954336134bf0
   MODEL_NAME=gemini-2.5-flash
   ```

2. **Não inclua o arquivo .env no repositório público**
   - O arquivo `.gitignore` já está configurado
   - Use apenas variáveis de ambiente no servidor

3. **Deploy automático:**
   - O app detectará automaticamente as variáveis de ambiente
   - Conexão será estabelecida automaticamente
   - Pronto para uso em produção!

## 🎨 Interface

### Características da Interface:
- **Design Moderno**: Gradientes coloridos e elementos visuais atraentes
- **Chat Responsivo**: Bolhas de mensagem distintas para usuário e bot
- **Barra Lateral Informativa**: Status da conexão, estatísticas e controles
- **Timestamps**: Horário de cada mensagem
- **Indicadores Visuais**: Status de conexão com cores e ícones
1. **Configurar Secrets no Streamlit Cloud:**
    - Adicione no Secrets (raiz):
       - `GOOGLE_SERVICE_ACCOUNT_CREDENTIALS` com o conteúdo JSON como string (Service Account)
       - `SHEETS_FOLDER_ID`, `SHEET_RANGE`, `ABACUS_API_KEY`, `MODEL_NAME`
    - Alternativamente, você pode usar seções `[google_service_account]` e `[sheets]`.
    - Dica: Compartilhe a pasta do Drive com o e-mail `client_email` da Service Account (do secret).
- **Estatísticas**: Contador de mensagens em tempo real
- **Modelo Display**: Informações sobre o modelo em uso

├── abacus_client.py     # Cliente para API da Abacus
├── requirements.txt     # Dependências do projeto
└── README.md           # Esta documentação
- Não versione arquivos JSON de credenciais. Use `st.secrets` no Cloud e `.env` local apontando para um caminho fora do repositório.
- O diretório `Keys/` está no `.gitignore`, mas se algum JSON tiver sido commitado no histórico, considere revogar/rotacionar as credenciais e reescrever o histórico.
```

## 📋 Dependências

- **streamlit**: Framework para interface web

## 🔧 Configuração Avançada

### Personalizando o Modelo

No arquivo `abacus_client.py`, você pode modificar:

```python
def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
    # Altere o modelo padrão aqui se necessário
```

### Personalizando a Interface

O CSS customizado está no arquivo `main.py`. Você pode modificar:
- Cores dos gradientes
- Tamanhos e fontes
- Animações e efeitos
- Layout dos elementos

### Configurações da API

No método `send_message()` do `abacus_client.py`:

```python
payload = {
    "model": self.model,
    "messages": messages,
    "temperature": 0.7,      # Criatividade das respostas (0.0 - 1.0)
    "max_tokens": 1000,      # Máximo de tokens por resposta
    "stream": False
}
```

## 🎯 Funcionalidades do ChatBot

### O que o ChatBot pode fazer:
- ✅ Responder perguntas gerais
- ✅ Ajudar com problemas específicos
- ✅ Explicar conceitos complexos
- ✅ Conversar naturalmente
- ✅ Manter contexto da conversa
- ✅ Fornecer informações úteis

### Exemplos de uso:
- "Explique-me sobre inteligência artificial"
- "Como posso melhorar minha produtividade?"
- "Qual a diferença entre Python e JavaScript?"
- "Me ajude a planejar minha semana"

## 🤖 Modo Simulado

Se a API da Abacus não estiver disponível, o chatbot automaticamente ativará o **Modo Simulado**, onde:

- ✅ Continua funcionando normalmente
- 🧠 Usa inteligência própria para gerar respostas
- 📝 Responde baseado em palavras-chave e contexto
- ⚡ Funciona offline após a configuração inicial
- � Tenta reconectar com a API automaticamente

### Indicadores do Modo Simulado:
- Status mostra "🤖 Modo Simulado Ativado"
- Respostas incluem "(Simulado)" no final
- Interface permanece totalmente funcional

## �🔍 Solução de Problemas

### Problemas Comuns:

1. **Erro de Conexão com API**:
   - ✅ **Não se preocupe!** O modo simulado será ativado automaticamente
   - Verifique se a API key está correta para tentar reconectar
   - Confirme se há conexão com a internet
   - O chatbot funcionará mesmo sem a API externa

2. **Aplicativo não inicia**:
   - Confirme se todas as dependências estão instaladas
   - Verifique se está usando Python 3.8+
   - Execute: `pip install -r requirements.txt`

3. **Interface não carrega corretamente**:
   - Limpe o cache do navegador
   - Tente acessar em uma aba anônima
   - Reinicie o servidor Streamlit

### Logs de Debug:

Para ativar logs detalhados, modifique o arquivo `abacus_client.py` adicionando prints nos métodos de erro.

## 🚀 Melhorias Futuras

Possíveis adições ao projeto:
- [ ] Histórico persistente de conversas
- [ ] Diferentes modelos de IA
- [ ] Temas personalizáveis
- [ ] Exportar conversas
- [ ] Comandos especiais
- [ ] Integração com banco de dados
- [ ] Autenticação de usuários
- [ ] API própria para terceiros

## 📞 Suporte

Se você encontrar algum problema ou tiver sugestões:
1. Verifique a seção de solução de problemas
2. Revise se a API key está correta
3. Confirme se todas as dependências estão instaladas

## 🏆 Créditos

- **Interface**: Streamlit
- **IA**: Gemini 2.5 Flash via Abacus AI
- **Linguagem**: Python
- **Design**: CSS customizado com gradientes modernos

---

💡 **Dica**: Para melhor experiência, use em tela cheia e experimente diferentes tipos de perguntas para explorar toda a capacidade do chatbot!

🌟 **Divirta-se conversando com seu novo assistente inteligente!**