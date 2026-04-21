"""Pydantic schemas — public HTTP contract of the notifications service."""

from .notification import EnrichedAssignmentEvent

__all__ = ["EnrichedAssignmentEvent"]
