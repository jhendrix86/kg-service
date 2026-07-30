from typing import Dict, Any
from datetime import datetime
import structlog
from autonomy_events import EventEnvelope, ConsumeResult, TraceParent
from .base import BaseConsumer
from ..graph import NodeType, RelationshipType


logger = structlog.get_logger()


class FailureConsumer(BaseConsumer):
    """Consumer for failure-related events."""
    
    async def handle_event(
        self,
        envelope: EventEnvelope,
        trace_parent: TraceParent
    ) -> ConsumeResult:
        """Handle failure events."""
        event_type = envelope.event_type
        payload = envelope.payload
        trace_id = trace_parent.trace_context.trace_id if trace_parent else None
        
        try:
            if event_type == "failure.detected":
                await self._handle_failure_detected(payload, trace_id)
            elif event_type == "failure.recovered":
                await self._handle_failure_recovered(payload, trace_id)
            elif event_type == "failure.retry_scheduled":
                await self._handle_retry_scheduled(payload, trace_id)
            else:
                logger.warning("unknown_failure_event", event_type=event_type)
                return ConsumeResult(
                    success=False,
                    event_id=envelope.event_id,
                    event_type=event_type,
                    error=f"Unknown failure event type: {event_type}"
                )
            
            return ConsumeResult(
                success=True,
                event_id=envelope.event_id,
                event_type=event_type
            )
        
        except Exception as e:
            logger.error("failure_consumer_error", error=str(e))
            return ConsumeResult(
                success=False,
                event_id=envelope.event_id,
                event_type=event_type,
                error=str(e)
            )
    
    async def _handle_failure_detected(self, payload: Dict[str, Any], trace_id: str):
        """Handle failure.detected event."""
        failure_id = payload["failure_id"]
        
        # Create failure node
        properties = {
            "failure_id": failure_id,
            "type": payload.get("failure_type"),
            "severity": payload.get("severity"),
            "component": payload.get("component"),
            "error_message": payload.get("error_message"),
            "error_code": payload.get("error_code"),
            "timestamp": payload.get("detected_at", datetime.utcnow().isoformat()),
            "resolved": False,
            "metadata": payload.get("context", {})
        }
        
        await self.write_to_graph(NodeType.FAILURE, properties, trace_id)
        
        # Link to engine if component is an engine
        component = payload.get("component", "")
        if "engine" in component.lower():
            await self.write_relationship(
                NodeType.FAILURE, failure_id,
                NodeType.ENGINE, component,
                RelationshipType.FAILED_BECAUSE.value,
                trace_id=trace_id
            )
        
        # Link to affected operations
        for operation in payload.get("affected_operations", []):
            # Try to find related funnel or entity
            if "funnel" in operation.lower():
                funnel_id = operation.split(":")[-1] if ":" in operation else operation
                await self.write_relationship(
                    NodeType.FAILURE, failure_id,
                    NodeType.FUNNEL, funnel_id,
                    RelationshipType.FAILED_BECAUSE.value,
                    trace_id=trace_id
                )
    
    async def _handle_failure_recovered(self, payload: Dict[str, Any], trace_id: str):
        """Handle failure.recovered event."""
        failure_id = payload["failure_id"]
        
        # Update failure node
        properties = {
            "resolved": True,
            "recovered_at": payload.get("recovered_at", datetime.utcnow().isoformat()),
            "recovered_by": payload.get("recovered_by")
        }
        
        await self.neo4j.update_node(NodeType.FAILURE, failure_id, properties, trace_id)
        
        # Create recovery node
        recovery_id = payload.get("recovery_id", f"recovery_{failure_id}")
        recovery_properties = {
            "recovery_id": recovery_id,
            "type": payload.get("recovery_type"),
            "failure_id": failure_id,
            "actions": payload.get("recovery_actions", []),
            "duration_seconds": payload.get("downtime_seconds", 0),
            "success": not payload.get("data_loss", False),
            "timestamp": payload.get("recovered_at", datetime.utcnow().isoformat())
        }
        
        await self.write_to_graph(NodeType.RECOVERY, recovery_properties, trace_id)
        
        # Link recovery to failure
        await self.write_relationship(
            NodeType.RECOVERY, recovery_id,
            NodeType.FAILURE, failure_id,
            RelationshipType.RECOVERED_BY.value,
            trace_id=trace_id
        )
    
    async def _handle_retry_scheduled(self, payload: Dict[str, Any], trace_id: str):
        """Handle failure.retry_scheduled event."""
        failure_id = payload["failure_id"]
        
        # Create event node for retry
        event_id = f"retry_{failure_id}_{payload['retry_attempt']}"
        properties = {
            "event_id": event_id,
            "event_type": "failure.retry_scheduled",
            "timestamp": payload.get("scheduled_at", datetime.utcnow().isoformat()),
            "source": payload.get("scheduled_by"),
            "payload": payload,
            "correlation_id": trace_id
        }
        
        await self.write_to_graph(NodeType.EVENT, properties, trace_id)
        
        # Link to failure
        await self.write_relationship(
            NodeType.EVENT, event_id,
            NodeType.FAILURE, failure_id,
            RelationshipType.RESULTS_IN.value,
            trace_id=trace_id
        )
