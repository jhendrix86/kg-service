from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
import structlog
from ..schemas import PatternQueryRequest, CausalChainQueryRequest, TemporalSequenceRequest, SimulationQueryRequest, GraphResponse
from ..graph import Neo4jClient
from ..embeddings import QdrantClient, EmbeddingGenerator
from ..tracing import Tracer


logger = structlog.get_logger()
router = APIRouter(prefix="/query", tags=["Query Graph"])


def get_neo4j():
    """Dependency for Neo4j client."""
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


@router.post("/patterns", response_model=GraphResponse)
async def query_patterns(
    request: PatternQueryRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    qdrant: QdrantClient = Depends(get_qdrant),
    embeddings: EmbeddingGenerator = Depends(get_embeddings),
    tracer: Tracer = Depends(get_tracer)
):
    """Query for patterns in the graph."""
    trace_parent = tracer.start_span("api.query_patterns")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        # Build Cypher query based on filters
        cypher = """
        MATCH (s:Strategy {type: 'pattern'})
        """
        
        params = {}
        
        if request.pattern_type:
            cypher += " WHERE s.name CONTAINS $pattern_type"
            params["pattern_type"] = request.pattern_type
        
        if request.entity_id:
            cypher += """
            MATCH (s)-[:SIMULATED_BY]->(e)
            WHERE e.id = $entity_id
            """
            params["entity_id"] = request.entity_id
        
        cypher += f"""
        RETURN s
        ORDER BY s.success_rate DESC
        LIMIT {request.limit}
        """
        
        results = await neo4j.query(cypher, params)
        
        # Filter by confidence threshold
        filtered_results = [
            r for r in results 
            if r.get("s", {}).get("success_rate", 0) >= request.confidence_threshold
        ]
        
        tracer.finish_span(trace_parent, "api.query_patterns", True, duration_ms=0)
        
        return GraphResponse(
            success=True,
            data={"patterns": filtered_results, "count": len(filtered_results)},
            trace_id=trace_id
        )
    
    except Exception as e:
        logger.error("query_patterns_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.query_patterns", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/causal-chain", response_model=GraphResponse)
async def query_causal_chain(
    request: CausalChainQueryRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    tracer: Tracer = Depends(get_tracer)
):
    """Query for causal chains starting from an event."""
    trace_parent = tracer.start_span("api.query_causal_chain")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        # Query causal chain
        cypher = f"""
        MATCH path = (start:Event {{event_id: $event_id}})-[:CAUSES*1..{request.max_depth}]->(end:Event)
        RETURN [node in nodes(path) | node] as chain, 
               [rel in relationships(path) | type(rel)] as relationships
        """
        
        results = await neo4j.query(cypher, {"event_id": request.event_id})
        
        chains = []
        for result in results:
            chain = result.get("chain", [])
            relationships = result.get("relationships", [])
            chains.append({
                "chain": chain,
                "relationships": relationships,
                "length": len(chain)
            })
        
        tracer.finish_span(trace_parent, "api.query_causal_chain", True, duration_ms=0)
        
        return GraphResponse(
            success=True,
            data={"causal_chains": chains, "count": len(chains)},
            trace_id=trace_id
        )
    
    except Exception as e:
        logger.error("query_causal_chain_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.query_causal_chain", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/temporal-sequence", response_model=GraphResponse)
async def query_temporal_sequence(
    request: TemporalSequenceRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    tracer: Tracer = Depends(get_tracer)
):
    """Query for temporal sequence of an entity."""
    trace_parent = tracer.start_span("api.query_temporal_sequence")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        # Get ID property for entity type
        from ..graph.client import Neo4jClient as Neo4jClientClass
        neo4j_client = Neo4jClientClass()
        id_property = neo4j_client._get_id_property_by_type(request.entity_type)
        
        # Build Cypher query
        cypher = f"""
        MATCH (e:{request.entity_type} {{{id_property}: $id}})-[:NEXT_STATE*]->(states)
        UNWIND states as state
        RETURN state
        """
        
        params = {"id": request.entity_id}
        
        # Add time filters if provided
        if request.start_time:
            cypher += " WHERE state.timestamp >= $start_time"
            params["start_time"] = request.start_time.isoformat()
        
        if request.end_time:
            if "WHERE" in cypher:
                cypher += " AND state.timestamp <= $end_time"
            else:
                cypher += " WHERE state.timestamp <= $end_time"
            params["end_time"] = request.end_time.isoformat()
        
        cypher += f"""
        ORDER BY state.timestamp
        LIMIT {request.limit}
        """
        
        results = await neo4j.query(cypher, params)
        
        tracer.finish_span(trace_parent, "api.query_temporal_sequence", True, duration_ms=0)
        
        return GraphResponse(
            success=True,
            data={"sequence": results, "count": len(results)},
            trace_id=trace_id
        )
    
    except Exception as e:
        logger.error("query_temporal_sequence_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.query_temporal_sequence", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/simulations", response_model=GraphResponse)
async def query_simulations(
    request: SimulationQueryRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    qdrant: QdrantClient = Depends(get_qdrant),
    embeddings: EmbeddingGenerator = Depends(get_embeddings),
    tracer: Tracer = Depends(get_tracer)
):
    """Query for simulations."""
    trace_parent = tracer.start_span("api.query_simulations")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        # Build Cypher query
        cypher = """
        MATCH (s:Simulation)
        """
        
        params = {}
        
        if request.simulation_type:
            cypher += " WHERE s.type CONTAINS $simulation_type"
            params["simulation_type"] = request.simulation_type
        
        if request.entity_id:
            cypher += """
            MATCH (s)-[:SIMULATED_BY]->(e)
            WHERE e.id = $entity_id
            """
            params["entity_id"] = request.entity_id
        
        cypher += f"""
        RETURN s
        ORDER BY s.confidence DESC
        LIMIT {request.limit}
        """
        
        results = await neo4j.query(cypher, params)
        
        # Filter by confidence threshold
        filtered_results = [
            r for r in results 
            if r.get("s", {}).get("confidence", 0) >= request.confidence_threshold
        ]
        
        tracer.finish_span(trace_parent, "api.query_simulations", True, duration_ms=0)
        
        return GraphResponse(
            success=True,
            data={"simulations": filtered_results, "count": len(filtered_results)},
            trace_id=trace_id
        )
    
    except Exception as e:
        logger.error("query_simulations_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.query_simulations", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/similar-funnels/{funnel_id}", response_model=GraphResponse)
async def query_similar_funnels(
    funnel_id: str,
    limit: int = 10,
    neo4j: Neo4jClient = Depends(get_neo4j),
    qdrant: QdrantClient = Depends(get_qdrant),
    embeddings: EmbeddingGenerator = Depends(get_embeddings),
    tracer: Tracer = Depends(get_tracer)
):
    """Query for similar funnels using embeddings."""
    trace_parent = tracer.start_span("api.query_similar_funnels")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        # Get funnel embedding
        embedding_data = await qdrant.get_embedding("funnels", funnel_id)
        if not embedding_data:
            raise HTTPException(status_code=404, detail="Funnel embedding not found")
        
        query_vector = embedding_data["vector"]
        
        # Search for similar funnels
        similar = await qdrant.search_similar(
            "funnels",
            query_vector,
            limit=limit,
            trace_id=trace_id
        )
        
        # Get full funnel data from Neo4j
        funnel_ids = [s["id"] for s in similar if s["id"] != funnel_id]
        funnels = []
        
        for fid in funnel_ids:
            from ..graph.schema import NodeType
            funnel = await neo4j.get_node(NodeType.FUNNEL, fid)
            if funnel:
                funnels.append(funnel)
        
        tracer.finish_span(trace_parent, "api.query_similar_funnels", True, duration_ms=0)
        
        return GraphResponse(
            success=True,
            data={"similar_funnels": funnels, "count": len(funnels)},
            trace_id=trace_id
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("query_similar_funnels_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.query_similar_funnels", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
