# Knowledge Graph Service

The memory and reasoning layer for the Autonomous Company OS. This service consumes events from RabbitMQ, stores entities and relationships in Neo4j, maintains embeddings in Qdrant, and provides APIs for querying the knowledge graph.

## Features

- **Graph Storage** - Neo4j for entities and relationships with 18 node types and 20+ relationship types
- **Embedding Storage** - Qdrant for vector similarity search across users, funnels, niches, competitors, content, and strategies
- **Event Consumption** - Consumes events from 7 event categories (funnel, governance, KG, safety, failure, engine, temporal)
- **Query APIs** - Pattern detection, causal chains, temporal sequences, simulations
- **Insight APIs** - Funnel, niche, market, and competitor insights
- **Distributed Tracing** - OpenTelemetry integration with W3C traceparent support
- **DLQ Management** - Dead letter queue with replay capabilities
- **Real-time Updates** - Async event processing with automatic graph updates

## Architecture

```
┌─────────────┐    Events    ┌──────────────┐
│   RabbitMQ  │ ────────────> │  Consumers   │
└─────────────┘              └──────┬───────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
            ┌───────▼──────┐ ┌────▼────┐ ┌────▼──────┐
            │    Neo4j     │ │ Qdrant  │ │  Tracing  │
            │  (Graph DB)  │ │(Vector) │ │ (OTel)    │
            └──────────────┘ └─────────┘ └───────────┘
                    │              │
                    └──────┬───────┘
                           │
                    ┌──────▼──────┐
                    │   FastAPI   │
                    │  (REST API) │
                    └─────────────┘
```

## Installation

### Prerequisites

- Python 3.9+
- Neo4j 5.14+
- Qdrant 1.7+
- RabbitMQ 3.12+
- Docker (optional, for containerized deployment)

### Local Development

```bash
# Clone repository
git clone https://github.com/autonomous-company/kg-service.git
cd kg-service

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your configuration

# Run the service
uvicorn app.main:app --reload --port 8034
```

### Docker Deployment

```bash
# Build and start all services
cd docker
docker-compose up -d

# View logs
docker-compose logs -f kg-service

# Stop services
docker-compose down
```

## Configuration

Configuration is managed via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `password` | Neo4j password |
| `QDRANT_HOST` | `localhost` | Qdrant host |
| `QDRANT_PORT` | `6333` | Qdrant port |
| `RABBITMQ_URL` | `amqp://localhost:5672` | RabbitMQ connection URL |
| `RABBITMQ_EXCHANGE` | `autonomy.events` | RabbitMQ exchange name |
| `OTEL_ENABLED` | `true` | Enable OpenTelemetry tracing |
| `OTEL_ENDPOINT` | `http://localhost:4318` | OTLP endpoint |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence transformer model |

## Graph Schema

### Node Types

- **User** - User accounts and profiles
- **Funnel** - Sales funnels
- **Product** - Products (Gumroad, etc.)
- **Niche** - Market niches
- **Keyword** - SEO keywords
- **Strategy** - Optimization strategies
- **Revenue** - Revenue records
- **Event** - System events
- **Engine** - Service engines
- **Competitor** - Competitor data
- **Content** - Marketing content
- **Platform** - Social platforms
- **Risk** - Risk factors
- **Failure** - System failures
- **Recovery** - Recovery actions
- **Market** - Market data
- **Simulation** - Simulations and snapshots

### Relationship Types

- **INTERACTED_WITH** - User-funnel interactions
- **GENERATES** - Funnel generates revenue
- **OPTIMIZED_BY** - Funnel optimized by strategy
- **HAS_TREND** - Niche has trending keywords
- **COMPETES_WITH** - Competitors in same niche
- **PERFORMS_ON** - Content performs on platform
- **CAUSED_BY** - Risk/failure caused by entity
- **LEADS_TO** - Event leads to another event
- **VERSION_OF** - Funnel version relationship
- **SIMULATED_BY** - Simulation of entity
- **FAILED_BECAUSE** - Failure cause
- **RECOVERED_BY** - Recovery action
- **PART_OF** - Entity belongs to another
- **RUNS_ON** - Engine runs on platform
- **NEXT_STATE** - Temporal state transition
- **PREVIOUS_STATE** - Previous temporal state
- **AT_TIME** - Temporal timestamp
- **CAUSES** - Causal relationship
- **RESULTS_IN** - Result relationship

## API Endpoints

### Health & Info

- `GET /health` - Health check
- `GET /` - Service information

### Write Events

- `POST /events/funnel-launched` - Record funnel launch
- `POST /events/funnel-metrics` - Update funnel metrics
- `POST /events/funnel-insights` - Store funnel insights
- `POST /events/anomaly` - Record detected anomaly

### Read Graph

- `GET /graph/funnel/{funnel_id}` - Get funnel by ID
- `GET /graph/user/{user_id}` - Get user by ID
- `GET /graph/niche/{niche_id}` - Get niche by ID
- `GET /graph/competitor/{competitor_id}` - Get competitor by ID
- `GET /graph/entity/{entity_type}/{entity_id}` - Get any entity

### Query Graph

- `POST /query/patterns` - Query for patterns
- `POST /query/causal-chain` - Query causal chains
- `POST /query/temporal-sequence` - Query temporal sequences
- `POST /query/simulations` - Query simulations
- `POST /query/similar-funnels/{funnel_id}` - Find similar funnels

### Insights

- `GET /insights/funnel/{funnel_id}` - Get funnel insights
- `GET /insights/niche/{niche_id}` - Get niche insights
- `GET /insights/market/{market_id}` - Get market insights
- `GET /insights/competitor/{competitor_id}` - Get competitor insights

### DLQ Management

- `GET /dlq/stats` - Get DLQ statistics
- `GET /dlq/messages` - Peek at DLQ messages
- `POST /dlq/replay/{event_id}` - Replay specific message
- `POST /dlq/replay-batch` - Replay batch of messages
- `POST /dlq/purge` - Purge old messages

## Event Consumption

The service consumes events from RabbitMQ and updates the graph accordingly:

### Funnel Events
- `funnel.created` - Create funnel node, link to niche, store embedding
- `funnel.launched` - Update funnel status, create event node
- `funnel.metrics` - Update funnel metrics, create revenue nodes
- `funnel.insights` - Store insights, update embedding
- `funnel.mutation` - Create strategy nodes, link to funnel
- `funnel.archived` - Mark funnel as archived

### Governance Events
- `governance.request` - Create event node, link to resource
- `governance.approved` - Update with approval data
- `governance.rejected` - Create risk node
- `governance.emergency_stop` - Create failure node
- `governance.override` - Create risk node

### Knowledge Graph Events
- `kg.entity_created` - Create/update entity node, store embedding
- `kg.relationship_created` - Create relationship between entities
- `kg.pattern_detected` - Create strategy node
- `kg.insight_generated` - Store insight, create embedding
- `kg.anomaly_detected` - Create risk node

### Safety Events
- `safety.violation_detected` - Create risk node, link to entity
- `safety.blocked_action` - Create event node
- `safety.rollback_triggered` - Create recovery node

### Failure Events
- `failure.detected` - Create failure node, link to component
- `failure.recovered` - Update failure, create recovery node
- `failure.retry_scheduled` - Create event node for retry

### Engine Events
- `engine.health_report` - Update engine node with health metrics
- `engine.degraded` - Mark engine as degraded, create failure node
- `engine.recovered` - Mark engine as recovered, create recovery node

### Temporal Events
- `temporal.snapshot` - Create simulation node, link to entity
- `causal.chain_detected` - Create strategy node, link causal chain

## Usage Examples

### Record Funnel Launch

```python
import httpx

async def record_funnel_launch():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8034/events/funnel-launched",
            json={
                "funnel_id": "funnel-123",
                "timestamp": "2024-01-01T00:00:00Z",
                "channels": ["twitter", "linkedin"],
                "launch_config": {"auto_optimize": True},
                "launched_by": "autonomous-engine"
            }
        )
        return response.json()
```

### Query Causal Chain

```python
async def query_causal_chain(event_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8034/query/causal-chain",
            json={
                "event_id": event_id,
                "max_depth": 5,
                "include_branches": False
            }
        )
        return response.json()
```

### Get Funnel Insights

```python
async def get_funnel_insights(funnel_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8034/insights/funnel/{funnel_id}"
        )
        return response.json()
```

### Replay DLQ Messages

```python
async def replay_dlq_batch():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8034/dlq/replay-batch",
            json={
                "limit": 100,
                "event_type_filter": "funnel.created"
            }
        )
        return response.json()
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_graph_schema.py
```

### Adding New Event Consumers

1. Create a new consumer class in `app/consumers/` extending `BaseConsumer`
2. Implement the `handle_event` method
3. Register the consumer in `ConsumerService`
4. Add routing keys to the consumer configuration

### Adding New Node Types

1. Add node type to `NodeType` enum in `app/graph/schema.py`
2. Add constraint in `get_node_constraints()`
3. Add properties in `get_node_properties()`
4. Update `_map_entity_type_to_node_type()` in consumers

## Monitoring

### OpenTelemetry Tracing

The service exports traces to OTLP endpoint (default: `http://localhost:4318`). View traces in Jaeger UI at `http://localhost:16686`.

### Health Check

```bash
curl http://localhost:8034/health
```

### Metrics

Metrics are available through OpenTelemetry integration. Configure Prometheus scraping for the OTLP endpoint.

## Troubleshooting

### Neo4j Connection Failed

- Check Neo4j is running: `docker ps | grep neo4j`
- Verify connection URI in environment variables
- Check Neo4j logs: `docker logs kg-neo4j`

### Qdrant Connection Failed

- Check Qdrant is running: `docker ps | grep qdrant`
- Verify host and port in environment variables
- Check Qdrant logs: `docker logs kg-qdrant`

### RabbitMQ Connection Failed

- Check RabbitMQ is running: `docker ps | grep rabbitmq`
- Verify connection URL in environment variables
- Check RabbitMQ logs: `docker logs kg-rabbitmq`

### Events Not Being Consumed

- Check consumer logs for errors
- Verify RabbitMQ exchange exists
- Check routing keys match event types
- Verify DLQ for failed messages

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request
