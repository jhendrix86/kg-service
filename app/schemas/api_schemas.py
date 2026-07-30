from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class FunnelLaunchedRequest(BaseModel):
    funnel_id: str = Field(..., description="Funnel ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    channels: List[str] = Field(default_factory=list)
    launch_config: Dict[str, Any] = Field(default_factory=dict)
    launched_by: str = Field(..., description="Engine that launched the funnel")


class FunnelMetricsRequest(BaseModel):
    funnel_id: str = Field(..., description="Funnel ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    period_start: datetime = Field(..., description="Metrics period start")
    period_end: datetime = Field(..., description="Metrics period end")
    visitors: int = Field(default=0)
    leads: int = Field(default=0)
    conversions: int = Field(default=0)
    revenue: float = Field(default=0.0)
    conversion_rate: float = Field(default=0.0)
    cost: float = Field(default=0.0)
    roi: float = Field(default=0.0)
    channel_metrics: Dict[str, Any] = Field(default_factory=dict)
    custom_metrics: Dict[str, Any] = Field(default_factory=dict)


class FunnelInsightsRequest(BaseModel):
    funnel_id: str = Field(..., description="Funnel ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    patterns: List[Dict[str, Any]] = Field(default_factory=list)
    predictions: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0)
    insight_type: str = Field(..., description="Type of insight")


class AnomalyRequest(BaseModel):
    anomaly_type: str = Field(..., description="Type of anomaly")
    severity: str = Field(..., description="Severity level")
    entity_type: str = Field(..., description="Type of entity affected")
    entity_id: str = Field(..., description="ID of entity affected")
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    detected_by: str = Field(..., description="Engine that detected anomaly")
    anomaly_data: Dict[str, Any] = Field(default_factory=dict)
    expected_value: Optional[Any] = None
    actual_value: Optional[Any] = None
    deviation: Optional[float] = None


class PatternQueryRequest(BaseModel):
    pattern_type: Optional[str] = Field(None, description="Filter by pattern type")
    entity_type: Optional[str] = Field(None, description="Filter by entity type")
    entity_id: Optional[str] = Field(None, description="Filter by entity ID")
    confidence_threshold: float = Field(default=0.5, description="Minimum confidence")
    limit: int = Field(default=10, description="Maximum results")


class CausalChainQueryRequest(BaseModel):
    event_id: str = Field(..., description="Starting event ID")
    max_depth: int = Field(default=5, description="Maximum chain depth")
    include_branches: bool = Field(default=False, description="Include branching paths")


class TemporalSequenceRequest(BaseModel):
    entity_type: str = Field(..., description="Entity type")
    entity_id: str = Field(..., description="Entity ID")
    limit: int = Field(default=100, description="Maximum states to return")
    start_time: Optional[datetime] = Field(None, description="Start time filter")
    end_time: Optional[datetime] = Field(None, description="End time filter")


class SimulationQueryRequest(BaseModel):
    simulation_type: Optional[str] = Field(None, description="Filter by simulation type")
    entity_type: Optional[str] = Field(None, description="Filter by entity type")
    entity_id: Optional[str] = Field(None, description="Filter by entity ID")
    confidence_threshold: float = Field(default=0.0, description="Minimum confidence")
    limit: int = Field(default=10, description="Maximum results")


class GraphResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    trace_id: Optional[str] = None


class InsightResponse(BaseModel):
    success: bool
    insights: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None
    trace_id: Optional[str] = None
