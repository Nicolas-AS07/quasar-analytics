# 🤖 ChatBot Inteligente

Um chatbot moderno e elegante desenvolvido em Python com Streamlit, integrado à API da Abacus usando o modelo Route-LLM (powered by Gemini).

## 🧱 Novidade: Camadas de Contexto com Dados Brutos

Agora você pode incluir no prompt da IA os dados brutos das suas planilhas do Google de forma controlada:

- Camadas disponíveis: `schema` (somente colunas), `samples` (amostras por aba) e `full` (conteúdo completo, limitado por tamanho)
- Formatos: `csv` ou `jsonl`
- Limites configuráveis na barra lateral: número de linhas por aba e limite de caracteres

Como usar:

1. Abra a barra lateral do app
2. Em "Camadas de contexto (dados brutos)", marque "Incluir dados brutos no prompt"
3. Escolha a camada, o formato e os limites
4. Opcional: baixe um preview do contexto bruto pelo botão de download para inspecionar

Isso permite que a IA leia o conteúdo original das planilhas e formate a saída como você quiser, mantendo o controle sobre tamanho e performance.

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

- **Configure o arquivo .env (local):**
   - Copie `.env.example` para `.env` e preencha:
      - `GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH` (caminho ABSOLUTO para o JSON da Service Account, fora do repositório)
      - `SHEETS_FOLDER_ID` (ID da pasta no Google Drive com as planilhas/arquivos)
      - `SHEETS_IDS` (opcional, CSV de IDs adicionais de planilhas)
      - `SHEET_RANGE` (ex.: `A:ZZZ`)
      - `ABACUS_API_KEY` e `MODEL_NAME`
   - Para deploy, use secrets/variáveis de ambiente do provedor (não commite segredos)
   ```
 
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
