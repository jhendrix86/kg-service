import asyncio
from typing import Dict, Any
import structlog
from autonomy_events import EventConsumer, ConsumeResult, TraceParent
from ..consumers import (
    FunnelConsumer,
    GovernanceConsumer,
    KGConsumer,
    SafetyConsumer,
    FailureConsumer,
    EngineConsumer,
    TemporalConsumer,
)
from ..graph import Neo4jClient
from ..embeddings import QdrantClient, EmbeddingGenerator
from ..tracing import Tracer
from ..utils.config import settings


logger = structlog.get_logger()


class ConsumerService:
    """Service to manage all event consumers."""
    
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
        
        self.consumers: Dict[str, EventConsumer] = {}
        self._consumer_handlers = {
            "funnel": FunnelConsumer,
            "governance": GovernanceConsumer,
            "kg": KGConsumer,
            "safety": SafetyConsumer,
            "failure": FailureConsumer,
            "engine": EngineConsumer,
            "temporal": TemporalConsumer,
        }
    
    async def initialize(self):
        """Initialize all consumers."""
        # Create consumers for each event type
        routing_keys = [
            "funnel.*",
            "governance.*",
            "kg.*",
            "safety.*",
            "failure.*",
            "engine.*",
            "temporal.*",
            "causal.*",
        ]
        
        for consumer_type, handler_class in self._consumer_handlers.items():
            consumer = EventConsumer(
                rabbitmq_url=settings.rabbitmq_url,
                queue_name=f"kg-{consumer_type}-events",
                exchange_name=settings.rabbitmq_exchange,
                exchange_type=settings.rabbitmq_exchange_type,
                routing_keys=[f"{consumer_type}.*"],
                # kg-service's own app Settings (pydantic-settings) was
                # passed here, not an autonomy_events.utils.config.Config -
                # EventConsumer.connect() reads config.dlq_queue_suffix
                # (and other Config-only fields) unconditionally, so every
                # consumer crashed on connect with AttributeError before
                # ever consuming a single message. Omit it and let
                # EventConsumer default to Config.from_env() - the real
                # Config class, with its own sensible defaults.
                tracer=self.tracer
            )
            
            # Create handler instance
            handler = handler_class(
                self.neo4j,
                self.qdrant,
                self.embeddings,
                self.tracer
            )
            
            # Register handler for all event types
            consumer.register_default_handler(handler.handle_event)
            
            self.consumers[consumer_type] = consumer
            
            logger.info("consumer_initialized", consumer_type=consumer_type)
    
    async def start_all(self):
        """Start all consumers."""
        for consumer_type, consumer in self.consumers.items():
            await consumer.connect()
            logger.info("consumer_connected", consumer_type=consumer_type)
        
        # Start consuming in parallel
        tasks = []
        for consumer_type, consumer in self.consumers.items():
            task = asyncio.create_task(
                self._run_consumer(consumer_type, consumer),
                name=f"consumer-{consumer_type}"
            )
            tasks.append(task)
        
        logger.info("all_consumers_started", count=len(tasks))
        
        # Wait for all tasks (they run forever)
        await asyncio.gather(*tasks)
    
    async def _run_consumer(self, consumer_type: str, consumer: EventConsumer):
        """Run a single consumer with error handling."""
        while True:
            try:
                logger.info("consumer_starting", consumer_type=consumer_type)
                await consumer.start_consuming()
            except Exception as e:
                logger.error(
                    "consumer_crashed",
                    consumer_type=consumer_type,
                    error=str(e)
                )
                # Wait before reconnecting
                await asyncio.sleep(5)
                try:
                    await consumer.connect()
                except Exception as reconnect_error:
                    logger.error(
                        "consumer_reconnect_failed",
                        consumer_type=consumer_type,
                        error=str(reconnect_error)
                    )
                    await asyncio.sleep(10)
    
    async def stop_all(self):
        """Stop all consumers."""
        for consumer_type, consumer in self.consumers.items():
            consumer.stop_consuming()
            await consumer.disconnect()
            logger.info("consumer_stopped", consumer_type=consumer_type)
