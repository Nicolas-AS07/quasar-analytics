a#!/usr/bin/env python3
"""
Teste rápido da API oficial da Abacus
"""

import requests
import json

def test_abacus_official():
    """Testa a API oficial da Abacus com os parâmetros fornecidos."""
    
    api_key = "s2_7ec8cf43a89443bf91d9954336134bf0"
    
    url = "https://routellm.abacus.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    payload = {
        "model": "route-llm",
        "messages": [
            {
                "role": "user",
                "content": "Olá! Este é um teste de conexão. Responda com uma mensagem simples."
            }
        ],
        "stream": False
    }
    
    print("🧪 TESTANDO API OFICIAL DA ABACUS")
    print(f"URL: {url}")
    print(f"API Key: {api_key[:20]}...")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("\n" + "="*50 + "\n")
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print("\nResposta:")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ SUCESSO!")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            if "choices" in result and len(result["choices"]) > 0:
                message = result["choices"][0]["message"]["content"]
                print(f"\n🤖 Mensagem do Bot: {message}")
            
            return True
        else:
            print("❌ ERRO!")
            print(f"Resposta: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ ERRO NA REQUISIÇÃO: {str(e)}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ ERRO NO JSON: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ ERRO INESPERADO: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_abacus_official()
    
    if success:
        print("\n🎉 A API está funcionando! O chatbot deve funcionar perfeitamente.")
    else:
        print("\n💔 Ainda há problemas com a API. Verifique a configuração.")