"""
RAG Engine para Quasar Analytics
Implementa Retrieval-Augmented Generation usando ChromaDB
"""
import os
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False
    print("⚠️ ChromaDB não instalado. Execute: pip install chromadb")

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    print("⚠️ sentence-transformers não instalado. Execute: pip install sentence-transformers")


class RAGEngine:
    """
    Motor de Retrieval-Augmented Generation para o Quasar.
    
    Responsabilidades:
    1. Indexar dados das planilhas em ChromaDB
    2. Gerar embeddings semânticos
    3. Realizar busca por similaridade
    4. Persistir índice em disco
    """
    
    def __init__(
        self,
        persist_dir: str = "./data/chroma_db",
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        """
        Inicializa o motor RAG.
        
        Args:
            persist_dir: Diretório para persistir o ChromaDB
            embedding_model: Modelo de embeddings (padrão: all-MiniLM-L6-v2, leve e eficiente)
        """
        if not HAS_CHROMA or not HAS_SENTENCE_TRANSFORMERS:
            raise ImportError(
                "Dependências faltando. Instale com:\n"
                "pip install chromadb sentence-transformers"
            )
        
        # Cria diretório se não existir
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        
        # Cliente ChromaDB com persistência
        self.client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=persist_dir,
            anonymized_telemetry=False
        ))
        
        # Modelo de embeddings
        print(f"🔄 Carregando modelo de embeddings: {embedding_model}")
        self.embedder = SentenceTransformer(embedding_model)
        print(f"✅ Modelo carregado com sucesso")
        
        # Coleção de vendas
        self.collection = self.client.get_or_create_collection(
            name="vendas",
            metadata={"description": "Dados de vendas do Quasar Analytics"}
        )
        
        self.persist_dir = persist_dir
    
    def index_dataframes(
        self,
        cache: Dict[str, pd.DataFrame],
        batch_size: int = 100
    ) -> int:
        """
        Indexa todos os DataFrames do cache em ChromaDB.
        
        Args:
            cache: Dict com chave "sheet_id::ws_title" e valor DataFrame
            batch_size: Tamanho do batch para inserção (evita estouro de memória)
            
        Returns:
            int: Número de documentos indexados
        """
        indexed = 0
        batch_docs = []
        batch_embeddings = []
        batch_metadatas = []
        batch_ids = []
        
        print(f"🔄 Indexando {len(cache)} planilhas...")
        
        for key, df in cache.items():
            if df.empty:
                continue
            
            sheet_id, ws_title = (key.split("::", 1) + [""])[:2]
            
            for idx, row in df.iterrows():
                # Texto semântico: combina colunas relevantes
                text = self._row_to_text(row, ws_title)
                
                # Metadados para filtros
                metadata = {
                    "sheet_id": sheet_id,
                    "worksheet": ws_title,
                    "row_index": int(idx)
                }
                
                # Adiciona colunas importantes aos metadados
                for col in ["Data", "Produto", "Categoria", "Região", "ID_Transação"]:
                    if col in row and pd.notna(row[col]):
                        metadata[col.lower()] = str(row[col])
                
                # ID único
                doc_id = f"{key}::{idx}"
                
                # Adiciona ao batch
                batch_docs.append(text)
                batch_metadatas.append(metadata)
                batch_ids.append(doc_id)
                
                # Gera embedding (processamento em batch é mais eficiente)
                if len(batch_docs) >= batch_size:
                    # Embeddings em batch
                    batch_embeddings = self.embedder.encode(batch_docs).tolist()
                    
                    # Adiciona ao ChromaDB
                    self.collection.add(
                        documents=batch_docs,
                        embeddings=batch_embeddings,
                        metadatas=batch_metadatas,
                        ids=batch_ids
                    )
                    
                    indexed += len(batch_docs)
                    print(f"  ✅ {indexed} documentos indexados...")
                    
                    # Limpa batch
                    batch_docs = []
                    batch_embeddings = []
                    batch_metadatas = []
                    batch_ids = []
        
        # Processa batch final
        if batch_docs:
            batch_embeddings = self.embedder.encode(batch_docs).tolist()
            self.collection.add(
                documents=batch_docs,
                embeddings=batch_embeddings,
                metadatas=batch_metadatas,
                ids=batch_ids
            )
            indexed += len(batch_docs)
        
        # Persiste no disco
        self.client.persist()
        print(f"✅ Total de {indexed} documentos indexados e salvos em {self.persist_dir}")
        
        return indexed
    
    def _row_to_text(self, row: pd.Series, ws_title: str) -> str:
        """
        Converte uma linha do DataFrame em texto semântico otimizado para busca.
        
        Args:
            row: Linha do DataFrame
            ws_title: Título da worksheet
            
        Returns:
            str: Texto formatado para embedding
        """
        parts = [f"Aba: {ws_title}"]
        
        # Prioriza colunas importantes
        priority_cols = ["Data", "Produto", "Categoria", "Região", "Quantidade", "Receita_Total"]
        
        for col in priority_cols:
            if col in row and pd.notna(row[col]) and str(row[col]).strip():
                parts.append(f"{col}: {row[col]}")
        
        # Adiciona outras colunas
        for col, val in row.items():
            if col in priority_cols or col.startswith("_"):
                continue
            if pd.notna(val) and str(val).strip():
                parts.append(f"{col}: {val}")
        
        return " | ".join(parts)
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Busca semântica por similaridade.
        
        Args:
            query: Texto da pergunta/busca
            top_k: Número de resultados a retornar
            filters: Filtros de metadados (ex: {"produto": "Laptop X1"})
            
        Returns:
            List[Dict]: Lista de resultados com texto, metadados e distância
        """
        # Gera embedding da query
        query_embedding = self.embedder.encode(query).tolist()
        
        # Busca no ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filters  # Ex: {"produto": "Laptop X1"}
        )
        
        # Formata resultados
        formatted = []
        for i in range(len(results["documents"][0])):
            formatted.append({
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if "distances" in results else None,
                "id": results["ids"][0][i]
            })
        
        return formatted
    
    def build_context(
        self,
        results: List[Dict[str, Any]],
        max_chars: int = 4000
    ) -> str:
        """
        Constrói string de contexto a partir dos resultados da busca.
        
        Args:
            results: Lista de resultados do search()
            max_chars: Limite de caracteres (para não estourar tokens)
            
        Returns:
            str: Contexto formatado para enviar ao LLM
        """
        if not results:
            return "[sem contexto disponível]"
        
        lines = []
        total_chars = 0
        
        for r in results:
            line = f"• {r['text']}"
            
            # Adiciona distância se disponível (menor = mais similar)
            if r.get("distance") is not None:
                similarity = 1 - r["distance"]  # Converte distância para similaridade
                line += f" (relevância: {similarity:.2%})"
            
            line_chars = len(line)
            
            # Verifica se cabe no limite
            if total_chars + line_chars > max_chars:
                lines.append(f"... (mais {len(results) - len(lines)} resultados omitidos por limite de tokens)")
                break
            
            lines.append(line)
            total_chars += line_chars
        
        return "\n".join(lines)
    
    def clear(self):
        """Limpa o índice (útil para reindexação completa)."""
        try:
            print("🗑️ Limpando índice ChromaDB...")
            
            # Proteção: verifica se collection existe
            if not hasattr(self, 'collection') or self.collection is None:
                print("⚠️ Collection não existe, criando nova...")
                self.collection = self.client.get_or_create_collection(
                    name="vendas",
                    metadata={"description": "Dados de vendas do Quasar Analytics"}
                )
                return
            
            # Deleta e recria collection
            self.client.delete_collection("vendas")
            self.collection = self.client.get_or_create_collection(
                name="vendas",
                metadata={"description": "Dados de vendas do Quasar Analytics"}
            )
            self.client.persist()
            print("✅ Índice limpo")
        except Exception as e:
            print(f"⚠️ Erro ao limpar índice: {e}")
            # Tenta recriar collection mesmo com erro
            try:
                self.collection = self.client.get_or_create_collection(
                    name="vendas",
                    metadata={"description": "Dados de vendas do Quasar Analytics"}
                )
            except Exception:
                pass
    
    def stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do índice."""
        count = self.collection.count()
        return {
            "total_documents": count,
            "persist_directory": self.persist_dir,
            "embedding_model": self.embedder.get_sentence_embedding_dimension(),
            "collection_name": self.collection.name
        }


# Exemplo de uso standalone
if __name__ == "__main__":
    # Teste básico
    rag = RAGEngine()
    
    # Dados de exemplo
    test_df = pd.DataFrame({
        "Data": ["2024-03-01", "2024-03-02"],
        "Produto": ["Laptop X1", "Mouse Óptico"],
        "Categoria": ["Eletrônicos", "Acessórios"],
        "Quantidade": [2, 5],
        "Receita_Total": ["10000.00", "500.00"]
    })
    
    cache = {"test::vendas": test_df}
    
    # Indexa
    indexed = rag.index_dataframes(cache)
    print(f"\n✅ Indexados {indexed} documentos")
    
    # Busca
    results = rag.search("quanto vendemos de laptops?", top_k=3)
    print(f"\n🔍 Resultados da busca:")
    for r in results:
        print(f"  - {r['text'][:100]}... (relevância: {1-r['distance']:.2%})")
    
    # Contexto
    context = rag.build_context(results)
    print(f"\n📄 Contexto gerado:\n{context}")
    
    # Stats
    stats = rag.stats()
    print(f"\n📊 Estatísticas: {stats}")
