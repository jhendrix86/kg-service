import uuid
import re
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import structlog
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from ..utils.config import settings


logger = structlog.get_logger()


@dataclass
class TraceContext:
    """W3C Trace Context."""
    trace_id: str
    span_id: str
    trace_flags: str = "00"
    
    def to_traceparent(self) -> str:
        """Convert to W3C traceparent header format."""
        return f"{self.trace_id}-{self.span_id}-{self.trace_flags}"
    
    @classmethod
    def from_traceparent(cls, traceparent: str) -> "TraceContext":
        """Parse W3C traceparent header."""
        match = re.match(r"^([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$", traceparent.lower())
        if not match:
            raise ValueError(f"Invalid traceparent format: {traceparent}")
        
        trace_id, span_id, trace_flags = match.groups()
        return cls(trace_id=trace_id, span_id=span_id, trace_flags=trace_flags)
    
    @classmethod
    def generate(cls) -> "TraceContext":
        """Generate a new trace context."""
        trace_id = uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]
        return cls(trace_id=trace_id, span_id=span_id)


@dataclass
class TraceParent:
    """Extended trace parent with correlation and causation IDs."""
    trace_context: TraceContext
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for headers."""
        return {
            "traceparent": self.trace_context.to_traceparent(),
            "correlation_id": self.correlation_id or "",
            "causation_id": self.causation_id or "",
            "parent_span_id": self.parent_span_id or "",
        }
    
    @classmethod
    def from_dict(cls, headers: Dict[str, str]) -> "TraceParent":
        """Parse from headers dictionary."""
        traceparent = headers.get("traceparent")
        if traceparent:
            trace_context = TraceContext.from_traceparent(traceparent)
        else:
            trace_context = TraceContext.generate()
        
        return cls(
            trace_context=trace_context,
            correlation_id=headers.get("correlation_id"),
            causation_id=headers.get("causation_id"),
            parent_span_id=headers.get("parent_span_id"),
        )
    
    def create_child(self) -> "TraceParent":
        """Create a child span."""
        child_trace_context = TraceContext(
            trace_id=self.trace_context.trace_id,
            span_id=uuid.uuid4().hex[:16],
            trace_flags=self.trace_context.trace_flags
        )
        
        return TraceParent(
            trace_context=child_trace_context,
            correlation_id=self.correlation_id or child_trace_context.trace_id,
            causation_id=self.causation_id or self.trace_context.span_id,
            parent_span_id=self.trace_context.span_id,
        )


class Tracer:
    """Distributed tracing utility with OpenTelemetry integration."""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.logger = logger.bind(service=service_name)
        self._otel_tracer = None
        
        if settings.otel_enabled:
            self._init_otel()
    
    def _init_otel(self):
        """Initialize OpenTelemetry."""
        resource = Resource.create({
            SERVICE_NAME: settings.otel_service_name or self.service_name
        })
        
        provider = TracerProvider(resource=resource)
        
        if settings.otel_endpoint:
            exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint, insecure=True)
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
        
        trace.set_tracer_provider(provider)
        self._otel_tracer = trace.get_tracer(self.service_name)
    
    def start_span(
        self,
        operation_name: str,
        parent: Optional[TraceParent] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> TraceParent:
        """Start a new span."""
        if parent:
            trace_parent = parent.create_child()
        elif headers:
            trace_parent = TraceParent.from_dict(headers)
            if not trace_parent.correlation_id:
                trace_parent.correlation_id = trace_parent.trace_context.trace_id
        else:
            trace_parent = TraceParent(
                trace_context=TraceContext.generate(),
                correlation_id=TraceContext.generate().trace_id,
            )
        
        # Also create OpenTelemetry span if enabled
        if self._otel_tracer:
            self._otel_tracer.start_span(operation_name)
        
        self.logger.info(
            "span_started",
            operation_name=operation_name,
            trace_id=trace_parent.trace_context.trace_id,
            span_id=trace_parent.trace_context.span_id,
            parent_span_id=trace_parent.parent_span_id,
            correlation_id=trace_parent.correlation_id,
            causation_id=trace_parent.causation_id,
        )
        
        return trace_parent
    
    def finish_span(
        self,
        trace_parent: TraceParent,
        operation_name: str,
        success: bool = True,
        error: Optional[str] = None,
        duration_ms: Optional[float] = None
    ):
        """Finish a span."""
        self.logger.info(
            "span_finished",
            operation_name=operation_name,
            trace_id=trace_parent.trace_context.trace_id,
            span_id=trace_parent.trace_context.span_id,
            success=success,
            error=error,
            duration_ms=duration_ms,
        )
    
    def inject_headers(self, trace_parent: TraceParent) -> Dict[str, str]:
        """Inject tracing headers into a dictionary."""
        return trace_parent.to_dict()
    
    def extract_headers(self, headers: Dict[str, str]) -> Optional[TraceParent]:
        """Extract tracing headers from a dictionary."""
        if "traceparent" not in headers:
            return None
        return TraceParent.from_dict(headers)
    
    def log_event(
        self,
        trace_parent: TraceParent,
        event_type: str,
        event_data: Dict[str, Any]
    ):
        """Log an event with tracing context."""
        self.logger.info(
            "event_logged",
            event_type=event_type,
            trace_id=trace_parent.trace_context.trace_id,
            span_id=trace_parent.trace_context.span_id,
            correlation_id=trace_parent.correlation_id,
            causation_id=trace_parent.causation_id,
            **event_data
        )
