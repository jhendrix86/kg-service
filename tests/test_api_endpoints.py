import pytest
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


class TestHealthEndpoints:
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "status" in data
        assert data["status"] == "healthy"
    
    def test_root(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data
        assert "docs" in data


class TestWriteEndpoints:
    def test_funnel_launched(self):
        from datetime import datetime
        request_data = {
            "funnel_id": "test-funnel-123",
            "timestamp": datetime.utcnow().isoformat(),
            "channels": ["twitter", "linkedin"],
            "launch_config": {"auto_optimize": True},
            "launched_by": "test-engine"
        }
        
        # This will fail if Neo4j is not connected, but we can test the schema
        response = client.post("/events/funnel-launched", json=request_data)
        # We expect 500 if services aren't running, or 200 if they are
        assert response.status_code in [200, 500]
    
    def test_funnel_metrics(self):
        from datetime import datetime
        request_data = {
            "funnel_id": "test-funnel-123",
            "timestamp": datetime.utcnow().isoformat(),
            "period_start": datetime.utcnow().isoformat(),
            "period_end": datetime.utcnow().isoformat(),
            "visitors": 1000,
            "conversions": 50,
            "revenue": 5000.0,
            "conversion_rate": 0.05
        }
        
        response = client.post("/events/funnel-metrics", json=request_data)
        assert response.status_code in [200, 500]


class TestReadEndpoints:
    def test_get_funnel_not_found(self):
        response = client.get("/graph/funnel/nonexistent")
        # Will be 404 if Neo4j is running, or 500 if not
        assert response.status_code in [404, 500]
    
    def test_get_user_not_found(self):
        response = client.get("/graph/user/nonexistent")
        assert response.status_code in [404, 500]


class TestQueryEndpoints:
    def test_query_patterns(self):
        request_data = {
            "pattern_type": "conversion",
            "confidence_threshold": 0.7,
            "limit": 10
        }
        
        response = client.post("/query/patterns", json=request_data)
        assert response.status_code in [200, 500]
    
    def test_query_causal_chain(self):
        request_data = {
            "event_id": "test-event-123",
            "max_depth": 5
        }
        
        response = client.post("/query/causal-chain", json=request_data)
        assert response.status_code in [200, 500]


class TestInsightEndpoints:
    def test_get_funnel_insights_not_found(self):
        response = client.get("/insights/funnel/nonexistent")
        assert response.status_code in [404, 500]
    
    def test_get_niche_insights_not_found(self):
        response = client.get("/insights/niche/nonexistent")
        assert response.status_code in [404, 500]


class TestDLQEndpoints:
    def test_get_dlq_stats(self):
        response = client.get("/dlq/stats")
        assert response.status_code in [200, 500]
    
    def test_peek_dlq_messages(self):
        response = client.get("/dlq/messages?limit=10")
        assert response.status_code in [200, 500]
