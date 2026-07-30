import pytest
from app.graph.schema import GraphSchema, NodeType, RelationshipType


class TestGraphSchema:
    def test_node_constraints(self):
        constraints = GraphSchema.get_node_constraints()
        
        assert len(constraints) > 0
        
        # Check for required constraints
        constraint_labels = [c["label"] for c in constraints]
        assert NodeType.USER.value in constraint_labels
        assert NodeType.FUNNEL.value in constraint_labels
        assert NodeType.NICHE.value in constraint_labels
    
    def test_node_indexes(self):
        indexes = GraphSchema.get_node_indexes()
        
        assert len(indexes) > 0
        
        # Check for required indexes
        index_labels = [i["label"] for i in indexes]
        assert NodeType.FUNNEL.value in index_labels
        assert NodeType.NICHE.value in index_labels
    
    def test_schema_cypher(self):
        cypher = GraphSchema.get_schema_cypher()
        
        assert "CREATE CONSTRAINT" in cypher
        assert "CREATE INDEX" in cypher
        assert "IF NOT EXISTS" in cypher
    
    def test_node_properties(self):
        properties = GraphSchema.get_node_properties(NodeType.FUNNEL)
        
        assert "funnel_id" in properties
        assert "niche" in properties
        assert "strategy" in properties
        assert "status" in properties
        assert properties["funnel_id"] == "string"
    
    def test_node_properties_user(self):
        properties = GraphSchema.get_node_properties(NodeType.USER)
        
        assert "user_id" in properties
        assert "email" in properties
        assert "lifecycle_stage" in properties
        assert "total_revenue" in properties
    
    def test_node_properties_niche(self):
        properties = GraphSchema.get_node_properties(NodeType.NICHE)
        
        assert "niche_id" in properties
        assert "name" in properties
        assert "trend_score" in properties
        assert "market_size" in properties
    
    def test_relationship_types(self):
        rel_types = [rt.value for rt in RelationshipType]
        
        assert "INTERACTED_WITH" in rel_types
        assert "GENERATES" in rel_types
        assert "OPTIMIZED_BY" in rel_types
        assert "CAUSES" in rel_types
        assert "RESULTS_IN" in rel_types
        assert "NEXT_STATE" in rel_types
