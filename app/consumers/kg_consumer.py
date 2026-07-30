from typing import Dict, Any
from datetime import datetime
import structlog
from autonomy_events import EventEnvelope, ConsumeResult, TraceParent
from .base import BaseConsumer
from ..graph import NodeType, RelationshipType


logger = structlog.get_logger()


class KGConsumer(BaseConsumer):
    """Consumer for knowledge graph events."""
    
    async def handle_event(
        self,
        envelope: EventEnvelope,
        trace_parent: TraceParent
    ) -> ConsumeResult:
        """Handle KG events."""
        event_type = envelope.event_type
        payload = envelope.payload
        trace_id = trace_parent.trace_context.trace_id if trace_parent else None
        
        try:
            if event_type == "kg.entity_created":
                await self._handle_entity_created(payload, trace_id)
            elif event_type == "kg.relationship_created":
                await self._handle_relationship_created(payload, trace_id)
            elif event_type == "kg.pattern_detected":
                await self._handle_pattern_detected(payload, trace_id)
            elif event_type == "kg.insight_generated":
                await self._handle_insight_generated(payload, trace_id)
            elif event_type == "kg.anomaly_detected":
                await self._handle_anomaly_detected(payload, trace_id)
            else:
                logger.warning("unknown_kg_event", event_type=event_type)
                return ConsumeResult(
                    success=False,
                    event_id=envelope.event_id,
                    event_type=event_type,
                    error=f"Unknown KG event type: {event_type}"
                )
            
            return ConsumeResult(
                success=True,
                event_id=envelope.event_id,
                event_type=event_type
            )
        
        except Exception as e:
            logger.error("kg_consumer_error", error=str(e))
            return ConsumeResult(
                success=False,
                event_id=envelope.event_id,
                event_type=event_type,
                error=str(e)
            )
    
    async def _handle_entity_created(self, payload: Dict[str, Any], trace_id: str):
        """Handle kg.entity_created event."""
        entity_type = payload["entity_type"]
        entity_id = payload["entity_id"]
        
        # Map entity type to NodeType
        node_type = self._map_entity_type_to_node_type(entity_type)
        if not node_type:
            logger.warning("unknown_entity_type", entity_type=entity_type)
            return
        
        # Create/update node
        properties = {
            **payload.get("attributes", {}),
            "created_at": payload.get("created_at", datetime.utcnow().isoformat()),
            "source": payload.get("source"),
            "confidence": payload.get("confidence", 1.0),
            "metadata": payload.get("metadata", {})
        }
        
        # Add ID property based on node type
        id_property = self._get_id_property_for_type(node_type)
        properties[id_property] = entity_id
        
        await self.write_to_graph(node_type, properties, trace_id)
        
        # Store embedding for certain entity types
        if entity_type in ["user", "product", "niche", "competitor", "content"]:
            text = self._extract_text_for_embedding(entity_type, properties)
            if text:
                await self.write_embedding(
                    entity_type + "s" if entity_type != "user" else "users",
                    entity_id,
                    text,
                    {"entity_type": entity_type, "source": payload.get("source")},
                    trace_id
                )
    
    async def _handle_relationship_created(self, payload: Dict[str, Any], trace_id: str):
        """Handle kg.relationship_created event."""
        from_type = payload["from_entity_type"]
        from_id = payload["from_entity_id"]
        to_type = payload["to_entity_type"]
        to_id = payload["to_entity_id"]
        rel_type = payload["relationship_type"]
        
        from_node_type = self._map_entity_type_to_node_type(from_type)
        to_node_type = self._map_entity_type_to_node_type(to_type)
        
        if not from_node_type or not to_node_type:
            logger.warning("unknown_entity_type_in_relationship", from_type=from_type, to_type=to_type)
            return
        
        properties = {
            **payload.get("attributes", {}),
            "created_at": payload.get("created_at", datetime.utcnow().isoformat()),
            "weight": payload.get("weight", 1.0),
            "metadata": payload.get("metadata", {})
        }
        
        await self.write_relationship(
            from_node_type, from_id,
            to_node_type, to_id,
            rel_type,
            properties,
            trace_id
        )
    
    async def _handle_pattern_detected(self, payload: Dict[str, Any], trace_id: str):
        """Handle kg.pattern_detected event."""
        pattern_id = f"pattern_{int(datetime.utcnow().timestamp())}"
        
        # Create strategy node for pattern
        properties = {
            "strategy_id": pattern_id,
            "name": f"pattern_{payload['pattern_type']}",
            "type": "pattern",
            "parameters": payload.get("pattern_data", {}),
            "success_rate": payload.get("confidence", 0.0),
            "created_at": datetime.utcnow().isoformat()
        }
        
        await self.write_to_graph(NodeType.STRATEGY, properties, trace_id)
        
        # Link to entities involved in pattern
        for entity in payload.get("entities", []):
            entity_type = entity.get("type")
            entity_id = entity.get("id")
            node_type = self._map_entity_type_to_node_type(entity_type)
            if node_type:
                await self.write_relationship(
                    NodeType.STRATEGY, pattern_id,
                    node_type, entity_id,
                    RelationshipType.SIMULATED_BY.value,
                    trace_id=trace_id
                )
    
    async def _handle_insight_generated(self, payload: Dict[str, Any], trace_id: str):
        """Handle kg.insight_generated event."""
        insight_id = f"insight_{int(datetime.utcnow().timestamp())}"
        
        # Create event node for insight
        properties = {
            "event_id": insight_id,
            "event_type": "kg.insight_generated",
            "timestamp": payload.get("generated_at", datetime.utcnow().isoformat()),
            "source": payload.get("generated_by"),
            "payload": payload,
            "correlation_id": trace_id
        }
        
        await self.write_to_graph(NodeType.EVENT, properties, trace_id)
        
        # Store insight embedding
        insight_text = payload.get("value", "")
        if insight_text:
            await self.write_embedding(
                "strategies",
                insight_id,
                insight_text,
                {"insight_type": payload.get("insight_type"), "priority": payload.get("priority")},
                trace_id
            )
    
    async def _handle_anomaly_detected(self, payload: Dict[str, Any], trace_id: str):
        """Handle kg.anomaly_detected event."""
        anomaly_id = f"anomaly_{int(datetime.utcnow().timestamp())}"
        
        # Create risk node for anomaly
        properties = {
            "risk_id": anomaly_id,
            "type": payload.get("anomaly_type"),
            "severity": payload.get("severity"),
            "description": f"Anomaly detected in {payload.get('anomaly_type')}",
            "mitigation": "Investigate and address",
            "probability": 0.8,
            "impact": 0.6,
            "created_at": datetime.utcnow().isoformat()
        }
        
        await self.write_to_graph(NodeType.RISK, properties, trace_id)
        
        # Link to affected entities
        for entity in payload.get("entities", []):
            entity_type = entity.get("type")
            entity_id = entity.get("id")
            node_type = self._map_entity_type_to_node_type(entity_type)
            if node_type:
                await self.write_relationship(
                    NodeType.RISK, anomaly_id,
                    node_type, entity_id,
                    RelationshipType.CAUSED_BY.value,
                    trace_id=trace_id
                )
    
    def _map_entity_type_to_node_type(self, entity_type: str):
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
    
    def _get_id_property_for_type(self, node_type: NodeType):
        """Get the ID property for a node type."""
        from ..graph.client import Neo4jClient
        client = Neo4jClient()
        return client._get_id_property(node_type)
    
    def _extract_text_for_embedding(self, entity_type: str, properties: Dict[str, Any]) -> str:
        """Extract text for embedding generation."""
        parts = []
        
        if entity_type == "user":
            parts.extend([
                properties.get("email", ""),
                properties.get("lifecycle_stage", ""),
                str(properties.get("total_revenue", 0))
            ])
        elif entity_type == "product":
            parts.extend([
                properties.get("name", ""),
                properties.get("category", ""),
                str(properties.get("price", 0))
            ])
        elif entity_type == "niche":
            parts.extend([
                properties.get("name", ""),
                properties.get("category", ""),
                str(properties.get("market_size", 0))
            ])
        elif entity_type == "competitor":
            parts.extend([
                properties.get("name", ""),
                " ".join(properties.get("products", [])),
                str(properties.get("market_share", 0))
            ])
        elif entity_type == "content":
            parts.extend([
                properties.get("title", ""),
                properties.get("type", ""),
                properties.get("body", "")
            ])
        
        return " ".join(filter(None, parts))
