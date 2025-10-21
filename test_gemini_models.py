#!/usr/bin/env python3
"""
Teste da API da Abacus com Gemini 2.5 (Flash e Pro) diretamente
"""

import requests
import json

def test_gemini_direct():
    """Testa a API da Abacus usando Gemini 2.5 Flash diretamente."""
    
    api_key = "s2_7ec8cf43a89443bf91d9954336134bf0"
    
    url = "https://routellm.abacus.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    # Teste com diferentes modelos para ver quais estão disponíveis
    models_to_test = [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-1.5-flash", 
        "gemini-1.5-pro",
        "gpt-4o",
        "gpt-4o-mini",
        "claude-3-5-sonnet-20241022",
        "route-llm"
    ]
    
    print("🧪 TESTANDO MODELOS DISPONÍVEIS NA ABACUS\n")
    print("="*60)
    
    working_models = []
    
    for model in models_to_test:
        print(f"\n🔍 Testando modelo: {model}")
        print("-" * 40)
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": f"Olá! Responda apenas 'Funcionando com {model}' para confirmar."
                }
            ],
            "stream": False,
            "max_tokens": 50
        }
        
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
            
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                
                if "choices" in result and len(result["choices"]) > 0:
                    message = result["choices"][0]["message"]["content"]
                    actual_model = result.get("model", "desconhecido")
                    usage = result.get("usage", {})
                    
                    print(f"✅ SUCESSO!")
                    print(f"Modelo solicitado: {model}")
                    print(f"Modelo usado: {actual_model}")
                    print(f"Resposta: {message}")
                    print(f"Tokens: {usage.get('input_tokens', 0)} in, {usage.get('output_tokens', 0)} out")
                    
                    working_models.append({
                        "requested": model,
                        "actual": actual_model,
                        "message": message,
                        "usage": usage
                    })
                else:
                    print("❌ Resposta sem choices")
                    
            elif response.status_code == 400:
                error_data = response.json()
                print(f"❌ Modelo não suportado: {error_data}")
            elif response.status_code == 422:
                print("❌ Parâmetros inválidos")
            else:
                print(f"❌ Erro {response.status_code}: {response.text[:200]}")
                
        except requests.exceptions.Timeout:
            print("❌ Timeout na requisição")
        except Exception as e:
            print(f"❌ Erro: {str(e)}")
    
    print("\n" + "="*60)
    print("📊 RESUMO DOS RESULTADOS")
    print("="*60)
    
    if working_models:
        print(f"\n✅ {len(working_models)} modelo(s) funcionando:")
        for model_info in working_models:
            print(f"  • {model_info['requested']} → {model_info['actual']}")
        
        # Destacar o Gemini 2.5 Flash se estiver funcionando
        gemini_flash = next((m for m in working_models if "gemini-2.5-flash" in m['requested']), None)
        if gemini_flash:
            print(f"\n🎯 GEMINI 2.5 FLASH ENCONTRADO!")
            print(f"   Modelo usado: {gemini_flash['actual']}")
            print(f"   Resposta de teste: {gemini_flash['message']}")
            print(f"   Tokens usados: {gemini_flash['usage']}")
            return True
        else:
            print(f"\n⚠️ Gemini 2.5 Flash não encontrado, mas outros modelos funcionam.")
            return False
    else:
        print("\n❌ Nenhum modelo funcionou")
        return False

if __name__ == "__main__":
    success = test_gemini_direct()
    
    if success:
        print("\n🎉 Gemini 2.5 Flash está funcionando!")
        print("Seu chatbot usará especificamente este modelo.")
    else:
        print("\n💡 Verifique quais modelos estão disponíveis acima.")
        print("Talvez seja necessário usar um modelo diferente.")