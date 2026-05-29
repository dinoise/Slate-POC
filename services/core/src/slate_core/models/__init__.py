"""Shared SQLAlchemy models for all Slate services."""

from .base import Base, BaseModel, TimestampMixin
from .demand_prediction import DemandPrediction
from .dispatch import Dispatch
from .dispatch_event import DispatchEvent
from .dispatch_note import DispatchNote
from .dispatch_status_history import DispatchStatusHistory
from .resource import Resource
from .resource_position import ResourcePosition
from .task import Task
from .user import User

__all__ = [
    "Base",
    "BaseModel",
    "TimestampMixin",
    "Task",
    "Resource",
    "ResourcePosition",
    "Dispatch",
    "DispatchEvent",
    "DispatchNote",
    "DispatchStatusHistory",
    "DemandPrediction",
    "User",
]
