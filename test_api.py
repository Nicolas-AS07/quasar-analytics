#!/usr/bin/env python3
"""
Script de teste para debugar a API da Abacus
"""

import requests
import json

def test_abacus_api():
    """Testa diferentes configurações da API da Abacus"""
    
    api_key = "s2_7ec8cf43a89443bf91d9954336134bf0"
    
    # URLs para testar
    urls_to_test = [
        "https://api.abacus.ai/v1/chat/completions",
        "https://api.abacus.ai/chat/completions",
        "https://abacus.ai/api/v1/chat/completions",
        "https://chat.abacus.ai/v1/completions",
        "https://api.abacus.ai/v1/completions",
        "https://api.abacus.ai/v1/engines/gemini-2.5-flash/completions"
    ]
    
    # Headers para testar
    headers_variants = [
        {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json"
        },
        {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        },
        {
            "Authorization": f"API-Key {api_key}",
            "Content-Type": "application/json"
        }
    ]
    
    # Payloads para testar
    payloads = [
        {
            "model": "gemini-2.5-flash",
            "messages": [
                {"role": "user", "content": "Olá, teste de conexão"}
            ],
            "max_tokens": 100,
            "temperature": 0.7
        },
        {
            "prompt": "Olá, teste de conexão",
            "model": "gemini-2.5-flash",
            "max_tokens": 100,
            "temperature": 0.7
        },
        {
            "query": "Olá, teste de conexão",
            "model": "gemini-2.5-flash",
            "max_tokens": 100
        }
    ]
    
    print("=== TESTE DA API ABACUS ===\n")
    print(f"API Key: {api_key}\n")
    
    for i, url in enumerate(urls_to_test, 1):
        print(f"--- Teste {i}: {url} ---")
        
        for j, headers in enumerate(headers_variants, 1):
            print(f"  Headers variant {j}: {list(headers.keys())}")
            
            for k, payload in enumerate(payloads, 1):
                print(f"    Payload {k}: {list(payload.keys())}")
                
                try:
                    response = requests.post(
                        url,
                        headers=headers,
                        json=payload,
                        timeout=10
                    )
                    
                    print(f"    Status: {response.status_code}")
                    
                    if response.status_code == 200:
                        print("    ✅ SUCESSO!")
                        print(f"    Resposta: {response.json()}")
                        return url, headers, payload
                    elif response.status_code == 401:
                        print("    ❌ Não autorizado (API key inválida?)")
                    elif response.status_code == 404:
                        print("    ❌ Endpoint não encontrado")
                    elif response.status_code == 403:
                        print("    ❌ Acesso negado")
                    else:
                        print(f"    ❌ Erro: {response.text[:200]}")
                        
                except requests.exceptions.ConnectionError:
                    print("    ❌ Erro de conexão")
                except requests.exceptions.Timeout:
                    print("    ❌ Timeout")
                except Exception as e:
                    print(f"    ❌ Erro: {str(e)}")
                
                print()
        print()
    
    print("❌ Nenhuma configuração funcionou")
    return None, None, None

if __name__ == "__main__":
    working_url, working_headers, working_payload = test_abacus_api()
    
    if working_url:
        print(f"\n🎉 CONFIGURAÇÃO QUE FUNCIONA:")
        print(f"URL: {working_url}")
        print(f"Headers: {working_headers}")
        print(f"Payload: {working_payload}")
    else:
        print("\n❌ Não foi possível encontrar uma configuração funcional.")
        print("Possíveis problemas:")
        print("1. API key inválida ou expirada")
        print("2. URL da API incorreta")
        print("3. Formato de autenticação incorreto")
        print("4. Serviço da Abacus fora do ar")