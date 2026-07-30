from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
import numpy as np
import structlog
from ..utils.config import settings


logger = structlog.get_logger()


class EmbeddingGenerator:
    """Generate embeddings using sentence-transformers."""
    
    def __init__(
        self,
        model_name: str = None,
        dimension: int = None
    ):
        self.model_name = model_name or settings.embedding_model
        self.dimension = dimension or settings.embedding_dimension
        self._model: Optional[SentenceTransformer] = None
    
    def load_model(self):
        """Load the embedding model."""
        self._model = SentenceTransformer(self.model_name)
        logger.info("embedding_model_loaded", model=self.model_name)
    
    def generate_embedding(
        self,
        text: str,
        trace_id: Optional[str] = None
    ) -> List[float]:
        """Generate embedding for a single text."""
        if not self._model:
            self.load_model()
        
        embedding = self._model.encode(text, convert_to_numpy=True)
        
        logger.debug(
            "embedding_generated",
            text_length=len(text),
            trace_id=trace_id
        )
        
        return embedding.tolist()
    
    def generate_embeddings(
        self,
        texts: List[str],
        trace_id: Optional[str] = None
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        if not self._model:
            self.load_model()
        
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        
        logger.info(
            "embeddings_generated_batch",
            count=len(texts),
            trace_id=trace_id
        )
        
        return embeddings.tolist()
    
    def generate_entity_embedding(
        self,
        entity_type: str,
        entity_data: Dict[str, Any],
        trace_id: Optional[str] = None
    ) -> List[float]:
        """Generate embedding for an entity by combining relevant fields."""
        text_parts = []
        
        # Combine relevant fields based on entity type
        if entity_type == "funnel":
            text_parts.extend([
                entity_data.get("niche", ""),
                entity_data.get("strategy", ""),
                entity_data.get("target_audience", ""),
                str(entity_data.get("total_revenue", 0)),
                str(entity_data.get("conversion_rate", 0))
            ])
        elif entity_type == "niche":
            text_parts.extend([
                entity_data.get("name", ""),
                entity_data.get("category", ""),
                str(entity_data.get("market_size", 0)),
                entity_data.get("description", "")
            ])
        elif entity_type == "competitor":
            text_parts.extend([
                entity_data.get("name", ""),
                " ".join(entity_data.get("products", [])),
                " ".join(entity_data.get("strategies", [])),
                str(entity_data.get("market_share", 0))
            ])
        elif entity_type == "content":
            text_parts.extend([
                entity_data.get("title", ""),
                entity_data.get("type", ""),
                entity_data.get("body", ""),
                entity_data.get("platform", "")
            ])
        elif entity_type == "user":
            text_parts.extend([
                entity_data.get("lifecycle_stage", ""),
                str(entity_data.get("total_revenue", 0)),
                str(entity_data.get("funnel_count", 0))
            ])
        elif entity_type == "strategy":
            text_parts.extend([
                entity_data.get("name", ""),
                entity_data.get("type", ""),
                str(entity_data.get("success_rate", 0))
            ])
        else:
            # Generic: combine all string fields
            for value in entity_data.values():
                if isinstance(value, str):
                    text_parts.append(value)
                elif isinstance(value, (int, float)):
                    text_parts.append(str(value))
        
        text = " ".join(filter(None, text_parts))
        return self.generate_embedding(text, trace_id)
    
    def calculate_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """Calculate cosine similarity between two embeddings."""
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        cosine = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
        return float(cosine)
    
    def find_most_similar(
        self,
        query_embedding: List[float],
        candidate_embeddings: List[List[float]],
        top_k: int = 5
    ) -> List[tuple]:
        """Find the most similar embeddings to a query."""
        similarities = []
        
        for idx, candidate in enumerate(candidate_embeddings):
            similarity = self.calculate_similarity(query_embedding, candidate)
            similarities.append((idx, similarity))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
