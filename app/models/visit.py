"""
Basic Visit model - Legacy compatibility
"""

# Import the main visit models from analytics
from .analytics.visit import BaseVisit, DocumentVisit, LandingVisit, PageVisit

# For backward compatibility, provide a basic Visit alias
# Most usage patterns suggest this should be DocumentVisit
Visit = DocumentVisit

__all__ = ["Visit", "BaseVisit", "DocumentVisit", "LandingVisit", "PageVisit"]