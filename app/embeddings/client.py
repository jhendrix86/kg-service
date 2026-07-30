from qdrant_client import QdrantClient as QdrantSyncClient
from qdrant_client.async_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from typing import Optional, Dict, Any, List
import structlog
from ..utils.config import settings


logger = structlog.get_logger()


class QdrantClient:
    """Qdrant vector database client for embeddings."""
    
    COLLECTIONS = {
        "users": "kg_users",
        "funnels": "kg_funnels",
        "niches": "kg_niches",
        "competitors": "kg_competitors",
        "content": "kg_content",
        "strategies": "kg_strategies",
    }
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        api_key: str = None,
        collection_prefix: str = None
    ):
        self.host = host or settings.qdrant_host
        self.port = port or settings.qdrant_port
        self.api_key = api_key or settings.qdrant_api_key
        self.collection_prefix = collection_prefix or settings.qdrant_collection_prefix
        self._client: Optional[AsyncQdrantClient] = None
        self._dimension = settings.embedding_dimension
    
    async def connect(self):
        """Connect to Qdrant."""
        url = f"http://{self.host}:{self.port}"
        self._client = AsyncQdrantClient(
            url=url,
            api_key=self.api_key
        )
        
        # Test connection
        collections = await self._client.get_collections()
        logger.info("qdrant_connected", url=url, collections=len(collections.collections))
    
    async def disconnect(self):
        """Disconnect from Qdrant."""
        if self._client:
            await self._client.close()
            logger.info("qdrant_disconnected")
    
    async def initialize_collections(self):
        """Initialize all collections."""
        for name, collection_name in self.COLLECTIONS.items():
            await self._create_collection_if_not_exists(collection_name)
        
        logger.info("qdrant_collections_initialized")
    
    async def _create_collection_if_not_exists(self, collection_name: str):
        """Create a collection if it doesn't exist."""
        collections = await self._client.get_collections()
        existing = [c.name for c in collections.collections]
        
        if collection_name not in existing:
            await self._client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=self._dimension,
                    distance=Distance.COSINE
                )
            )
            logger.info("qdrant_collection_created", collection=collection_name)
    
    async def upsert_embedding(
        self,
        collection_type: str,
        point_id: str,
        vector: List[float],
        metadata: Dict[str, Any],
        trace_id: Optional[str] = None
    ):
        """Upsert an embedding."""
        collection_name = self.COLLECTIONS.get(collection_type)
        if not collection_name:
            raise ValueError(f"Unknown collection type: {collection_type}")
        
        point = PointStruct(
            id=point_id,
            vector=vector,
            payload={
                **metadata,
                "timestamp": metadata.get("timestamp", None),
                "version": metadata.get("version", "1.0.0")
            }
        )
        
        await self._client.upsert(
            collection_name=collection_name,
            points=[point]
        )
        
        logger.info(
            "embedding_upserted",
            collection=collection_name,
            point_id=point_id,
            trace_id=trace_id
        )
    
    async def search_similar(
        self,
        collection_type: str,
        query_vector: List[float],
        limit: int = 10,
        filter_conditions: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar embeddings."""
        collection_name = self.COLLECTIONS.get(collection_type)
        if not collection_name:
            raise ValueError(f"Unknown collection type: {collection_type}")
        
        query_filter = None
        if filter_conditions:
            conditions = [
                FieldCondition(
                    key=key,
                    match=MatchValue(value=value)
                )
                for key, value in filter_conditions.items()
            ]
            query_filter = Filter(must=conditions)
        
        results = await self._client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=query_filter
        )
        
        logger.info(
            "embedding_search",
            collection=collection_name,
            results=len(results),
            trace_id=trace_id
        )
        
        return [
            {
                "id": result.id,
                "score": result.score,
                "payload": result.payload
            }
            for result in results
        ]
    
    async def get_embedding(
        self,
        collection_type: str,
        point_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get an embedding by ID."""
        collection_name = self.COLLECTIONS.get(collection_type)
        if not collection_name:
            raise ValueError(f"Unknown collection type: {collection_type}")
        
        try:
            result = await self._client.retrieve(
                collection_name=collection_name,
                ids=[point_id]
            )
            
            if result:
                return {
                    "id": result[0].id,
                    "vector": result[0].vector,
                    "payload": result[0].payload
                }
            return None
        except Exception as e:
            logger.error("qdrant_retrieve_error", error=str(e))
            return None
    
    async def delete_embedding(
        self,
        collection_type: str,
        point_id: str,
        trace_id: Optional[str] = None
    ):
        """Delete an embedding."""
        collection_name = self.COLLECTIONS.get(collection_type)
        if not collection_name:
            raise ValueError(f"Unknown collection type: {collection_type}")
        
        await self._client.delete(
            collection_name=collection_name,
            points_selector=[point_id]
        )
        
        logger.info(
            "embedding_deleted",
            collection=collection_name,
            point_id=point_id,
            trace_id=trace_id
        )
    
    async def get_collection_info(self, collection_type: str) -> Dict[str, Any]:
        """Get collection information."""
        collection_name = self.COLLECTIONS.get(collection_type)
        if not collection_name:
            raise ValueError(f"Unknown collection type: {collection_type}")
        
        info = await self._client.get_collection(collection_name)
        
        return {
            "name": collection_name,
            "vectors_count": info.vectors_count,
            "indexed_vectors_count": info.indexed_vectors_count,
            "points_count": info.points_count,
            "status": info.status,
        }
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
