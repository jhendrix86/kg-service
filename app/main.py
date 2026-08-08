import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog
from .controllers import write_controller, read_controller, query_controller, insight_controller, dlq_controller
from .graph import Neo4jClient
from .embeddings import QdrantClient, EmbeddingGenerator
from .tracing import Tracer
from .services import ConsumerService
from .utils.config import settings


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Create FastAPI app
app = FastAPI(
    title="Knowledge Graph Service",
    description="Memory and reasoning layer for the Autonomous Company OS",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(write_controller.router)
app.include_router(read_controller.router)
app.include_router(query_controller.router)
app.include_router(insight_controller.router)
app.include_router(dlq_controller.router)

# Global clients
neo4j_client: Neo4jClient = None
qdrant_client: QdrantClient = None
embedding_generator: EmbeddingGenerator = None
tracer: Tracer = None
consumer_service: ConsumerService = None


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global neo4j_client, qdrant_client, embedding_generator, tracer, consumer_service
    
    logger.info("service_starting", service=settings.service_name)
    
    # Initialize tracer
    tracer = Tracer(settings.service_name)
    
    # Initialize Neo4j
    neo4j_client = Neo4jClient()
    await neo4j_client.connect()
    await neo4j_client.initialize_schema()
    logger.info("neo4j_initialized")
    
    # Initialize Qdrant
    qdrant_client = QdrantClient()
    await qdrant_client.connect()
    await qdrant_client.initialize_collections()
    logger.info("qdrant_initialized")
    
    # Initialize embedding generator
    embedding_generator = EmbeddingGenerator()
    embedding_generator.load_model()
    logger.info("embedding_generator_initialized")
    
    # Initialize consumer service
    consumer_service = ConsumerService(
        neo4j_client,
        qdrant_client,
        embedding_generator,
        tracer
    )
    await consumer_service.initialize()
    
    # Start consumers in background
    asyncio.create_task(consumer_service.start_all())
    
    logger.info("service_started", service=settings.service_name)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global neo4j_client, qdrant_client, consumer_service
    
    logger.info("service_stopping")
    
    if consumer_service:
        await consumer_service.stop_all()
    
    if neo4j_client:
        await neo4j_client.disconnect()
    
    if qdrant_client:
        await qdrant_client.disconnect()
    
    logger.info("service_stopped")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "status": "healthy"
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Knowledge Graph Service",
        "version": "1.0.0",
        "description": "Memory and reasoning layer for the Autonomous Company OS",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True
    )
