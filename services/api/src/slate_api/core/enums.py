"""Domain enumerations shared across schemas, services, and models."""

from enum import StrEnum


class TaskStatus(StrEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


ACTIVE_TASK_STATUSES: frozenset[TaskStatus] = frozenset(
    {
        TaskStatus.PENDING,
        TaskStatus.ASSIGNED,
        TaskStatus.IN_PROGRESS,
    }
)


class DispatchStatus(StrEnum):
    ASSIGNED = "assigned"
    ACCEPTED = "accepted"
    EN_ROUTE = "en_route"
    ARRIVED = "arrived"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


ACTIVE_DISPATCH_STATUSES: frozenset[DispatchStatus] = frozenset(
    {
        DispatchStatus.ASSIGNED,
        DispatchStatus.ACCEPTED,
        DispatchStatus.EN_ROUTE,
        DispatchStatus.ARRIVED,
        DispatchStatus.IN_PROGRESS,
    }
)


class ResourceStatus(StrEnum):
    AVAILABLE = "available"
    BUSY = "busy"
    EN_ROUTE = "en_route"
    ON_SITE = "on_site"
    OFFLINE = "offline"


BUSY_RESOURCE_STATUSES: frozenset[ResourceStatus] = frozenset(
    {ResourceStatus.BUSY, ResourceStatus.EN_ROUTE, ResourceStatus.ON_SITE}
)
