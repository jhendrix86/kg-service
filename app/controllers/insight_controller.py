from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
import structlog
from ..schemas import InsightResponse
from ..graph import Neo4jClient, NodeType
from ..embeddings import QdrantClient, EmbeddingGenerator
from ..tracing import Tracer


logger = structlog.get_logger()
router = APIRouter(prefix="/insights", tags=["Insights"])


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


@router.get("/funnel/{funnel_id}", response_model=InsightResponse)
async def get_funnel_insights(
    funnel_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
    qdrant: QdrantClient = Depends(get_qdrant),
    embeddings: EmbeddingGenerator = Depends(get_embeddings),
    tracer: Tracer = Depends(get_tracer)
):
    """Get insights for a funnel."""
    trace_parent = tracer.start_span("api.get_funnel_insights")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        insights = []
        
        # Get funnel data
        funnel = await neo4j.get_node(NodeType.FUNNEL, funnel_id)
        if not funnel:
            raise HTTPException(status_code=404, detail="Funnel not found")
        
        # Get similar funnels
        similar_funnels = await neo4j.get_similar_funnels(funnel_id, limit=5)
        if similar_funnels:
            insights.append({
                "type": "similar_funnels",
                "description": f"Found {len(similar_funnels)}类似funnels",
                "data": similar_funnels
            })
        
        # Get causal chains
        causal_chains = await neo4j.get_causal_chain(f"event_{funnel_id}")
        if causal_chains:
            insights.append({
                "type": "causal_chains",
                "description": f"Found {len(causal_chains)} causal chains",
                "data": causal_chains
            })
        
        # Get revenue trends
        cypher = """
        MATCH (f:Funnel {funnel_id: $funnel_id})-[:GENERATES]->(r:Revenue)
        RETURN r
        ORDER BY r.timestamp DESC
        LIMIT 10
        """
        revenues = await neo4j.query(cypher, {"funnel_id": funnel_id})
        if revenues:
            insights.append({
                "type": "revenue_trends",
                "description": f"Revenue history with {len(revenues)} data points",
                "data": revenues
            })
        
        # Get strategies used
        cypher = """
        MATCH (f:Funnel {funnel_id: $funnel_id})<-[:OPTIMIZED_BY]-(s:Strategy)
        RETURN s
        ORDER BY s.created_at DESC
        """
        strategies = await neo4j.query(cypher, {"funnel_id": funnel_id})
        if strategies:
            insights.append({
                "type": "strategies",
                "description": f"{len(strategies)} strategies applied",
                "data": strategies
            })
        
        # Get associated risks
        cypher = """
        MATCH (f:Funnel {funnel_id: $funnel_id})<-[:CAUSED_BY]-(r:Risk)
        RETURN r
        ORDER BY r.created_at DESC
        """
        risks = await neo4j.query(cypher, {"funnel_id": funnel_id})
        if risks:
            insights.append({
                "type": "risks",
                "description": f"{len(risks)} associated risks",
                "data": risks
            })
        
        tracer.finish_span(trace_parent, "api.get_funnel_insights", True, duration_ms=0)
        
        return InsightResponse(
            success=True,
            insights=insights,
            metadata={"funnel_id": funnel_id, "total_insights": len(insights)},
            trace_id=trace_id
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_funnel_insights_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.get_funnel_insights", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/niche/{niche_id}", response_model=InsightResponse)
async def get_niche_insights(
    niche_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
    qdrant: QdrantClient = Depends(get_qdrant),
    embeddings: EmbeddingGenerator = Depends(get_embeddings),
    tracer: Tracer = Depends(get_tracer)
):
    """Get insights for a niche."""
    trace_parent = tracer.start_span("api.get_niche_insights")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        insights = []
        
        # Get niche data
        niche = await neo4j.get_node(NodeType.NICHE, niche_id)
        if not niche:
            raise HTTPException(status_code=404, detail="Niche not found")
        
        # Get trends
        trends = await neo4j.get_niche_trends(niche_id)
        if trends:
            insights.append({
                "type": "trends",
                "description": f"Niche trends with {len(trends)} data points",
                "data": trends
            })
        
        # Get funnels in this niche
        cypher = """
        MATCH (n:Niche {niche_id: $niche_id})<-[:PART_OF]-(f:Funnel)
        RETURN f
        ORDER BY f.conversion_rate DESC
        LIMIT 10
        """
        funnels = await neo4j.query(cypher, {"niche_id": niche_id})
        if funnels:
            insights.append({
                "type": "top_funnels",
                "description": f"Top {len(funnels)} funnels in this niche",
                "data": funnels
            })
        
        # Get competitors
        cypher = """
        MATCH (n:Niche {niche_id: $niche_id})-[:COMPETES_WITH]->(c:Competitor)
        RETURN c
        ORDER BY c.market_share DESC
        """
        competitors = await neo4j.query(cypher, {"niche_id": niche_id})
        if competitors:
            insights.append({
                "type": "competitors",
                "description": f"{len(competitors)} competitors in this niche",
                "data": competitors
            })
        
        # Get keywords
        cypher = """
        MATCH (n:Niche {niche_id: $niche_id})-[:HAS_TREND]->(k:Keyword)
        RETURN k
        ORDER BY k.trend_score DESC
        LIMIT 20
        """
        keywords = await neo4j.query(cypher, {"niche_id": niche_id})
        if keywords:
            insights.append({
                "type": "keywords",
                "description": f"Top {len(keywords)} keywords in this niche",
                "data": keywords
            })
        
        tracer.finish_span(trace_parent, "api.get_niche_insights", True, duration_ms=0)
        
        return InsightResponse(
            success=True,
            insights=insights,
            metadata={"niche_id": niche_id, "total_insights": len(insights)},
            trace_id=trace_id
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_niche_insights_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.get_niche_insights", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market/{market_id}", response_model=InsightResponse)
async def get_market_insights(
    market_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
    qdrant: QdrantClient = Depends(get_qdrant),
    embeddings: EmbeddingGenerator = Depends(get_embeddings),
    tracer: Tracer = Depends(get_tracer)
):
    """Get insights for a market."""
    trace_parent = tracer.start_span("api.get_market_insights")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        insights = []
        
        # Get market data
        market = await neo4j.get_node(NodeType.MARKET, market_id)
        if not market:
            raise HTTPException(status_code=404, detail="Market not found")
        
        # Get niches in this market
        cypher = """
        MATCH (m:Market {market_id: $market_id})<-[:PART_OF]-(n:Niche)
        RETURN n
        ORDER BY n.market_size DESC
        """
        niches = await neo4j.query(cypher, {"market_id": market_id})
        if niches:
            insights.append({
                "type": "niches",
                "description": f"{len(niches)} niches in this market",
                "data": niches
            })
        
        # Get competitors in this market
        cypher = """
        MATCH (m:Market {market_id: $market_id})<-[:PART_OF]-(c:Competitor)
        RETURN c
        ORDER BY c.market_share DESC
        """
        competitors = await neo4j.query(cypher, {"market_id": market_id})
        if competitors:
            insights.append({
                "type": "competitors",
                "description": f"{len(competitors)} competitors in this market",
                "data": competitors
            })
        
        # Get total revenue
        cypher = """
        MATCH (m:Market {market_id: $market_id})<-[:PART_OF]-(:Niche)<-[:PART_OF]-(:Funnel)-[:GENERATES]->(r:Revenue)
        RETURN sum(r.amount) as total_revenue
        """
        revenue_result = await neo4j.query(cypher, {"market_id": market_id})
        if revenue_result and revenue_result[0].get("total_revenue"):
            insights.append({
                "type": "total_revenue",
                "description": "Total market revenue",
                "data": {"total_revenue": revenue_result[0]["total_revenue"]}
            })
        
        tracer.finish_span(trace_parent, "api.get_market_insights", True, duration_ms=0)
        
        return InsightResponse(
            success=True,
            insights=insights,
            metadata={"market_id": market_id, "total_insights": len(insights)},
            trace_id=trace_id
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_market_insights_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.get_market_insights", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/competitor/{competitor_id}", response_model=InsightResponse)
async def get_competitor_insights(
    competitor_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
    tracer: Tracer = Depends(get_tracer)
):
    """Get insights for a competitor."""
    trace_parent = tracer.start_span("api.get_competitor_insights")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        # Get comprehensive competitor analysis
        analysis = await neo4j.get_competitor_analysis(competitor_id)
        
        insights = []
        
        if analysis.get("niches"):
            insights.append({
                "type": "niches",
                "description": f"Competitor in {len(analysis['niches'])} niches",
                "data": analysis["niches"]
            })
        
        if analysis.get("platforms"):
            insights.append({
                "type": "platforms",
                "description": f"Active on {len(analysis['platforms'])} platforms",
                "data": analysis["platforms"]
            })
        
        if analysis.get("keywords"):
            insights.append({
                "type": "keywords",
                "description": f"Targeting {len(analysis['keywords'])} keywords",
                "data": analysis["keywords"]
            })
        
        tracer.finish_span(trace_parent, "api.get_competitor_insights", True, duration_ms=0)
        
        return InsightResponse(
            success=True,
            insights=insights,
            metadata={"competitor_id": competitor_id, "total_insights": len(insights)},
            trace_id=trace_id
        )
    
    except Exception as e:
        logger.error("get_competitor_insights_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.get_competitor_insights", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
