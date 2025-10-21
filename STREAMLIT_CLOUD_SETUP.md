# 🚨 GUIA DEFINITIVO - Streamlit Cloud + Google Sheets

## Problema Identificado

O Streamlit Cloud tem dificuldades para processar JSONs grandes em secrets. Aqui estão as soluções testadas:

## ✅ SOLUÇÃO 1: JSON em linha única (RECOMENDADO)

No Streamlit Cloud (Settings → Secrets), configure assim:

```toml
ABACUS_API_KEY = "s2_7ec8cf43a89443bf91d9954336134bf0"
MODEL_NAME = "gemini-2.5-pro"
SHEETS_FOLDER_ID = "1VyxfRqAeh4ecCow3Rm4rQi_BWRD_Ss9G"
SHEET_RANGE = "A:Z"
SHEETS_IDS = ""

# JSON EM UMA LINHA ÚNICA (sem quebras de linha)
# SUBSTITUA pelos valores do SEU arquivo service_account.json
GOOGLE_SERVICE_ACCOUNT_CREDENTIALS = "{\"type\":\"service_account\",\"project_id\":\"SEU_PROJECT_ID\",\"private_key_id\":\"SUA_PRIVATE_KEY_ID\",\"private_key\":\"-----BEGIN PRIVATE KEY-----\\nSUA_CHAVE_PRIVADA_AQUI\\n-----END PRIVATE KEY-----\",\"client_email\":\"seu-service-account@seu-projeto.iam.gserviceaccount.com\",\"client_id\":\"SEU_CLIENT_ID\",\"auth_uri\":\"https://accounts.google.com/o/oauth2/auth\",\"token_uri\":\"https://oauth2.googleapis.com/token\",\"auth_provider_x509_cert_url\":\"https://www.googleapis.com/oauth2/v1/certs\",\"client_x509_cert_url\":\"https://www.googleapis.com/robot/v1/metadata/x509/seu-service-account@seu-projeto.iam.gserviceaccount.com\",\"universe_domain\":\"googleapis.com\"}"
```

## ✅ SOLUÇÃO 2: Bloco TOML (alternativa)

Se a solução 1 não funcionar, tente:

```toml
ABACUS_API_KEY = "s2_7ec8cf43a89443bf91d9954336134bf0"
MODEL_NAME = "gemini-2.5-pro"
SHEETS_FOLDER_ID = "1VyxfRqAeh4ecCow3Rm4rQi_BWRD_Ss9G"
SHEET_RANGE = "A:Z"
SHEETS_IDS = ""

[google_service_account]
type = "service_account"
project_id = "SEU_PROJECT_ID"
private_key_id = "SUA_PRIVATE_KEY_ID"
private_key = """-----BEGIN PRIVATE KEY-----
SUA_CHAVE_PRIVADA_COMPLETA_AQUI
-----END PRIVATE KEY-----"""
client_email = "seu-service-account@seu-projeto.iam.gserviceaccount.com"
client_id = "SEU_CLIENT_ID"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/seu-service-account@seu-projeto.iam.gserviceaccount.com"
universe_domain = "googleapis.com"
```

## � ERRO: "Invalid control character"

Se você receber este erro:
```
❌ JSON Error: Invalid control character at: line 1 column 158 (char 157)
```

**CAUSA**: Quebras de linha na `private_key` não estão escapadas corretamente.

**SOLUÇÃO RÁPIDA**: Use a **Solução 2** (bloco TOML) em vez de JSON string:

```toml
[google_service_account]
type = "service_account"  
project_id = "SEU_PROJECT_ID"
private_key = '''-----BEGIN PRIVATE KEY-----
SUA_CHAVE_PRIVADA_AQUI_SEM_\n
-----END PRIVATE KEY-----'''
client_email = "seu-service-account@projeto.iam.gserviceaccount.com"
# ... resto das configurações
```

**NOTA**: Use aspas triplas simples (`'''`) para a private_key no TOML!

## 🔧 Como converter JSON para linha única

1. Pegue seu arquivo `service_account.json`
2. Use um minificador JSON online (ex: jsonformatter.org/json-minify)
3. Escape as aspas duplas (\" no lugar de ")
4. Cole no campo `GOOGLE_SERVICE_ACCOUNT_CREDENTIALS`

1. Pegue seu arquivo `service_account.json`
2. Use um minificador JSON online (ex: jsonformatter.org/json-minify)
3. Escape as aspas duplas (\" no lugar de ")
4. Cole no campo `GOOGLE_SERVICE_ACCOUNT_CREDENTIALS`

## 🚨 Pontos Importantes

1. **NÃO use aspas triplas (`"""`) no Streamlit Cloud** - elas causam problemas
2. **USE o JSON em linha única** (Solução 1) - é mais confiável
3. **Escape as quebras de linha** como `\\n` 
4. **Teste depois de cada mudança** nos secrets
5. **A pasta do Drive deve estar compartilhada** com o email da sua service account

## 📝 Suas Credenciais

Você deve usar suas próprias credenciais:
- `SHEETS_FOLDER_ID`: ID da sua pasta no Google Drive
- `ABACUS_API_KEY`: sua chave da API Abacus
- Service Account: credenciais do seu projeto Google Cloud

## ✅ Como verificar se funcionou

Depois de configurar, acesse seu app e veja se aparece:
- ✅ Credenciais carregadas! Email: seu-service-account@seu-projeto.iam.gserviceaccount.com
- Lista de arquivos aparece na interface

Se ainda não funcionar, veja os logs de debug que agora aparecem na interface.