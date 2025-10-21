# 🤖 Modelos Disponíveis na API Abacus

## ✅ Modelos Testados e Funcionando

### 🎯 **Gemini 2.5 Flash** (ATUAL)
- **Nome**: `gemini-2.5-flash`
- **Status**: ✅ Funcionando perfeitamente
- **Resposta de teste**: "Funcionando com gemini-2.5-flash"
- **Tokens**: 23 input, 11 output
- **Observação**: **Este é o modelo configurado no seu chatbot!**

### 🔥 **GPT-4o**
- **Nome**: `gpt-4o`
- **Modelo real**: `gpt-4o-2024-11-20`
- **Status**: ✅ Funcionando
- **Tokens**: 26 input, 8 output

### ⚡ **GPT-4o Mini**
- **Nome**: `gpt-4o-mini`
- **Status**: ✅ Funcionando
- **Tokens**: 27 input, 10 output

### 🧠 **Claude 3.5 Sonnet**
- **Nome**: `claude-3-5-sonnet-20241022`
- **Status**: ✅ Funcionando
- **Tokens**: 38 input, 19 output

### 🎲 **Route-LLM**
- **Nome**: `route-llm`
- **Modelo real**: `gemini-2.5-flash` (roteamento automático)
- **Status**: ✅ Funcionando
- **Tokens**: 19 input, 7 output

## ❌ Modelos Não Disponíveis

- `gemini-1.5-flash` - Não suportado
- `gemini-1.5-pro` - Não suportado

## 🔧 Como Trocar de Modelo

Se você quiser usar um modelo diferente no seu chatbot, edite o arquivo `main.py`:

```python
# Na função create_client, linha ~164:
client = AbacusClient(api_key=api_key, model="NOME_DO_MODELO")
```

### Opções disponíveis:
- `"gemini-2.5-flash"` (atual)
- `"gpt-4o"`
- `"gpt-4o-mini"`
- `"claude-3-5-sonnet-20241022"`
- `"route-llm"` (roteamento automático)

## 🎯 Configuração Atual

Seu chatbot está configurado para usar:
- **Modelo**: Gemini 2.5 Flash
- **API**: Abacus AI
- **URL**: https://routellm.abacus.ai/v1/chat/completions
- **Status**: ✅ Funcionando perfeitamente

## 📊 Comparação Rápida

| Modelo | Velocidade | Qualidade | Tokens (teste) |
|--------|------------|-----------|----------------|
| Gemini 2.5 Flash | 🚀🚀🚀 | 🌟🌟🌟🌟🌟 | 23→11 |
| GPT-4o | 🚀🚀 | 🌟🌟🌟🌟🌟 | 26→8 |
| GPT-4o Mini | 🚀🚀🚀 | 🌟🌟🌟🌟 | 27→10 |
| Claude 3.5 Sonnet | 🚀🚀 | 🌟🌟🌟🌟🌟 | 38→19 |
| Route-LLM | 🚀🚀🚀 | 🌟🌟🌟🌟 | 19→7 |

**🎊 Seu chatbot está usando o melhor modelo disponível!**