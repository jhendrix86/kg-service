import pytest
from unittest.mock import AsyncMock, MagicMock
from app.consumers.funnel_consumer import FunnelConsumer
from app.consumers.governance_consumer import GovernanceConsumer
from app.consumers.kg_consumer import KGConsumer
from autonomy_events import EventEnvelope, ConsumeResult, TraceParent


class TestFunnelConsumer:
    @pytest.fixture
    def funnel_consumer(self):
        neo4j_mock = AsyncMock()
        qdrant_mock = AsyncMock()
        embeddings_mock = MagicMock()
        tracer_mock = MagicMock()
        
        return FunnelConsumer(neo4j_mock, qdrant_mock, embeddings_mock, tracer_mock)
    
    @pytest.fixture
    def trace_parent(self):
        return TraceParent(
            trace_context=MagicMock(trace_id="test-trace-123", span_id="test-span-123"),
            correlation_id="test-corr-123"
        )
    
    @pytest.mark.asyncio
    async def test_handle_funnel_created(self, funnel_consumer, trace_parent):
        envelope = EventEnvelope(
            event_type="funnel.created",
            engine_id="test-engine",
            payload={
                "funnel_id": "funnel-123",
                "niche": "fitness",
                "strategy": "content_first",
                "created_by": "autonomous-engine"
            }
        )
        
        result = await funnel_consumer.handle_event(envelope, trace_parent)
        
        assert result.success is True
        assert result.event_id == envelope.event_id
        assert result.event_type == "funnel.created"
    
    @pytest.mark.asyncio
    async def test_handle_funnel_launched(self, funnel_consumer, trace_parent):
        envelope = EventEnvelope(
            event_type="funnel.launched",
            engine_id="test-engine",
            payload={
                "funnel_id": "funnel-123",
                "channels": ["twitter", "linkedin"],
                "launched_by": "autonomous-engine"
            }
        )
        
        result = await funnel_consumer.handle_event(envelope, trace_parent)
        
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_handle_unknown_event(self, funnel_consumer, trace_parent):
        envelope = EventEnvelope(
            event_type="funnel.unknown",
            engine_id="test-engine",
            payload={}
        )
        
        result = await funnel_consumer.handle_event(envelope, trace_parent)
        
        assert result.success is False
        assert "Unknown funnel event type" in result.error


class TestGovernanceConsumer:
    @pytest.fixture
    def governance_consumer(self):
        neo4j_mock = AsyncMock()
        qdrant_mock = AsyncMock()
        embeddings_mock = MagicMock()
        tracer_mock = MagicMock()
        
        return GovernanceConsumer(neo4j_mock, qdrant_mock, embeddings_mock, tracer_mock)
    
    @pytest.fixture
    def trace_parent(self):
        return TraceParent(
            trace_context=MagicMock(trace_id="test-trace-123", span_id="test-span-123"),
            correlation_id="test-corr-123"
        )
    
    @pytest.mark.asyncio
    async def test_handle_governance_request(self, governance_consumer, trace_parent):
        envelope = EventEnvelope(
            event_type="governance.request",
            engine_id="test-engine",
            payload={
                "request_id": "req-123",
                "action_type": "create_funnel",
                "requester": "autonomous-engine"
            }
        )
        
        result = await governance_consumer.handle_event(envelope, trace_parent)
        
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_handle_governance_approved(self, governance_consumer, trace_parent):
        envelope = EventEnvelope(
            event_type="governance.approved",
            engine_id="test-engine",
            payload={
                "request_id": "req-123",
                "approved_by": "governance-engine",
                "approval_token": "token-123"
            }
        )
        
        result = await governance_consumer.handle_event(envelope, trace_parent)
        
        assert result.success is True


class TestKGConsumer:
    @pytest.fixture
    def kg_consumer(self):
        neo4j_mock = AsyncMock()
        qdrant_mock = AsyncMock()
        embeddings_mock = MagicMock()
        tracer_mock = MagicMock()
        
        return KGConsumer(neo4j_mock, qdrant_mock, embeddings_mock, tracer_mock)
    
    @pytest.fixture
    def trace_parent(self):
        return TraceParent(
            trace_context=MagicMock(trace_id="test-trace-123", span_id="test-span-123"),
            correlation_id="test-corr-123"
        )
    
    @pytest.mark.asyncio
    async def test_handle_entity_created(self, kg_consumer, trace_parent):
        envelope = EventEnvelope(
            event_type="kg.entity_created",
            engine_id="test-engine",
            payload={
                "entity_type": "user",
                "entity_id": "user-123",
                "attributes": {"email": "test@example.com"},
                "source": "gumroad"
            }
        )
        
        result = await kg_consumer.handle_event(envelope, trace_parent)
        
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_handle_pattern_detected(self, kg_consumer, trace_parent):
        envelope = EventEnvelope(
            event_type="kg.pattern_detected",
            engine_id="test-engine",
            payload={
                "pattern_type": "high_conversion",
                "entities": [{"type": "funnel", "id": "funnel-1"}],
                "confidence": 0.85,
                "detected_by": "intelligence-engine"
            }
        )
        
        result = await kg_consumer.handle_event(envelope, trace_parent)
        
        assert result.success is True
