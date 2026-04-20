"""Domain enumerations shared across schemas, services, and models."""

from enum import StrEnum


class IncidentStatus(StrEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


ACTIVE_INCIDENT_STATUSES: frozenset[IncidentStatus] = frozenset(
    {
        IncidentStatus.PENDING,
        IncidentStatus.ASSIGNED,
        IncidentStatus.IN_PROGRESS,
    }
)


class AssignmentStatus(StrEnum):
    ASSIGNED = "assigned"
    ACCEPTED = "accepted"
    EN_ROUTE = "en_route"
    ARRIVED = "arrived"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


ACTIVE_ASSIGNMENT_STATUSES: frozenset[AssignmentStatus] = frozenset(
    {
        AssignmentStatus.ASSIGNED,
        AssignmentStatus.ACCEPTED,
        AssignmentStatus.EN_ROUTE,
        AssignmentStatus.ARRIVED,
        AssignmentStatus.IN_PROGRESS,
    }
)


class AdjusterStatus(StrEnum):
    AVAILABLE = "available"
    BUSY = "busy"
    EN_ROUTE = "en_route"
    ON_SITE = "on_site"
    OFFLINE = "offline"


BUSY_ADJUSTER_STATUS: frozenset[AdjusterStatus] = frozenset(
    {AdjusterStatus.BUSY, AdjusterStatus.EN_ROUTE, AdjusterStatus.ON_SITE}
)
