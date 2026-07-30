from typing import Dict, Any
from datetime import datetime
import structlog
from autonomy_events import EventEnvelope, ConsumeResult, TraceParent
from .base import BaseConsumer
from ..graph import NodeType, RelationshipType


logger = structlog.get_logger()


class GovernanceConsumer(BaseConsumer):
    """Consumer for governance-related events."""
    
    async def handle_event(
        self,
        envelope: EventEnvelope,
        trace_parent: TraceParent
    ) -> ConsumeResult:
        """Handle governance events."""
        event_type = envelope.event_type
        payload = envelope.payload
        trace_id = trace_parent.trace_context.trace_id if trace_parent else None
        
        try:
            if event_type == "governance.request":
                await self._handle_governance_request(payload, trace_id)
            elif event_type == "governance.approved":
                await self._handle_governance_approved(payload, trace_id)
            elif event_type == "governance.rejected":
                await self._handle_governance_rejected(payload, trace_id)
            elif event_type == "governance.emergency_stop":
                await self._handle_emergency_stop(payload, trace_id)
            elif event_type == "governance.override":
                await self._handle_governance_override(payload, trace_id)
            else:
                logger.warning("unknown_governance_event", event_type=event_type)
                return ConsumeResult(
                    success=False,
                    event_id=envelope.event_id,
                    event_type=event_type,
                    error=f"Unknown governance event type: {event_type}"
                )
            
            return ConsumeResult(
                success=True,
                event_id=envelope.event_id,
                event_type=event_type
            )
        
        except Exception as e:
            logger.error("governance_consumer_error", error=str(e))
            return ConsumeResult(
                success=False,
                event_id=envelope.event_id,
                event_type=event_type,
                error=str(e)
            )
    
    async def _handle_governance_request(self, payload: Dict[str, Any], trace_id: str):
        """Handle governance.request event."""
        request_id = payload["request_id"]
        
        # Create event node for request
        properties = {
            "event_id": request_id,
            "event_type": "governance.request",
            "timestamp": payload.get("requested_at", datetime.utcnow().isoformat()),
            "source": payload.get("requester"),
            "payload": payload,
            "correlation_id": trace_id
        }
        
        await self.write_to_graph(NodeType.EVENT, properties, trace_id)
        
        # Link to resource if specified
        if payload.get("resource_id"):
            resource_type = payload.get("resource_type", "funnel")
            node_type = self._map_resource_type_to_node_type(resource_type)
            if node_type:
                await self.write_relationship(
                    NodeType.EVENT, request_id,
                    node_type, payload["resource_id"],
                    RelationshipType.CAUSES.value,
                    trace_id=trace_id
                )
    
    async def _handle_governance_approved(self, payload: Dict[str, Any], trace_id: str):
        """Handle governance.approved event."""
        request_id = payload["request_id"]
        
        # Update event node
        event_properties = {
            "event_id": f"{request_id}_approved",
            "event_type": "governance.approved",
            "timestamp": payload.get("approved_at", datetime.utcnow().isoformat()),
            "source": payload.get("approved_by"),
            "payload": payload,
            "correlation_id": trace_id
        }
        
        await self.write_to_graph(NodeType.EVENT, event_properties, trace_id)
        
        # Link to original request
        await self.write_relationship(
            NodeType.EVENT, f"{request_id}_approved",
            NodeType.EVENT, request_id,
            RelationshipType.RESULTS_IN.value,
            trace_id=trace_id
        )
    
    async def _handle_governance_rejected(self, payload: Dict[str, Any], trace_id: str):
        """Handle governance.rejected event."""
        request_id = payload["request_id"]
        
        # Create risk node for rejection
        risk_id = f"risk_{request_id}"
        risk_properties = {
            "risk_id": risk_id,
            "type": "governance_rejection",
            "severity": payload.get("violation_type", "medium"),
            "description": payload.get("reason"),
            "mitigation": "; ".join(payload.get("suggestions", [])),
            "probability": 1.0,
            "impact": 0.5,
            "created_at": datetime.utcnow().isoformat()
        }
        
        await self.write_to_graph(NodeType.RISK, risk_properties, trace_id)
        
        # Link risk to request
        await self.write_relationship(
            NodeType.RISK, risk_id,
            NodeType.EVENT, request_id,
            RelationshipType.CAUSED_BY.value,
            trace_id=trace_id
        )
    
    async def _handle_emergency_stop(self, payload: Dict[str, Any], trace_id: str):
        """Handle governance.emergency_stop event."""
        # Create failure node
        failure_id = f"failure_emergency_{int(datetime.utcnow().timestamp())}"
        failure_properties = {
            "failure_id": failure_id,
            "type": "emergency_stop",
            "severity": payload.get("severity", "critical"),
            "component": "governance",
            "error_message": payload.get("reason"),
            "timestamp": datetime.utcnow().isoformat(),
            "resolved": False
        }
        
        await self.write_to_graph(NodeType.FAILURE, failure_properties, trace_id)
        
        # Link to affected entities
        for entity_id in payload.get("affected_entities", []):
            await self.write_relationship(
                NodeType.FAILURE, failure_id,
                NodeType.FUNNEL, entity_id,
                RelationshipType.FAILED_BECAUSE.value,
                trace_id=trace_id
            )
    
    async def _handle_governance_override(self, payload: Dict[str, Any], trace_id: str):
        """Handle governance.override event."""
        # Create risk node for override
        risk_id = f"risk_override_{payload['original_request_id']}"
        risk_properties = {
            "risk_id": risk_id,
            "type": "governance_override",
            "severity": "high",
            "description": payload.get("override_reason"),
            "mitigation": "Monitor closely",
            "probability": 0.5,
            "impact": 0.7,
            "created_at": datetime.utcnow().isoformat()
        }
        
        await self.write_to_graph(NodeType.RISK, risk_properties, trace_id)
    
    def _map_resource_type_to_node_type(self, resource_type: str):
        """Map resource type string to NodeType."""
        mapping = {
            "funnel": NodeType.FUNNEL,
            "product": NodeType.PRODUCT,
            "niche": NodeType.NICHE,
            "strategy": NodeType.STRATEGY,
            "content": NodeType.CONTENT
        }
        return mapping.get(resource_type.lower())
