"""Pydantic schemas for API request/response."""

from .dispatch import DispatchCreate, DispatchRead, DispatchUpdate
from .pagination import PaginatedResponse
from .resource import ResourceCreate, ResourceRead, ResourceUpdate
from .task import TaskCreate, TaskRead, TaskUpdate

__all__ = [
    # Pagination
    "PaginatedResponse",
    # Task
    "TaskCreate",
    "TaskRead",
    "TaskUpdate",
    # Resource
    "ResourceCreate",
    "ResourceRead",
    "ResourceUpdate",
    # Dispatch
    "DispatchCreate",
    "DispatchRead",
    "DispatchUpdate",
]
