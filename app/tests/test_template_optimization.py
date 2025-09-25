"""
Test optimized template system
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session
from app.services.template_service import TemplateLoader, TemplateCacheService
from app.models.template import Template

@pytest.fixture
def test_templates(db: Session):
    """Create test templates"""
    templates = []
    for i in range(5):
        template = Template(
            name=f"Test Template {i}",
            description=f"Test template {i} description",
            category="test",
            type="document",
            file_path=f"/test/path/{i}.docx",
            file_size=1000,
            file_hash="test_hash",
            created_by=1,
            is_active=True
        )
        db.add(template)
        templates.append(template)
    
    db.commit()
    for template in templates:
        db.refresh(template)
    
    return templates

@pytest.mark.asyncio
async def test_template_caching(db: Session, test_templates):
    """Test template caching functionality"""
    template = test_templates[0]
    
    # Test cache miss (first load)
    cached = await TemplateCacheService.get_cached_template(template.id)
    assert cached is None
    
    # Cache the template
    success = await TemplateCacheService.cache_template(template)
    assert success is True
    
    # Test cache hit
    cached = await TemplateCacheService.get_cached_template(template.id)
    assert cached is not None
    assert cached['id'] == template.id
    
    # Test cache invalidation
    success = await TemplateCacheService.invalidate_template_cache(template.id)
    assert success is True
    
    cached = await TemplateCacheService.get_cached_template(template.id)
    assert cached is None

@pytest.mark.asyncio
async def test_template_loader(db: Session, test_templates):
    """Test optimized template loading"""
    template = test_templates[0]
    
    # Test single template load
    loaded = await TemplateLoader.load_template(db, template.id)
    assert loaded is not None
    assert loaded.id == template.id
    
    # Should be cached now
    cached = await TemplateCacheService.get_cached_template(template.id)
    assert cached is not None

@pytest.mark.asyncio
async def test_bulk_template_loading(db: Session, test_templates):
    """Test bulk template loading"""
    template_ids = [t.id for t in test_templates]
    
    # Test bulk load
    loaded = await TemplateLoader.load_templates_bulk(db, template_ids)
    assert len(loaded) == len(template_ids)
    
    # Test batch processing
    loaded = await TemplateLoader.load_templates_bulk(db, template_ids, batch_size=2)
    assert len(loaded) == len(template_ids)
    
    # Test cache hits after bulk load
    for template_id in template_ids:
        cached = await TemplateCacheService.get_cached_template(template_id)
        assert cached is not None

@pytest.mark.asyncio
async def test_template_preloading(db: Session, test_templates):
    """Test template preloading"""
    # Clear any existing cache
    for template in test_templates:
        await TemplateCacheService.invalidate_template_cache(template.id)
    
    # Test preloading
    success = await TemplateLoader.preload_templates(db, category="test")
    assert success is True
    
    # Verify all templates are cached
    for template in test_templates:
        cached = await TemplateCacheService.get_cached_template(template.id)
        assert cached is not None

@pytest.mark.asyncio
async def test_cache_performance(db: Session, test_templates):
    """Test cache performance metrics"""
    template = test_templates[0]
    
    # Clear cache
    await TemplateCacheService.invalidate_template_cache(template.id)
    
    # First load (should miss cache)
    loaded = await TemplateLoader.load_template(db, template.id)
    assert loaded is not None
    
    # Second load (should hit cache)
    loaded = await TemplateLoader.load_template(db, template.id)
    assert loaded is not None
    
    # Bulk load should use cache for this template
    loaded = await TemplateLoader.load_templates_bulk(db, [template.id])
    assert len(loaded) == 1