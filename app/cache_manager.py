"""
Cache Manager para Quasar Analytics
Gerencia cache de embeddings baseado em hash dos dados
"""
import hashlib
import json
from pathlib import Path
from typing import Dict, Any
import pandas as pd


class CacheManager:
    """
    Gerencia cache inteligente de embeddings.
    
    Funcionalidades:
    1. Gera hash dos dados para detectar mudanças
    2. Evita reindexação desnecessária
    3. Salva metadados do cache
    """
    
    def __init__(self, cache_dir: str = "./data/cache"):
        """
        Inicializa o gerenciador de cache.
        
        Args:
            cache_dir: Diretório para armazenar arquivos de cache
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.hash_file = self.cache_dir / "last_index_hash.txt"
        self.metadata_file = self.cache_dir / "cache_metadata.json"
    
    def get_data_hash(self, cache: Dict[str, pd.DataFrame]) -> str:
        """
        Gera hash MD5 do cache atual.
        
        O hash é baseado em:
        - Chaves do cache (sheet_id::ws_title)
        - Shape de cada DataFrame (linhas, colunas)
        - Nomes das colunas
        
        Args:
            cache: Dict com DataFrames do SheetsLoader
            
        Returns:
            str: Hash MD5 hexadecimal
        """
        # ===== VALIDAÇÃO CRÍTICA =====
        if cache is None or not isinstance(cache, dict):
            return hashlib.md5(b"empty_cache").hexdigest()
        
        if not cache:  # Dict vazio
            return hashlib.md5(b"empty_cache").hexdigest()
        
        # Concatena informações estruturais de todos os DataFrames
        signature = []
        
        for key, df in sorted(cache.items()):
            # Proteção contra None no DataFrame
            if df is None or not isinstance(df, pd.DataFrame):
                continue
                
            # Inclui: chave, shape, colunas
            sig_parts = [
                f"key:{key}",
                f"shape:{df.shape}",
                f"columns:{','.join(df.columns)}"
            ]
            
            # Opcional: incluir hash das primeiras/últimas linhas
            # (detecta mudanças no conteúdo, não só estrutura)
            if not df.empty:
                try:
                    # Hash das primeiras 5 e últimas 5 linhas
                    head = df.head(5).to_csv(index=False)
                    tail = df.tail(5).to_csv(index=False)
                    sig_parts.append(f"content:{hashlib.md5((head+tail).encode()).hexdigest()[:8]}")
                except Exception:
                    pass
            
            signature.append("|".join(sig_parts))
        
        # Proteção contra signature vazia
        if not signature:
            return hashlib.md5(b"empty_cache").hexdigest()
        
        # Combina tudo e gera hash
        combined = "||".join(signature)
        return hashlib.md5(combined.encode()).hexdigest()
    
    def needs_reindex(self, current_hash: str) -> bool:
        """
        Verifica se precisa reindexar comparando hashes.
        
        Args:
            current_hash: Hash dos dados atuais
            
        Returns:
            bool: True se precisa reindexar, False caso contrário
        """
        if not self.hash_file.exists():
            print("📝 Primeira indexação: hash file não encontrado")
            return True
        
        try:
            with open(self.hash_file, "r") as f:
                last_hash = f.read().strip()
            
            if current_hash != last_hash:
                print(f"🔄 Dados mudaram (hash diferente): reindexação necessária")
                print(f"   Anterior: {last_hash[:12]}...")
                print(f"   Atual:    {current_hash[:12]}...")
                return True
            else:
                print(f"✅ Cache válido (hash: {current_hash[:12]}...)")
                return False
                
        except Exception as e:
            print(f"⚠️ Erro ao ler hash file: {e}")
            return True
    
    def save_hash(self, current_hash: str):
        """
        Salva hash do índice atual.
        
        Args:
            current_hash: Hash dos dados indexados
        """
        try:
            with open(self.hash_file, "w") as f:
                f.write(current_hash)
            print(f"💾 Hash salvo: {current_hash[:12]}...")
        except Exception as e:
            print(f"⚠️ Erro ao salvar hash: {e}")
    
    def save_metadata(self, metadata: Dict[str, Any]):
        """
        Salva metadados da indexação.
        
        Args:
            metadata: Dict com informações como:
                - timestamp: quando foi indexado
                - total_docs: quantos documentos
                - sheets_count: quantas planilhas
                - etc.
        """
        try:
            with open(self.metadata_file, "w") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            print(f"💾 Metadados salvos em {self.metadata_file}")
        except Exception as e:
            print(f"⚠️ Erro ao salvar metadados: {e}")
    
    def load_metadata(self) -> Dict[str, Any]:
        """
        Carrega metadados da última indexação.
        
        Returns:
            Dict com metadados ou {} se não existir
        """
        if not self.metadata_file.exists():
            return {}
        
        try:
            with open(self.metadata_file, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Erro ao ler metadados: {e}")
            return {}
    
    def clear(self):
        """Remove cache e hash files."""
        try:
            if self.hash_file.exists():
                self.hash_file.unlink()
            if self.metadata_file.exists():
                self.metadata_file.unlink()
            print("🗑️ Cache limpo")
        except Exception as e:
            print(f"⚠️ Erro ao limpar cache: {e}")


# Exemplo de uso standalone
if __name__ == "__main__":
    import time
    
    # Teste básico
    cache_mgr = CacheManager()
    
    # Dados de exemplo
    test_cache = {
        "test::vendas": pd.DataFrame({
            "Produto": ["Laptop", "Mouse"],
            "Quantidade": [10, 20]
        })
    }
    
    # Gera hash
    hash1 = cache_mgr.get_data_hash(test_cache)
    print(f"Hash 1: {hash1}")
    
    # Verifica se precisa reindexar (primeira vez)
    needs = cache_mgr.needs_reindex(hash1)
    print(f"Precisa reindexar? {needs}")
    
    # Salva hash
    cache_mgr.save_hash(hash1)
    
    # Salva metadados
    metadata = {
        "timestamp": time.time(),
        "total_docs": 2,
        "sheets_count": 1
    }
    cache_mgr.save_metadata(metadata)
    
    # Verifica novamente (agora não precisa)
    needs = cache_mgr.needs_reindex(hash1)
    print(f"Precisa reindexar? {needs}")
    
    # Muda dados
    test_cache["test::vendas"] = pd.DataFrame({
        "Produto": ["Laptop", "Mouse", "Teclado"],  # +1 linha
        "Quantidade": [10, 20, 30]
    })
    
    hash2 = cache_mgr.get_data_hash(test_cache)
    needs = cache_mgr.needs_reindex(hash2)
    print(f"Dados mudaram. Precisa reindexar? {needs}")
    
    # Carrega metadados
    loaded = cache_mgr.load_metadata()
    print(f"Metadados: {loaded}")
