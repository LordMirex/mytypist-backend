"""Search service shim.

This module exposes `SearchService` as the canonical service name while
reusing the implementation in `advanced_search_service.py`. This keeps a
single public import path and allows us to remove the "advanced_" prefix
from route/service imports incrementally.
"""

from app.services.advanced_search_service import AdvancedSearchService as SearchService

__all__ = ["SearchService"]
