from typing import Dict, Any
from datetime import datetime
import structlog
from autonomy_events import EventEnvelope, ConsumeResult, TraceParent
from .base import BaseConsumer
from ..graph import NodeType, RelationshipType


logger = structlog.get_logger()


class FunnelConsumer(BaseConsumer):
    """Consumer for funnel-related events."""
    
    async def handle_event(
        self,
        envelope: EventEnvelope,
        trace_parent: TraceParent
    ) -> ConsumeResult:
        """Handle funnel events."""
        event_type = envelope.event_type
        payload = envelope.payload
        trace_id = trace_parent.trace_context.trace_id if trace_parent else None
        
        try:
            if event_type == "funnel.created":
                await self._handle_funnel_created(payload, trace_id)
            elif event_type == "funnel.launched":
                await self._handle_funnel_launched(payload, trace_id)
            elif event_type == "funnel.metrics":
                await self._handle_funnel_metrics(payload, trace_id)
            elif event_type == "funnel.insights":
                await self._handle_funnel_insights(payload, trace_id)
            elif event_type == "funnel.mutation":
                await self._handle_funnel_mutation(payload, trace_id)
            elif event_type == "funnel.archived":
                await self._handle_funnel_archived(payload, trace_id)
            else:
                logger.warning("unknown_funnel_event", event_type=event_type)
                return ConsumeResult(
                    success=False,
                    event_id=envelope.event_id,
                    event_type=event_type,
                    error=f"Unknown funnel event type: {event_type}"
                )
            
            return ConsumeResult(
                success=True,
                event_id=envelope.event_id,
                event_type=event_type
            )
        
        except Exception as e:
            logger.error("funnel_consumer_error", error=str(e))
            return ConsumeResult(
                success=False,
                event_id=envelope.event_id,
                event_type=event_type,
                error=str(e)
            )
    
    async def _handle_funnel_created(self, payload: Dict[str, Any], trace_id: str):
        """Handle funnel.created event."""
        funnel_id = payload["funnel_id"]
        
        # Create funnel node
        properties = {
            "funnel_id": funnel_id,
            "niche": payload.get("niche"),
            "strategy": payload.get("strategy"),
            "status": "created",
            "governance_status": payload.get("governance_status", "pending"),
            "target_audience": payload.get("target_audience"),
            "channels": payload.get("channels", []),
            "created_at": datetime.utcnow().isoformat(),
            "total_visitors": 0,
            "total_conversions": 0,
            "total_revenue": 0.0,
            "conversion_rate": 0.0,
            "metadata": payload.get("metadata", {})
        }
        
        await self.write_to_graph(NodeType.FUNNEL, properties, trace_id)
        
        # Create relationship to niche if niche exists
        if payload.get("niche"):
            niche_id = f"niche_{payload['niche'].lower().replace(' ', '_')}"
            await self.write_relationship(
                NodeType.FUNNEL, funnel_id,
                NodeType.NICHE, niche_id,
                RelationshipType.PART_OF.value,
                trace_id=trace_id
            )
        
        # Store embedding
        await self.write_embedding(
            "funnels",
            funnel_id,
            f"{payload.get('niche')} {payload.get('strategy')} {payload.get('target_audience')}",
            {"funnel_id": funnel_id, "event": "created"},
            trace_id
        )
    
    async def _handle_funnel_launched(self, payload: Dict[str, Any], trace_id: str):
        """Handle funnel.launched event."""
        funnel_id = payload["funnel_id"]
        
        # Update funnel node
        properties = {
            "status": "launched",
            "launched_at": payload.get("timestamp", datetime.utcnow().isoformat()),
            "channels": payload.get("channels", []),
            "launched_by": payload.get("launched_by")
        }
        
        await self.neo4j.update_node(NodeType.FUNNEL, funnel_id, properties, trace_id)
        
        # Create event node
        event_properties = {
            "event_id": envelope_event_id := f"event_{funnel_id}_launched",
            "event_type": "funnel.launched",
            "timestamp": datetime.utcnow().isoformat(),
            "source": payload.get("launched_by"),
            "payload": payload,
            "correlation_id": trace_id
        }
        
        await self.write_to_graph(NodeType.EVENT, event_properties, trace_id)
        
        # Link event to funnel
        await self.write_relationship(
            NodeType.EVENT, envelope_event_id,
            NodeType.FUNNEL, funnel_id,
            RelationshipType.CAUSES.value,
            trace_id=trace_id
        )
    
    async def _handle_funnel_metrics(self, payload: Dict[str, Any], trace_id: str):
        """Handle funnel.metrics event."""
        funnel_id = payload["funnel_id"]
        
        # Update funnel node with metrics
        properties = {
            "total_visitors": payload.get("visitors", 0),
            "total_conversions": payload.get("conversions", 0),
            "total_revenue": payload.get("revenue", 0.0),
            "conversion_rate": payload.get("conversion_rate", 0.0),
            "cost": payload.get("cost", 0.0),
            "roi": payload.get("roi", 0.0)
        }
        
        await self.neo4j.update_node(NodeType.FUNNEL, funnel_id, properties, trace_id)
        
        # Create revenue node if revenue > 0
        if payload.get("revenue", 0) > 0:
            revenue_id = f"revenue_{funnel_id}_{int(datetime.utcnow().timestamp())}"
            revenue_properties = {
                "revenue_id": revenue_id,
                "amount": payload.get("revenue"),
                "currency": "USD",
                "source": "funnel",
                "funnel_id": funnel_id,
                "timestamp": payload.get("timestamp", datetime.utcnow().isoformat())
            }
            
            await self.write_to_graph(NodeType.REVENUE, revenue_properties, trace_id)
            await self.write_relationship(
                NodeType.FUNNEL, funnel_id,
                NodeType.REVENUE, revenue_id,
                RelationshipType.GENERATES.value,
                trace_id=trace_id
            )
    
    async def _handle_funnel_insights(self, payload: Dict[str, Any], trace_id: str):
        """Handle funnel.insights event."""
        funnel_id = payload["funnel_id"]
        
        # Update funnel node with insights
        properties = {
            "insights": payload.get("recommendations", []),
            "insight_confidence": payload.get("confidence", 0.0),
            "insight_type": payload.get("insight_type"),
            "last_insight_at": datetime.utcnow().isoformat()
        }
        
        await self.neo4j.update_node(NodeType.FUNNEL, funnel_id, properties, trace_id)
        
        # Store insight embedding
        insights_text = " ".join(payload.get("recommendations", []))
        if insights_text:
            await self.write_embedding(
                "funnels",
                f"{funnel_id}_insights",
                insights_text,
                {"funnel_id": funnel_id, "type": "insights"},
                trace_id
            )
    
    async def _handle_funnel_mutation(self, payload: Dict[str, Any], trace_id: str):
        """Handle funnel.mutation event."""
        funnel_id = payload["funnel_id"]
        mutation_type = payload.get("mutation_type")
        
        # Create strategy node for mutation
        strategy_id = f"strategy_{funnel_id}_{mutation_type}_{int(datetime.utcnow().timestamp())}"
        strategy_properties = {
            "strategy_id": strategy_id,
            "name": f"{mutation_type}_strategy",
            "type": mutation_type,
            "parameters": payload.get("mutation_config", {}),
            "success_rate": 0.0,
            "created_at": datetime.utcnow().isoformat()
        }
        
        await self.write_to_graph(NodeType.STRATEGY, strategy_properties, trace_id)
        
        # Link strategy to funnel
        await self.write_relationship(
            NodeType.STRATEGY, strategy_id,
            NodeType.FUNNEL, funnel_id,
            RelationshipType.OPTIMIZED_BY.value,
            trace_id=trace_id
        )
        
        # If replicating, link to source funnel
        if payload.get("source_funnel_id"):
            await self.write_relationship(
                NodeType.FUNNEL, funnel_id,
                NodeType.FUNNEL, payload["source_funnel_id"],
                RelationshipType.VERSION_OF.value,
                trace_id=trace_id
            )
    
    async def _handle_funnel_archived(self, payload: Dict[str, Any], trace_id: str):
        """Handle funnel.archived event."""
        funnel_id = payload["funnel_id"]
        
        # Update funnel node
        properties = {
            "status": "archived",
            "archived_at": payload.get("archived_at", datetime.utcnow().isoformat()),
            "archived_by": payload.get("archived_by"),
            "archival_reason": payload.get("reason"),
            "final_metrics": payload.get("final_metrics", {})
        }
        
        await self.neo4j.update_node(NodeType.FUNNEL, funnel_id, properties, trace_id)
