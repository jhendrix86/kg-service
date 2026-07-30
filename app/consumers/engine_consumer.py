from typing import Dict, Any
from datetime import datetime
import structlog
from autonomy_events import EventEnvelope, ConsumeResult, TraceParent
from .base import BaseConsumer
from ..graph import NodeType, RelationshipType


logger = structlog.get_logger()


class EngineConsumer(BaseConsumer):
    """Consumer for engine health events."""
    
    async def handle_event(
        self,
        envelope: EventEnvelope,
        trace_parent: TraceParent
    ) -> ConsumeResult:
        """Handle engine events."""
        event_type = envelope.event_type
        payload = envelope.payload
        trace_id = trace_parent.trace_context.trace_id if trace_parent else None
        
        try:
            if event_type == "engine.health_report":
                await self._handle_health_report(payload, trace_id)
            elif event_type == "engine.degraded":
                await self._handle_engine_degraded(payload, trace_id)
            elif event_type == "engine.recovered":
                await self._handle_engine_recovered(payload, trace_id)
            else:
                logger.warning("unknown_engine_event", event_type=event_type)
                return ConsumeResult(
                    success=False,
                    event_id=envelope.event_id,
                    event_type=event_type,
                    error=f"Unknown engine event type: {event_type}"
                )
            
            return ConsumeResult(
                success=True,
                event_id=envelope.event_id,
                event_type=event_type
            )
        
        except Exception as e:
            logger.error("engine_consumer_error", error=str(e))
            return ConsumeResult(
                success=False,
                event_id=envelope.event_id,
                event_type=event_type,
                error=str(e)
            )
    
    async def _handle_health_report(self, payload: Dict[str, Any], trace_id: str):
        """Handle engine.health_report event."""
        engine_id = payload["engine_id"]
        
        # Create or update engine node
        properties = {
            "engine_id": engine_id,
            "engine_type": payload.get("engine_type"),
            "status": payload.get("status"),
            "health_score": self._calculate_health_score(payload),
            "last_heartbeat": payload.get("reported_at", datetime.utcnow().isoformat()),
            "cpu_usage": payload.get("cpu_usage", 0.0),
            "memory_usage": payload.get("memory_usage", 0.0),
            "active_connections": payload.get("active_connections", 0),
            "queue_depth": payload.get("queue_depth", 0),
            "error_rate": payload.get("error_rate", 0.0),
            "latency_ms": payload.get("latency_ms", 0.0),
            "throughput": payload.get("throughput", 0.0),
            "metadata": payload.get("custom_metrics", {})
        }
        
        await self.write_to_graph(NodeType.ENGINE, properties, trace_id)
    
    async def _handle_engine_degraded(self, payload: Dict[str, Any], trace_id: str):
        """Handle engine.degraded event."""
        engine_id = payload["engine_id"]
        
        # Update engine node
        properties = {
            "status": "degraded",
            "degradation_type": payload.get("degradation_type"),
            "degradation_severity": payload.get("severity"),
            "degraded_at": payload.get("detected_at", datetime.utcnow().isoformat())
        }
        
        await self.neo4j.update_node(NodeType.ENGINE, engine_id, properties, trace_id)
        
        # Create failure node for degradation
        failure_id = f"failure_degraded_{engine_id}_{int(datetime.utcnow().timestamp())}"
        failure_properties = {
            "failure_id": failure_id,
            "type": "degradation",
            "severity": payload.get("severity"),
            "component": engine_id,
            "error_message": f"Engine degraded: {payload.get('degradation_type')}",
            "timestamp": payload.get("detected_at", datetime.utcnow().isoformat()),
            "resolved": False
        }
        
        await self.write_to_graph(NodeType.FAILURE, failure_properties, trace_id)
        
        # Link failure to engine
        await self.write_relationship(
            NodeType.FAILURE, failure_id,
            NodeType.ENGINE, engine_id,
            RelationshipType.FAILED_BECAUSE.value,
            trace_id=trace_id
        )
    
    async def _handle_engine_recovered(self, payload: Dict[str, Any], trace_id: str):
        """Handle engine.recovered event."""
        engine_id = payload["engine_id"]
        
        # Update engine node
        properties = {
            "status": "healthy",
            "recovered_at": payload.get("recovered_at", datetime.utcnow().isoformat()),
            "recovery_type": payload.get("recovery_type")
        }
        
        await self.neo4j.update_node(NodeType.ENGINE, engine_id, properties, trace_id)
        
        # Find and update associated failure
        failure_properties = {
            "resolved": True,
            "recovered_at": payload.get("recovered_at", datetime.utcnow().isoformat())
        }
        
        # Create recovery node
        recovery_id = f"recovery_{engine_id}_{int(datetime.utcnow().timestamp())}"
        recovery_properties = {
            "recovery_id": recovery_id,
            "type": payload.get("recovery_type"),
            "failure_id": None,  # Would need to query for associated failure
            "actions": payload.get("recovery_actions", []),
            "duration_seconds": payload.get("degradation_duration", 0),
            "success": not payload.get("data_loss", False),
            "timestamp": payload.get("recovered_at", datetime.utcnow().isoformat())
        }
        
        await self.write_to_graph(NodeType.RECOVERY, recovery_properties, trace_id)
        
        # Link recovery to engine
        await self.write_relationship(
            NodeType.RECOVERY, recovery_id,
            NodeType.ENGINE, engine_id,
            RelationshipType.RECOVERED_BY.value,
            trace_id=trace_id
        )
    
    def _calculate_health_score(self, payload: Dict[str, Any]) -> float:
        """Calculate health score from metrics."""
        score = 1.0
        
        # Penalize high error rate
        error_rate = payload.get("error_rate", 0.0)
        score -= error_rate * 10
        
        # Penalize high latency
        latency = payload.get("latency_ms", 0.0)
        if latency > 1000:
            score -= 0.2
        elif latency > 500:
            score -= 0.1
        
        # Penalize high CPU/memory
        cpu = payload.get("cpu_usage", 0.0)
        memory = payload.get("memory_usage", 0.0)
        if cpu > 80:
            score -= 0.15
        if memory > 80:
            score -= 0.15
        
        return max(0.0, min(1.0, score))
