from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import asyncio
import structlog
from autonomy_events import EventEnvelope, ConsumeResult, TraceParent
from ..graph import Neo4jClient, NodeType
from ..embeddings import QdrantClient, EmbeddingGenerator
from ..tracing import Tracer


logger = structlog.get_logger()


class BaseConsumer(ABC):
    """Base class for all event consumers."""
    
    def __init__(
        self,
        neo4j_client: Neo4jClient,
        qdrant_client: QdrantClient,
        embedding_generator: EmbeddingGenerator,
        tracer: Tracer
    ):
        self.neo4j = neo4j_client
        self.qdrant = qdrant_client
        self.embeddings = embedding_generator
        self.tracer = tracer
    
    @abstractmethod
    async def handle_event(
        self,
        envelope: EventEnvelope,
        trace_parent: TraceParent
    ) -> ConsumeResult:
        """Handle the event. Must be implemented by subclasses."""
        pass
    
    async def process_with_retry(
        self,
        envelope: EventEnvelope,
        trace_parent: TraceParent,
        max_retries: int = 3
    ) -> ConsumeResult:
        """Process event with retry logic."""
        retry_count = 0
        last_error = None
        
        while retry_count <= max_retries:
            try:
                result = await self.handle_event(envelope, trace_parent)
                if result.success:
                    return result
                else:
                    last_error = result.error
            except Exception as e:
                last_error = str(e)
                logger.error(
                    "consumer_error",
                    event_id=envelope.event_id,
                    event_type=envelope.event_type,
                    retry_count=retry_count,
                    error=str(e)
                )
            
            retry_count += 1
            if retry_count <= max_retries:
                await asyncio.sleep(2 ** retry_count)  # Exponential backoff
        
        return ConsumeResult(
            success=False,
            event_id=envelope.event_id,
            event_type=envelope.event_type,
            error=last_error or "Max retries exceeded",
            should_ack=False,
            should_requeue=True
        )
    
    async def write_to_graph(
        self,
        node_type: NodeType,
        properties: Dict[str, Any],
        trace_id: Optional[str] = None
    ) -> str:
        """Write a node to the graph."""
        return await self.neo4j.create_node(node_type, properties, trace_id)
    
    async def write_relationship(
        self,
        from_type: NodeType,
        from_id: str,
        to_type: NodeType,
        to_id: str,
        rel_type: str,
        properties: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ):
        """Write a relationship to the graph."""
        from ..graph.schema import RelationshipType
        rel_enum = RelationshipType(rel_type)
        await self.neo4j.create_relationship(
            from_type, from_id, to_type, to_id, rel_enum, properties, trace_id
        )
    
    async def write_embedding(
        self,
        collection_type: str,
        point_id: str,
        text: str,
        metadata: Dict[str, Any],
        trace_id: Optional[str] = None
    ):
        """Generate and store embedding."""
        vector = self.embeddings.generate_embedding(text, trace_id)
        await self.qdrant.upsert_embedding(
            collection_type, point_id, vector, metadata, trace_id
        )
