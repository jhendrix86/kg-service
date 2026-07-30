from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Knowledge Graph Service Configuration."""
    
    # Service
    service_name: str = "kg-service"
    service_version: str = "1.0.0"
    port: int = 8034
    
    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    neo4j_database: str = "neo4j"
    
    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: Optional[str] = None
    qdrant_collection_prefix: str = "kg"
    
    # RabbitMQ
    rabbitmq_url: str = "amqp://localhost:5672"
    rabbitmq_exchange: str = "autonomy.events"
    rabbitmq_exchange_type: str = "topic"
    
    # Event Consumers
    consumer_prefetch_count: int = 10
    consumer_auto_ack: bool = False
    dlq_enabled: bool = True
    
    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    
    # OpenTelemetry
    otel_enabled: bool = True
    otel_endpoint: str = "http://localhost:4318"
    otel_service_name: str = "kg-service"
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
