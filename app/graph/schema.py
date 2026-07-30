from typing import List, Dict, Any
from enum import Enum


class NodeType(Enum):
    """Neo4j node types."""
    USER = "User"
    FUNNEL = "Funnel"
    PRODUCT = "Product"
    NICHE = "Niche"
    KEYWORD = "Keyword"
    STRATEGY = "Strategy"
    REVENUE = "Revenue"
    EVENT = "Event"
    ENGINE = "Engine"
    COMPETITOR = "Competitor"
    CONTENT = "Content"
    PLATFORM = "Platform"
    RISK = "Risk"
    FAILURE = "Failure"
    RECOVERY = "Recovery"
    MARKET = "Market"
    SIMULATION = "Simulation"


class RelationshipType(Enum):
    """Neo4j relationship types."""
    INTERACTED_WITH = "INTERACTED_WITH"
    GENERATES = "GENERATES"
    OPTIMIZED_BY = "OPTIMIZED_BY"
    HAS_TREND = "HAS_TREND"
    COMPETES_WITH = "COMPETES_WITH"
    PERFORMS_ON = "PERFORMS_ON"
    CAUSED_BY = "CAUSED_BY"
    LEADS_TO = "LEADS_TO"
    VERSION_OF = "VERSION_OF"
    SIMULATED_BY = "SIMULATED_BY"
    FAILED_BECAUSE = "FAILED_BECAUSE"
    RECOVERED_BY = "RECOVERED_BY"
    PART_OF = "PART_OF"
    RUNS_ON = "RUNS_ON"
    # Temporal edges
    NEXT_STATE = "NEXT_STATE"
    PREVIOUS_STATE = "PREVIOUS_STATE"
    AT_TIME = "AT_TIME"
    # Causal edges
    CAUSES = "CAUSES"
    RESULTS_IN = "RESULTS_IN"


class GraphSchema:
    """Neo4j graph schema definition and management."""
    
    @staticmethod
    def get_node_constraints() -> List[Dict[str, Any]]:
        """Get unique constraints for nodes."""
        return [
            {
                "label": NodeType.USER.value,
                "property": "user_id",
                "name": "user_id_unique"
            },
            {
                "label": NodeType.FUNNEL.value,
                "property": "funnel_id",
                "name": "funnel_id_unique"
            },
            {
                "label": NodeType.PRODUCT.value,
                "property": "product_id",
                "name": "product_id_unique"
            },
            {
                "label": NodeType.NICHE.value,
                "property": "niche_id",
                "name": "niche_id_unique"
            },
            {
                "label": NodeType.KEYWORD.value,
                "property": "keyword",
                "name": "keyword_unique"
            },
            {
                "label": NodeType.STRATEGY.value,
                "property": "strategy_id",
                "name": "strategy_id_unique"
            },
            {
                "label": NodeType.REVENUE.value,
                "property": "revenue_id",
                "name": "revenue_id_unique"
            },
            {
                "label": NodeType.EVENT.value,
                "property": "event_id",
                "name": "event_id_unique"
            },
            {
                "label": NodeType.ENGINE.value,
                "property": "engine_id",
                "name": "engine_id_unique"
            },
            {
                "label": NodeType.COMPETITOR.value,
                "property": "competitor_id",
                "name": "competitor_id_unique"
            },
            {
                "label": NodeType.CONTENT.value,
                "property": "content_id",
                "name": "content_id_unique"
            },
            {
                "label": NodeType.PLATFORM.value,
                "property": "platform_id",
                "name": "platform_id_unique"
            },
            {
                "label": NodeType.RISK.value,
                "property": "risk_id",
                "name": "risk_id_unique"
            },
            {
                "label": NodeType.FAILURE.value,
                "property": "failure_id",
                "name": "failure_id_unique"
            },
            {
                "label": NodeType.RECOVERY.value,
                "property": "recovery_id",
                "name": "recovery_id_unique"
            },
            {
                "label": NodeType.MARKET.value,
                "property": "market_id",
                "name": "market_id_unique"
            },
            {
                "label": NodeType.SIMULATION.value,
                "property": "simulation_id",
                "name": "simulation_id_unique"
            },
        ]
    
    @staticmethod
    def get_node_indexes() -> List[Dict[str, Any]]:
        """Get indexes for nodes."""
        return [
            {
                "label": NodeType.USER.value,
                "properties": ["email", "created_at"],
                "name": "user_email_idx"
            },
            {
                "label": NodeType.FUNNEL.value,
                "properties": ["niche", "created_at", "status"],
                "name": "funnel_niche_idx"
            },
            {
                "label": NodeType.PRODUCT.value,
                "properties": ["category", "created_at"],
                "name": "product_category_idx"
            },
            {
                "label": NodeType.NICHE.value,
                "properties": ["name", "trend_score"],
                "name": "niche_trend_idx"
            },
            {
                "label": NodeType.KEYWORD.value,
                "properties": ["search_volume", "competition"],
                "name": "keyword_volume_idx"
            },
            {
                "label": NodeType.COMPETITOR.value,
                "properties": ["name", "market_share"],
                "name": "competitor_market_idx"
            },
            {
                "label": NodeType.CONTENT.value,
                "properties": ["type", "created_at", "performance_score"],
                "name": "content_performance_idx"
            },
        ]
    
    @staticmethod
    def get_schema_cypher() -> str:
        """Generate Cypher statements to create schema."""
        statements = []
        
        # Create constraints
        for constraint in GraphSchema.get_node_constraints():
            statements.append(
                f"CREATE CONSTRAINT {constraint['name']} IF NOT EXISTS "
                f"FOR (n:{constraint['label']}) REQUIRE n.{constraint['property']} IS UNIQUE"
            )
        
        # Create indexes
        for index in GraphSchema.get_node_indexes():
            props = ", ".join([f"n.{p}" for p in index['properties']])
            statements.append(
                f"CREATE INDEX {index['name']} IF NOT EXISTS "
                f"FOR (n:{index['label']}) ON ({props})"
            )
        
        return "\n".join(statements)
    
    @staticmethod
    def get_node_properties(node_type: NodeType) -> Dict[str, str]:
        """Get expected properties for a node type."""
        properties = {
            NodeType.USER: {
                "user_id": "string",
                "email": "string",
                "created_at": "datetime",
                "lifecycle_stage": "string",
                "total_revenue": "float",
                "funnel_count": "int",
                "metadata": "map"
            },
            NodeType.FUNNEL: {
                "funnel_id": "string",
                "niche": "string",
                "strategy": "string",
                "status": "string",
                "created_at": "datetime",
                "launched_at": "datetime",
                "total_visitors": "int",
                "total_conversions": "int",
                "total_revenue": "float",
                "conversion_rate": "float",
                "governance_status": "string",
                "metadata": "map"
            },
            NodeType.PRODUCT: {
                "product_id": "string",
                "name": "string",
                "category": "string",
                "price": "float",
                "created_at": "datetime",
                "total_sales": "int",
                "total_revenue": "float",
                "platform": "string",
                "metadata": "map"
            },
            NodeType.NICHE: {
                "niche_id": "string",
                "name": "string",
                "category": "string",
                "trend_score": "float",
                "competition_level": "string",
                "market_size": "float",
                "created_at": "datetime",
                "metadata": "map"
            },
            NodeType.KEYWORD: {
                "keyword": "string",
                "search_volume": "int",
                "competition": "float",
                "cpc": "float",
                "trend_score": "float",
                "created_at": "datetime",
                "metadata": "map"
            },
            NodeType.STRATEGY: {
                "strategy_id": "string",
                "name": "string",
                "type": "string",
                "parameters": "map",
                "success_rate": "float",
                "created_at": "datetime",
                "metadata": "map"
            },
            NodeType.REVENUE: {
                "revenue_id": "string",
                "amount": "float",
                "currency": "string",
                "source": "string",
                "funnel_id": "string",
                "product_id": "string",
                "timestamp": "datetime",
                "metadata": "map"
            },
            NodeType.EVENT: {
                "event_id": "string",
                "event_type": "string",
                "timestamp": "datetime",
                "source": "string",
                "payload": "map",
                "correlation_id": "string",
                "causation_id": "string",
                "metadata": "map"
            },
            NodeType.ENGINE: {
                "engine_id": "string",
                "engine_type": "string",
                "status": "string",
                "health_score": "float",
                "last_heartbeat": "datetime",
                "metadata": "map"
            },
            NodeType.COMPETITOR: {
                "competitor_id": "string",
                "name": "string",
                "market_share": "float",
                "products": "list",
                "strategies": "list",
                "strengths": "list",
                "weaknesses": "list",
                "created_at": "datetime",
                "metadata": "map"
            },
            NodeType.CONTENT: {
                "content_id": "string",
                "type": "string",
                "title": "string",
                "platform": "string",
                "performance_score": "float",
                "engagement_metrics": "map",
                "created_at": "datetime",
                "metadata": "map"
            },
            NodeType.PLATFORM: {
                "platform_id": "string",
                "name": "string",
                "type": "string",
                "api_status": "string",
                "rate_limit": "int",
                "created_at": "datetime",
                "metadata": "map"
            },
            NodeType.RISK: {
                "risk_id": "string",
                "type": "string",
                "severity": "string",
                "description": "string",
                "mitigation": "string",
                "probability": "float",
                "impact": "float",
                "created_at": "datetime",
                "metadata": "map"
            },
            NodeType.FAILURE: {
                "failure_id": "string",
                "type": "string",
                "severity": "string",
                "component": "string",
                "error_message": "string",
                "timestamp": "datetime",
                "resolved": "boolean",
                "metadata": "map"
            },
            NodeType.RECOVERY: {
                "recovery_id": "string",
                "type": "string",
                "failure_id": "string",
                "actions": "list",
                "duration_seconds": "int",
                "success": "boolean",
                "timestamp": "datetime",
                "metadata": "map"
            },
            NodeType.MARKET: {
                "market_id": "string",
                "name": "string",
                "size": "float",
                "growth_rate": "float",
                "segments": "list",
                "trends": "list",
                "created_at": "datetime",
                "metadata": "map"
            },
            NodeType.SIMULATION: {
                "simulation_id": "string",
                "type": "string",
                "parameters": "map",
                "results": "map",
                "confidence": "float",
                "created_at": "datetime",
                "metadata": "map"
            },
        }
        
        return properties.get(node_type, {})
