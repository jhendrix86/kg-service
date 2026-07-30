from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import structlog
from ..schemas import GraphResponse
from ..tracing import Tracer
from autonomy_events import DLQManager


logger = structlog.get_logger()
router = APIRouter(prefix="/dlq", tags=["DLQ Management"])


def get_tracer():
    """Dependency for tracer."""
    from ..tracing import Tracer
    return Tracer("kg-service")


@router.get("/stats", response_model=GraphResponse)
async def get_dlq_stats(
    tracer: Tracer = Depends(get_tracer)
):
    """Get DLQ statistics."""
    trace_parent = tracer.start_span("api.get_dlq_stats")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        from ..utils.config import settings
        dlq = DLQManager(
            rabbitmq_url=settings.rabbitmq_url,
            dlq_queue_name="kg-funnel-events.dlq"  # Example queue name
        )
        
        async with dlq:
            stats = await dlq.get_statistics()
        
        tracer.finish_span(trace_parent, "api.get_dlq_stats", True, duration_ms=0)
        
        return GraphResponse(
            success=True,
            data=stats,
            trace_id=trace_id
        )
    
    except Exception as e:
        logger.error("get_dlq_stats_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.get_dlq_stats", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/messages", response_model=GraphResponse)
async def peek_dlq_messages(
    limit: int = 10,
    tracer: Tracer = Depends(get_tracer)
):
    """Peek at DLQ messages without consuming them."""
    trace_parent = tracer.start_span("api.peek_dlq_messages")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        from ..utils.config import settings
        dlq = DLQManager(
            rabbitmq_url=settings.rabbitmq_url,
            dlq_queue_name="kg-funnel-events.dlq"
        )
        
        async with dlq:
            messages = await dlq.peek_messages(limit=limit)
        
        tracer.finish_span(trace_parent, "api.peek_dlq_messages", True, duration_ms=0)
        
        return GraphResponse(
            success=True,
            data={"messages": messages, "count": len(messages)},
            trace_id=trace_id
        )
    
    except Exception as e:
        logger.error("peek_dlq_messages_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.peek_dlq_messages", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/replay/{event_id}", response_model=GraphResponse)
async def replay_dlq_message(
    event_id: str,
    tracer: Tracer = Depends(get_tracer)
):
    """Replay a specific message from DLQ."""
    trace_parent = tracer.start_span("api.replay_dlq_message")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        from ..utils.config import settings
        dlq = DLQManager(
            rabbitmq_url=settings.rabbitmq_url,
            dlq_queue_name="kg-funnel-events.dlq"
        )
        
        async with dlq:
            success = await dlq.replay_message(original_event_id=event_id)
        
        tracer.finish_span(trace_parent, "api.replay_dlq_message", True, duration_ms=0)
        
        return GraphResponse(
            success=success,
            data={"event_id": event_id, "replayed": success},
            trace_id=trace_id
        )
    
    except Exception as e:
        logger.error("replay_dlq_message_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.replay_dlq_message", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/replay-batch", response_model=GraphResponse)
async def replay_dlq_batch(
    limit: int = 100,
    event_type_filter: str = None,
    tracer: Tracer = Depends(get_tracer)
):
    """Replay a batch of messages from DLQ."""
    trace_parent = tracer.start_span("api.replay_dlq_batch")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        from ..utils.config import settings
        dlq = DLQManager(
            rabbitmq_url=settings.rabbitmq_url,
            dlq_queue_name="kg-funnel-events.dlq"
        )
        
        async with dlq:
            result = await dlq.replay_batch(
                limit=limit,
                event_type_filter=event_type_filter
            )
        
        tracer.finish_span(trace_parent, "api.replay_dlq_batch", True, duration_ms=0)
        
        return GraphResponse(
            success=True,
            data=result,
            trace_id=trace_id
        )
    
    except Exception as e:
        logger.error("replay_dlq_batch_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.replay_dlq_batch", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/purge", response_model=GraphResponse)
async def purge_dlq_messages(
    age_hours: int = 24,
    tracer: Tracer = Depends(get_tracer)
):
    """Purge old messages from DLQ."""
    trace_parent = tracer.start_span("api.purge_dlq_messages")
    trace_id = trace_parent.trace_context.trace_id
    
    try:
        from ..utils.config import settings
        dlq = DLQManager(
            rabbitmq_url=settings.rabbitmq_url,
            dlq_queue_name="kg-funnel-events.dlq"
        )
        
        async with dlq:
            purged = await dlq.purge_old_messages(age_hours=age_hours)
        
        tracer.finish_span(trace_parent, "api.purge_dlq_messages", True, duration_ms=0)
        
        return GraphResponse(
            success=True,
            data={"purged_count": purged, "age_hours": age_hours},
            trace_id=trace_id
        )
    
    except Exception as e:
        logger.error("purge_dlq_messages_error", error=str(e), trace_id=trace_id)
        tracer.finish_span(trace_parent, "api.purge_dlq_messages", False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
