from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
import structlog
from ..schemas import GraphResponse
from ..graph import Neo4jClient, NodeType
from ..tracing import Tracer, TraceParent


logger = structlog.get_logger()
router = APIRouter(prefix="/graph", tags=["Read Graph"])


def get_neo4j():
    """Dependency for Neo4j client."""
    from ..graph.client import Neo4jClient
    return Neo4jClient()


def get_tracer():
    """Dependency for tracer."""
    from ..tracing import Tracer
    return Tracer("kg-service")


@router.get("/funnel/{funnel_id}", response_model=GraphResponse)
async def get_funnel(
    funnel_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
    tracer: Tracer = Depends(get_tracer)
):
    """Get a funnel by ID."""
    trace_parent = tracer.start_span("api.get_funnel")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        funnel = await neo4j.get_node(NodeType.FUNNEL, funnel_id)
        
        if not funnel:
            raise HTTPException(status_code=404, detail="Funnel not found")
        
        tracer.finish_span(trace_parent, "api.get_funnel", True, duration_ms=0)
        
        return GraphResponse(
            success=True,
            data={"funnel": funnel},
            trace_id=trace_id
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_funnel_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.get_funnel", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}", response_model=GraphResponse)
async def get_user(
    user_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
    tracer: Tracer = Depends(get_tracer)
):
    """Get a user by ID."""
    trace_parent = tracer.start_span("api.get_user")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        user = await neo4j.get_node(NodeType.USER, user_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        tracer.finish_span(trace_parent, "api.get_user", True, duration_ms=0)
        
        return GraphResponse(
            success=True,
            data={"user": user},
            trace_id=trace_id
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_user_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.get_user", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/niche/{niche_id}", response_model=GraphResponse)
async def get_niche(
    niche_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
    tracer: Tracer = Depends(get_tracer)
):
    """Get a niche by ID."""
    trace_parent = tracer.start_span("api.get_niche")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        niche = await neo4j.get_node(NodeType.NICHE, niche_id)
        
        if not niche:
            raise HTTPException(status_code=404, detail="Niche not found")
        
        tracer.finish_span(trace_parent, "api.get_niche", True, duration_ms=0)
        
        return GraphResponse(
            success=True,
            data={"niche": niche},
            trace_id=trace_id
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_niche_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.get_niche", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/competitor/{competitor_id}", response_model=GraphResponse)
async def get_competitor(
    competitor_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
    tracer: Tracer = Depends(get_tracer)
):
    """Get a competitor by ID."""
    trace_parent = tracer.start_span("api.get_competitor")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        competitor = await neo4j.get_node(NodeType.COMPETITOR, competitor_id)
        
        if not competitor:
            raise HTTPException(status_code=404, detail="Competitor not found")
        
        tracer.finish_span(trace_parent, "api.get_competitor", True, duration_ms=0)
        
        return GraphResponse(
            success=True,
            data={"competitor": competitor},
            trace_id=trace_id
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_competitor_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.get_competitor", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity/{entity_type}/{entity_id}", response_model=GraphResponse)
async def get_entity(
    entity_type: str,
    entity_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
    tracer: Tracer = Depends(get_tracer)
):
    """Get any entity by type and ID."""
    trace_parent = tracer.start_span("api.get_entity")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        node_type = _map_entity_type_to_node_type(entity_type)
        if not node_type:
            raise HTTPException(status_code=400, detail=f"Unknown entity type: {entity_type}")
        
        entity = await neo4j.get_node(node_type, entity_id)
        
        if not entity:
            raise HTTPException(status_code=404, detail=f"{entity_type} not found")
        
        tracer.finish_span(trace_parent, "api.get_entity", True, duration_ms=0)
        
        return GraphResponse(
            success=True,
            data={"entity": entity, "entity_type": entity_type},
            trace_id=trace_id
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_entity_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.get_entity", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


def _map_entity_type_to_node_type(entity_type: str):
    """Map entity type string to NodeType."""
    mapping = {
        "user": NodeType.USER,
        "funnel": NodeType.FUNNEL,
        "product": NodeType.PRODUCT,
        "niche": NodeType.NICHE,
        "keyword": NodeType.KEYWORD,
        "strategy": NodeType.STRATEGY,
        "revenue": NodeType.REVENUE,
        "event": NodeType.EVENT,
        "engine": NodeType.ENGINE,
        "competitor": NodeType.COMPETITOR,
        "content": NodeType.CONTENT,
        "platform": NodeType.PLATFORM,
        "risk": NodeType.RISK,
        "failure": NodeType.FAILURE,
        "recovery": NodeType.RECOVERY,
        "market": NodeType.MARKET,
        "simulation": NodeType.SIMULATION
    }
    return mapping.get(entity_type.lower())
