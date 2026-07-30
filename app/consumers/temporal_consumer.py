from typing import Dict, Any
from datetime import datetime
import structlog
from autonomy_events import EventEnvelope, ConsumeResult, TraceParent
from .base import BaseConsumer
from ..graph import NodeType, RelationshipType


logger = structlog.get_logger()


class TemporalConsumer(BaseConsumer):
    """Consumer for temporal and causal events."""
    
    async def handle_event(
        self,
        envelope: EventEnvelope,
        trace_parent: TraceParent
    ) -> ConsumeResult:
        """Handle temporal events."""
        event_type = envelope.event_type
        payload = envelope.payload
        trace_id = trace_parent.trace_context.trace_id if trace_parent else None
        
        try:
            if event_type == "temporal.snapshot":
                await self._handle_temporal_snapshot(payload, trace_id)
            elif event_type == "causal.chain_detected":
                await self._handle_causal_chain(payload, trace_id)
            else:
                logger.warning("unknown_temporal_event", event_type=event_type)
                return ConsumeResult(
                    success=False,
                    event_id=envelope.event_id,
                    event_type=event_type,
                    error=f"Unknown temporal event type: {event_type}"
                )
            
            return ConsumeResult(
                success=True,
                event_id=envelope.event_id,
                event_type=event_type
            )
        
        except Exception as e:
            logger.error("temporal_consumer_error", error=str(e))
            return ConsumeResult(
                success=False,
                event_id=envelope.event_id,
                event_type=event_type,
                error=str(e)
            )
    
    async def _handle_temporal_snapshot(self, payload: Dict[str, Any], trace_id: str):
        """Handle temporal.snapshot event."""
        snapshot_id = payload["snapshot_id"]
        entity_type = payload["entity_type"]
        entity_id = payload["entity_id"]
        snapshot_type = payload["snapshot_type"]
        
        # Map entity type to NodeType
        node_type = self._map_entity_type_to_node_type(entity_type)
        if not node_type:
            logger.warning("unknown_entity_type_in_snapshot", entity_type=entity_type)
            return
        
        # Create simulation node for snapshot
        properties = {
            "simulation_id": snapshot_id,
            "type": f"snapshot_{snapshot_type}",
            "parameters": {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "snapshot_type": snapshot_type
            },
            "results": {
                "state_data": payload.get("state_data", {}),
                "metrics_data": payload.get("metrics_data", {}),
                "config_data": payload.get("config_data", {})
            },
            "confidence": 1.0,
            "created_at": payload.get("captured_at", datetime.utcnow().isoformat())
        }
        
        await self.write_to_graph(NodeType.SIMULATION, properties, trace_id)
        
        # Link simulation to entity
        await self.write_relationship(
            NodeType.SIMULATION, snapshot_id,
            node_type, entity_id,
            RelationshipType.SIMULATED_BY.value,
            trace_id=trace_id
        )
        
        # Create temporal edge to previous snapshot if available
        version = payload.get("version")
        if version and "." in version:
            # Try to find previous version
            parts = version.split(".")
            if len(parts) >= 2:
                major, minor = parts[0], parts[1]
                if minor > "0":
                    prev_version = f"{major}.{int(minor) - 1}"
                    # In a real implementation, you'd query for the previous snapshot
                    # For now, we'll create a placeholder relationship
                    pass
        
        # Create event node
        event_properties = {
            "event_id": f"event_{snapshot_id}",
            "event_type": "temporal.snapshot",
            "timestamp": payload.get("captured_at", datetime.utcnow().isoformat()),
            "source": payload.get("captured_by"),
            "payload": payload,
            "correlation_id": trace_id
        }
        
        await self.write_to_graph(NodeType.EVENT, event_properties, trace_id)
    
    async def _handle_causal_chain(self, payload: Dict[str, Any], trace_id: str):
        """Handle causal.chain_detected event."""
        chain_id = payload["chain_id"]
        chain_type = payload["chain_type"]
        
        # Create strategy node for causal chain
        properties = {
            "strategy_id": chain_id,
            "name": f"causal_chain_{chain_type}",
            "type": "causal_chain",
            "parameters": {
                "chain_type": chain_type,
                "chain_length": payload.get("chain_length"),
                "confidence": payload.get("confidence")
            },
            "success_rate": payload.get("confidence", 0.0),
            "created_at": payload.get("detected_at", datetime.utcnow().isoformat())
        }
        
        await self.write_to_graph(NodeType.STRATEGY, properties, trace_id)
        
        # Link events in the chain
        events = payload.get("events", [])
        for i, event in enumerate(events):
            event_id = event.get("id")
            if event_id:
                await self.write_relationship(
                    NodeType.STRATEGY, chain_id,
                    NodeType.EVENT, event_id,
                    RelationshipType.CAUSES.value,
                    trace_id=trace_id
                )
                
                # Link to next event in chain
                if i < len(events) - 1:
                    next_event_id = events[i + 1].get("id")
                    if next_event_id:
                        await self.write_relationship(
                            NodeType.EVENT, event_id,
                            NodeType.EVENT, next_event_id,
                            RelationshipType.LEADS_TO.value,
                            trace_id=trace_id
                        )
        
        # Link root and leaf events
        root_event_id = payload.get("root_event_id")
        leaf_event_id = payload.get("leaf_event_id")
        
        if root_event_id:
            await self.write_relationship(
                NodeType.STRATEGY, chain_id,
                NodeType.EVENT, root_event_id,
                RelationshipType.CAUSES.value,
                trace_id=trace_id
            )
        
        if leaf_event_id:
            await self.write_relationship(
                NodeType.EVENT, leaf_event_id,
                NodeType.STRATEGY, chain_id,
                RelationshipType.RESULTS_IN.value,
                trace_id=trace_id
            )
        
        # Store embedding for chain insights
        suggested_actions = payload.get("suggested_actions", [])
        if suggested_actions:
            actions_text = " ".join(suggested_actions)
            await self.write_embedding(
                "strategies",
                chain_id,
                actions_text,
                {"chain_type": chain_type, "actionable": payload.get("actionable")},
                trace_id
            )
    
    def _map_entity_type_to_node_type(self, entity_type: str):
        """Map entity type string to NodeType."""
        mapping = {
            "funnel": NodeType.FUNNEL,
            "product": NodeType.PRODUCT,
            "niche": NodeType.NICHE,
            "user": NodeType.USER,
            "strategy": NodeType.STRATEGY,
            "engine": NodeType.ENGINE
        }
        return mapping.get(entity_type.lower())
