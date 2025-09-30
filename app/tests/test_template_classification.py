"""
Test template classification functionality
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.template import Template
from app.models.template import TemplateCategory
from app.services.admin_service import AdminService
from app.services.template_service import TemplateSimilarityService

def create_test_template(db: Session, name: str, content: str) -> Template:
    """Helper to create a test template"""
    template = Template(
        name=name,
        content=content,
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(template)
    db.commit()
    return template

def test_template_classification(db: Session):
    """Test template classification functionality"""
    # Create test templates
    template1 = create_test_template(
        db,
        "Invoice Template",
        "This is an invoice template for business transactions and payments"
    )
    template2 = create_test_template(
        db,
        "Receipt Template",
        "This is a receipt template for recording business transactions and payments"
    )
    template3 = create_test_template(
        db,
        "Letter Template",
        "This is a formal letter template for business correspondence"
    )
    
    # Run classification
    AdminService.update_template_classifications(db)
    
    # Verify keywords were extracted
    db.refresh(template1)
    db.refresh(template2)
    db.refresh(template3)
    
    assert template1.keywords is not None
    assert template2.keywords is not None
    assert template3.keywords is not None
    
    # Verify similar templates are found
    similar = TemplateSimilarityService.find_similar_templates(db, template1.id)
    assert len(similar) > 0
    assert any(t.id == template2.id for t in similar)  # Invoice and receipt should be similar
    
    # Verify cluster assignment
    assert template1.cluster_id is not None
    assert template2.cluster_id is not None
    assert template3.cluster_id is not None

def test_keyword_search(db: Session):
    """Test keyword-based template search"""
    # Create test templates
    template1 = create_test_template(
        db,
        "Invoice Template",
        "Professional invoice template for business transactions"
    )
    template2 = create_test_template(
        db,
        "Report Template",
        "Business report template for annual reviews"
    )
    
    # Run classification
    AdminService.update_template_classifications(db)
    
    # Search by keywords
    results = TemplateSimilarityService.search_by_keywords(db, ["invoice", "business"])
    assert len(results) > 0
    assert any(t.id == template1.id for t in results)

def test_template_stats(db: Session):
    """Test template classification statistics"""
    # Create test templates
    template1 = create_test_template(
        db,
        "Invoice Template",
        "Professional invoice template"
    )
    template2 = create_test_template(
        db,
        "Receipt Template",
        "Professional receipt template"
    )
    
    # Run classification
    AdminService.update_template_classifications(db)
    
    # Get stats
    stats = AdminService._get_template_classification_stats(db)
    
    assert "clusters" in stats
    assert "top_keywords" in stats
    assert "classified_count" in stats
    assert stats["classified_count"] > 0

def test_cluster_details(db: Session):
    """Test getting cluster details"""
    # Create test templates
    template1 = create_test_template(
        db,
        "Invoice Template",
        "Professional invoice template"
    )
    template2 = create_test_template(
        db,
        "Receipt Template",
        "Professional receipt template"
    )
    
    # Run classification
    AdminService.update_template_classifications(db)
    db.refresh(template1)
    
    # Get cluster details
    details = AdminService.get_cluster_details(db, template1.cluster_id)
    
    assert details["cluster_id"] == template1.cluster_id
    assert details["template_count"] > 0
    assert len(details["common_keywords"]) > 0
    assert len(details["templates"]) > 0