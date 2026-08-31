from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import json
import structlog
from ..schemas import FunnelLaunchedRequest, FunnelMetricsRequest, FunnelInsightsRequest, AnomalyRequest, GraphResponse
from ..graph import Neo4jClient, NodeType
from ..embeddings import QdrantClient, EmbeddingGenerator
from ..tracing import Tracer, TraceParent


logger = structlog.get_logger()
router = APIRouter(prefix="/events", tags=["Write Events"])


def get_neo4j():
    """Dependency for Neo4j client."""
    # In production, this would be a singleton
    from ..graph.client import Neo4jClient
    return Neo4jClient()


def get_qdrant():
    """Dependency for Qdrant client."""
    from ..embeddings.client import QdrantClient
    return QdrantClient()


def get_embeddings():
    """Dependency for embedding generator."""
    from ..embeddings.generator import EmbeddingGenerator
    return EmbeddingGenerator()


def get_tracer():
    """Dependency for tracer."""
    from ..tracing import Tracer
    return Tracer("kg-service")


@router.post("/funnel-launched", response_model=GraphResponse)
async def funnel_launched(
    request: FunnelLaunchedRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    qdrant: QdrantClient = Depends(get_qdrant),
    embeddings: EmbeddingGenerator = Depends(get_embeddings),
    tracer: Tracer = Depends(get_tracer)
):
    """Handle funnel.launched event write."""
    trace_parent = tracer.start_span("api.funnel_launched")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        # Update funnel node
        properties = {
            "status": "launched",
            "launched_at": request.timestamp.isoformat(),
            "channels": request.channels,
            "launched_by": request.launched_by
        }
        
        await neo4j.update_node(NodeType.FUNNEL, request.funnel_id, properties, trace_id)
        
        # Create event node
        event_id = f"event_{request.funnel_id}_launched"
        event_properties = {
            "event_id": event_id,
            "event_type": "funnel.launched",
            "timestamp": request.timestamp.isoformat(),
            "source": request.launched_by,
            # Neo4j properties must be primitives - a nested dict (and its
            # raw datetime) can't be stored; JSON-encode it. mode="json"
            # so the datetime inside serializes.
            "payload": json.dumps(request.model_dump(mode="json")),
            "correlation_id": trace_id
        }
        
        await neo4j.create_node(NodeType.EVENT, event_properties, trace_id)
        
        # Link event to funnel
        from ..graph.schema import RelationshipType
        await neo4j.create_relationship(
            NodeType.EVENT, event_id,
            NodeType.FUNNEL, request.funnel_id,
            RelationshipType.CAUSES,
            trace_id=trace_id
        )
        
        tracer.finish_span(trace_parent, "api.funnel_launched", True, duration_ms=0)
        
        return GraphResponse(
            success=True,
            data={"funnel_id": request.funnel_id, "event_id": event_id},
            trace_id=trace_id
        )
    
    except Exception as e:
        logger.error("funnel_launched_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.funnel_launched", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/funnel-metrics", response_model=GraphResponse)
async def funnel_metrics(
    request: FunnelMetricsRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    tracer: Tracer = Depends(get_tracer)
):
    """Handle funnel.metrics event write."""
    trace_parent = tracer.start_span("api.funnel_metrics")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        # Update funnel node with metrics
        properties = {
            "total_visitors": request.visitors,
            "total_conversions": request.conversions,
            "total_revenue": request.revenue,
            "conversion_rate": request.conversion_rate,
            "cost": request.cost,
            "roi": request.roi
        }
        
        await neo4j.update_node(NodeType.FUNNEL, request.funnel_id, properties, trace_id)
        
        # Create revenue node if revenue > 0
        if request.revenue > 0:
            from datetime import datetime
            revenue_id = f"revenue_{request.funnel_id}_{int(datetime.utcnow().timestamp())}"
            revenue_properties = {
                "revenue_id": revenue_id,
                "amount": request.revenue,
                "currency": "USD",
                "source": "funnel",
                "funnel_id": request.funnel_id,
                "timestamp": request.timestamp.isoformat()
            }
            
            await neo4j.create_node(NodeType.REVENUE, revenue_properties, trace_id)
            
            from ..graph.schema import RelationshipType
            await neo4j.create_relationship(
                NodeType.FUNNEL, request.funnel_id,
                NodeType.REVENUE, revenue_id,
                RelationshipType.GENERATES,
                trace_id=trace_id
            )
        
        tracer.finish_span(trace_parent, "api.funnel_metrics", True, duration_ms=0)
        
        return GraphResponse(
            success=True,
            data={"funnel_id": request.funnel_id, "metrics_updated": True},
            trace_id=trace_id
        )
    
    except Exception as e:
        logger.error("funnel_metrics_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.funnel_metrics", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/funnel-insights", response_model=GraphResponse)
async def funnel_insights(
    request: FunnelInsightsRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    qdrant: QdrantClient = Depends(get_qdrant),
    embeddings: EmbeddingGenerator = Depends(get_embeddings),
    tracer: Tracer = Depends(get_tracer)
):
    """Handle funnel.insights event write."""
    trace_parent = tracer.start_span("api.funnel_insights")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        # Update funnel node with insights
        properties = {
            "insights": request.recommendations,
            "insight_confidence": request.confidence,
            "insight_type": request.insight_type,
            "last_insight_at": request.timestamp.isoformat()
        }
        
        await neo4j.update_node(NodeType.FUNNEL, request.funnel_id, properties, trace_id)
        
        # Store insight embedding
        insights_text = " ".join(request.recommendations)
        if insights_text:
            vector = embeddings.generate_embedding(insights_text, trace_id)
            await qdrant.upsert_embedding(
                "funnels",
                f"{request.funnel_id}_insights",
                vector,
                {"funnel_id": request.funnel_id, "type": "insights"},
                trace_id
            )
        
        tracer.finish_span(trace_parent, "api.funnel_insights", True, duration_ms=0)
        
        return GraphResponse(
            success=True,
            data={"funnel_id": request.funnel_id, "insights_stored": len(request.recommendations)},
            trace_id=trace_id
        )
    
    except Exception as e:
        logger.error("funnel_insights_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.funnel_insights", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/anomaly", response_model=GraphResponse)
async def anomaly(
    request: AnomalyRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    tracer: Tracer = Depends(get_tracer)
):
    """Handle anomaly event write."""
    trace_parent = tracer.start_span("api.anomaly")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        from datetime import datetime
        anomaly_id = f"anomaly_{int(datetime.utcnow().timestamp())}"
        
        # Create risk node for anomaly
        properties = {
            "risk_id": anomaly_id,
            "type": request.anomaly_type,
            "severity": request.severity,
            "description": f"Anomaly detected in {request.anomaly_type}",
            "mitigation": "Investigate and address",
            "probability": 0.8,
            "impact": 0.6,
            "created_at": request.detected_at.isoformat()
        }
        
        await neo4j.create_node(NodeType.RISK, properties, trace_id)
        
        # Link to affected entity
        node_type = _map_entity_type_to_node_type(request.entity_type)
        if node_type:
            from ..graph.schema import RelationshipType
            await neo4j.create_relationship(
                NodeType.RISK, anomaly_id,
                node_type, request.entity_id,
                RelationshipType.CAUSED_BY,
                trace_id=trace_id
            )
        
        tracer.finish_span(trace_parent, "api.anomaly", True, duration_ms=0)
        
        return GraphResponse(
            success=True,
            data={"anomaly_id": anomaly_id, "entity_id": request.entity_id},
            trace_id=trace_id
        )
    
    except Exception as e:
        logger.error("anomaly_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.anomaly", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


def _map_entity_type_to_node_type(entity_type: str):
    """Map entity type string to NodeType."""
    from ..graph.schema import NodeType
    mapping = {
        "funnel": NodeType.FUNNEL,
        "product": NodeType.PRODUCT,
        "niche": NodeType.NICHE,
        "user": NodeType.USER,
        "engine": NodeType.ENGINE
    }
    return mapping.get(entity_type.lower())
