from neo4j import AsyncGraphDatabase
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
import structlog
from .schema import GraphSchema, NodeType, RelationshipType
from ..utils.config import settings


logger = structlog.get_logger()


class Neo4jClient:
    """Neo4j graph database client."""
    
    def __init__(
        self,
        uri: str = None,
        user: str = None,
        password: str = None,
        database: str = None
    ):
        self.uri = uri or settings.neo4j_uri
        self.user = user or settings.neo4j_user
        self.password = password or settings.neo4j_password
        self.database = database or settings.neo4j_database
        self._driver: Optional[AsyncGraphDatabase.driver] = None
    
    async def connect(self):
        """Connect to Neo4j."""
        self._driver = AsyncGraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password)
        )
        await self._driver.verify_connectivity()
        logger.info("neo4j_connected", uri=self.uri, database=self.database)
    
    async def disconnect(self):
        """Disconnect from Neo4j."""
        if self._driver:
            await self._driver.close()
            logger.info("neo4j_disconnected")
    
    async def initialize_schema(self):
        """Initialize graph schema with constraints and indexes."""
        # Neo4j's driver only accepts one Cypher statement per session.run() -
        # get_schema_cypher() returns them newline-joined, so split and run
        # each individually rather than passing the whole block as one query.
        schema_cypher = GraphSchema.get_schema_cypher()
        async with self._driver.session(database=self.database) as session:
            for statement in schema_cypher.split("\n"):
                statement = statement.strip()
                if statement:
                    await session.run(statement)
        logger.info("neo4j_schema_initialized")
    
    @asynccontextmanager
    async def session(self):
        """Get a Neo4j session."""
        async with self._driver.session(database=self.database) as session:
            yield session
    
    async def create_node(
        self,
        node_type: NodeType,
        properties: Dict[str, Any],
        trace_id: Optional[str] = None
    ) -> str:
        """Create a node in the graph."""
        label = node_type.value
        id_property = self._get_id_property(node_type)
        
        cypher = f"""
        MERGE (n:{label} {{{id_property}: $id}})
        SET n += $properties
        RETURN n.{id_property} as id
        """
        
        node_id = properties.get(id_property)
        async with self.session() as session:
            result = await session.run(
                cypher,
                id=node_id,
                properties=properties
            )
            record = await result.single()
        
        logger.info(
            "node_created",
            node_type=label,
            node_id=node_id,
            trace_id=trace_id
        )
        
        return node_id
    
    async def update_node(
        self,
        node_type: NodeType,
        node_id: str,
        properties: Dict[str, Any],
        trace_id: Optional[str] = None
    ):
        """Update a node in the graph."""
        label = node_type.value
        id_property = self._get_id_property(node_type)
        
        cypher = f"""
        MATCH (n:{label} {{{id_property}: $id}})
        SET n += $properties
        RETURN n
        """
        
        async with self.session() as session:
            await session.run(
                cypher,
                id=node_id,
                properties=properties
            )
        
        logger.info(
            "node_updated",
            node_type=label,
            node_id=node_id,
            trace_id=trace_id
        )
    
    async def get_node(
        self,
        node_type: NodeType,
        node_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a node by ID."""
        label = node_type.value
        id_property = self._get_id_property(node_type)
        
        cypher = f"""
        MATCH (n:{label} {{{id_property}: $id}})
        RETURN n
        """
        
        async with self.session() as session:
            result = await session.run(cypher, id=node_id)
            record = await result.single()
            
            if record:
                return dict(record["n"])
            return None
    
    async def create_relationship(
        self,
        from_type: NodeType,
        from_id: str,
        to_type: NodeType,
        to_id: str,
        rel_type: RelationshipType,
        properties: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ):
        """Create a relationship between two nodes."""
        from_label = from_type.value
        to_label = to_type.value
        from_id_prop = self._get_id_property(from_type)
        to_id_prop = self._get_id_property(to_type)
        rel_label = rel_type.value
        
        props = properties or {}
        
        cypher = f"""
        MATCH (a:{from_label} {{{from_id_prop}: $from_id}})
        MATCH (b:{to_label} {{{to_id_prop}: $to_id}})
        MERGE (a)-[r:{rel_label}]->(b)
        SET r += $properties
        RETURN r
        """
        
        async with self.session() as session:
            await session.run(
                cypher,
                from_id=from_id,
                to_id=to_id,
                properties=props
            )
        
        logger.info(
            "relationship_created",
            from_type=from_label,
            from_id=from_id,
            to_type=to_label,
            to_id=to_id,
            relationship=rel_label,
            trace_id=trace_id
        )
    
    async def query(
        self,
        cypher: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a custom Cypher query."""
        params = parameters or {}
        
        async with self.session() as session:
            result = await session.run(cypher, **params)
            records = await result.data()
        
        return records
    
    async def get_funnel_journey(self, funnel_id: str) -> List[Dict[str, Any]]:
        """Get the user journey for a funnel."""
        cypher = """
        MATCH (f:Funnel {funnel_id: $funnel_id})<-[:INTERACTED_WITH]-(u:User)
        MATCH (u)-[r:INTERACTED_WITH]->(f)
        OPTIONAL MATCH (f)-[:GENERATES]->(rev:Revenue)
        RETURN u, r, rev
        ORDER BY r.timestamp
        """
        
        return await self.query(cypher, {"funnel_id": funnel_id})
    
    async def get_niche_trends(self, niche_id: str) -> List[Dict[str, Any]]:
        """Get trends for a niche."""
        cypher = """
        MATCH (n:Niche {niche_id: $niche_id})-[:HAS_TREND]->(k:Keyword)
        MATCH (n)-[:COMPETES_WITH]->(c:Competitor)
        RETURN n, k, c
        ORDER BY k.trend_score DESC
        """
        
        return await self.query(cypher, {"niche_id": niche_id})
    
    async def get_causal_chain(self, event_id: str) -> List[Dict[str, Any]]:
        """Get causal chain for an event."""
        cypher = """
        MATCH path = (start:Event {event_id: $event_id})-[:CAUSES*]->(end:Event)
        RETURN [node in nodes(path) | node] as chain
        """
        
        return await self.query(cypher, {"event_id": event_id})
    
    async def get_temporal_sequence(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get temporal sequence for an entity."""
        cypher = f"""
        MATCH (e:{entity_type} {{{self._get_id_property_by_type(entity_type)}: $id}})-[:NEXT_STATE*]->(states)
        UNWIND states as state
        RETURN state
        ORDER BY state.timestamp
        LIMIT $limit
        """
        
        return await self.query(cypher, {"id": entity_id, "limit": limit})
    
    async def get_similar_funnels(
        self,
        funnel_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get similar funnels based on niche and strategy."""
        cypher = """
        MATCH (f:Funnel {funnel_id: $funnel_id})
        MATCH (similar:Funnel)
        WHERE similar.niche = f.niche 
        AND similar.strategy = f.strategy
        AND similar.funnel_id <> f.funnel_id
        RETURN similar
        ORDER BY similar.conversion_rate DESC
        LIMIT $limit
        """
        
        return await self.query(cypher, {"funnel_id": funnel_id, "limit": limit})
    
    async def get_competitor_analysis(self, competitor_id: str) -> Dict[str, Any]:
        """Get comprehensive competitor analysis."""
        cypher = """
        MATCH (c:Competitor {competitor_id: $competitor_id})
        OPTIONAL MATCH (c)-[:COMPETES_WITH]->(n:Niche)
        OPTIONAL MATCH (c)-[:PERFORMS_ON]->(p:Platform)
        OPTIONAL MATCH (c)-[:HAS_TREND]->(k:Keyword)
        RETURN c, collect(DISTINCT n) as niches, 
               collect(DISTINCT p) as platforms,
               collect(DISTINCT k) as keywords
        """
        
        result = await self.query(cypher, {"competitor_id": competitor_id})
        return result[0] if result else {}
    
    def _get_id_property(self, node_type: NodeType) -> str:
        """Get the ID property for a node type."""
        mapping = {
            NodeType.USER: "user_id",
            NodeType.FUNNEL: "funnel_id",
            NodeType.PRODUCT: "product_id",
            NodeType.NICHE: "niche_id",
            NodeType.KEYWORD: "keyword",
            NodeType.STRATEGY: "strategy_id",
            NodeType.REVENUE: "revenue_id",
            NodeType.EVENT: "event_id",
            NodeType.ENGINE: "engine_id",
            NodeType.COMPETITOR: "competitor_id",
            NodeType.CONTENT: "content_id",
            NodeType.PLATFORM: "platform_id",
            NodeType.RISK: "risk_id",
            NodeType.FAILURE: "failure_id",
            NodeType.RECOVERY: "recovery_id",
            NodeType.MARKET: "market_id",
            NodeType.SIMULATION: "simulation_id",
        }
        return mapping.get(node_type, "id")
    
    def _get_id_property_by_type(self, node_type: str) -> str:
        """Get the ID property by node type string."""
        type_mapping = {
            "User": "user_id",
            "Funnel": "funnel_id",
            "Product": "product_id",
            "Niche": "niche_id",
            "Keyword": "keyword",
            "Strategy": "strategy_id",
            "Revenue": "revenue_id",
            "Event": "event_id",
            "Engine": "engine_id",
            "Competitor": "competitor_id",
            "Content": "content_id",
            "Platform": "platform_id",
            "Risk": "risk_id",
            "Failure": "failure_id",
            "Recovery": "recovery_id",
            "Market": "market_id",
            "Simulation": "simulation_id",
        }
        return type_mapping.get(node_type, "id")
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
