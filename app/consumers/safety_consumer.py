from typing import Dict, Any
from datetime import datetime
import structlog
from autonomy_events import EventEnvelope, ConsumeResult, TraceParent
from .base import BaseConsumer
from ..graph import NodeType, RelationshipType


logger = structlog.get_logger()


class SafetyConsumer(BaseConsumer):
    """Consumer for safety-related events."""
    
    async def handle_event(
        self,
        envelope: EventEnvelope,
        trace_parent: TraceParent
    ) -> ConsumeResult:
        """Handle safety events."""
        event_type = envelope.event_type
        payload = envelope.payload
        trace_id = trace_parent.trace_context.trace_id if trace_parent else None
        
        try:
            if event_type == "safety.violation_detected":
                await self._handle_violation_detected(payload, trace_id)
            elif event_type == "safety.blocked_action":
                await self._handle_blocked_action(payload, trace_id)
            elif event_type == "safety.rollback_triggered":
                await self._handle_rollback_triggered(payload, trace_id)
            else:
                logger.warning("unknown_safety_event", event_type=event_type)
                return ConsumeResult(
                    success=False,
                    event_id=envelope.event_id,
                    event_type=event_type,
                    error=f"Unknown safety event type: {event_type}"
                )
            
            return ConsumeResult(
                success=True,
                event_id=envelope.event_id,
                event_type=event_type
            )
        
        except Exception as e:
            logger.error("safety_consumer_error", error=str(e))
            return ConsumeResult(
                success=False,
                event_id=envelope.event_id,
                event_type=event_type,
                error=str(e)
            )
    
    async def _handle_violation_detected(self, payload: Dict[str, Any], trace_id: str):
        """Handle safety.violation_detected event."""
        violation_id = f"violation_{int(datetime.utcnow().timestamp())}"
        
        # Create risk node for violation
        properties = {
            "risk_id": violation_id,
            "type": payload.get("violation_type"),
            "severity": payload.get("severity"),
            "description": f"Violated rule: {payload.get('violated_rule')}",
            "mitigation": "; ".join(payload.get("suggested_actions", [])),
            "probability": 1.0,
            "impact": self._severity_to_impact(payload.get("severity")),
            "created_at": datetime.utcnow().isoformat()
        }
        
        await self.write_to_graph(NodeType.RISK, properties, trace_id)
        
        # Link to entity that caused violation
        entity_type = payload.get("entity_type")
        entity_id = payload.get("entity_id")
        node_type = self._map_entity_type_to_node_type(entity_type)
        if node_type:
            await self.write_relationship(
                NodeType.RISK, violation_id,
                node_type, entity_id,
                RelationshipType.CAUSED_BY.value,
                trace_id=trace_id
            )
        
        # Create event node
        event_properties = {
            "event_id": f"event_{violation_id}",
            "event_type": "safety.violation_detected",
            "timestamp": payload.get("detected_at", datetime.utcnow().isoformat()),
            "source": payload.get("detected_by"),
            "payload": payload,
            "correlation_id": trace_id
        }
        
        await self.write_to_graph(NodeType.EVENT, event_properties, trace_id)
    
    async def _handle_blocked_action(self, payload: Dict[str, Any], trace_id: str):
        """Handle safety.blocked_action event."""
        blocked_id = f"blocked_{int(datetime.utcnow().timestamp())}"
        
        # Create event node for blocked action
        properties = {
            "event_id": blocked_id,
            "event_type": "safety.blocked_action",
            "timestamp": payload.get("blocked_at", datetime.utcnow().isoformat()),
            "source": payload.get("blocked_by"),
            "payload": payload,
            "correlation_id": trace_id
        }
        
        await self.write_to_graph(NodeType.EVENT, properties, trace_id)
        
        # Link to requester
        requester = payload.get("requester")
        if requester:
            await self.write_relationship(
                NodeType.EVENT, blocked_id,
                NodeType.ENGINE, requester,
                RelationshipType.CAUSED_BY.value,
                trace_id=trace_id
            )
    
    async def _handle_rollback_triggered(self, payload: Dict[str, Any], trace_id: str):
        """Handle safety.rollback_triggered event."""
        rollback_id = f"rollback_{int(datetime.utcnow().timestamp())}"
        
        # Create recovery node for rollback
        properties = {
            "recovery_id": rollback_id,
            "type": payload.get("rollback_type"),
            "failure_id": None,
            "actions": [payload.get("reason")],
            "duration_seconds": payload.get("estimated_duration", 0),
            "success": None,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.write_to_graph(NodeType.RECOVERY, properties, trace_id)
        
        # Link to affected entities
        for entity_id in payload.get("affected_entities", []):
            await self.write_relationship(
                NodeType.RECOVERY, rollback_id,
                NodeType.FUNNEL, entity_id,
                RelationshipType.RECOVERED_BY.value,
                trace_id=trace_id
            )
    
    def _map_entity_type_to_node_type(self, entity_type: str):
        """Map entity type string to NodeType."""
        mapping = {
            "funnel": NodeType.FUNNEL,
            "product": NodeType.PRODUCT,
            "content": NodeType.CONTENT,
            "strategy": NodeType.STRATEGY
        }
        return mapping.get(entity_type.lower())
    
    def _severity_to_impact(self, severity: str) -> float:
        """Convert severity to impact score."""
        mapping = {
            "low": 0.2,
            "medium": 0.5,
            "high": 0.8,
            "critical": 1.0
        }
        return mapping.get(severity.lower(), 0.5)
