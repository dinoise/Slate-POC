"""Assignment routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from ..core import DBSession
from ..core.provider_registry import ProviderDep
from ..schemas.assignment import (
    AssignmentCreate,
    AssignmentRead,
    AssignmentStatusHistoryRead,
    AssignmentUpdate,
    OptimizeRequest,
    OptimizeResponse,
    RouteResponse,
)
from ..schemas.assignment_metrics import AssignmentMetrics
from ..schemas.pagination import PaginatedResponse
from ..services.assignment_metrics_service import AssignmentMetricsService
from ..services.assignment_service import AssignmentService

router = APIRouter(prefix="/assignments", tags=["assignments"])


def get_assignment_service(db: DBSession) -> AssignmentService:
    """Get assignment service dependency."""
    return AssignmentService(db)


AssignmentServiceDep = Annotated[AssignmentService, Depends(get_assignment_service)]


def get_metrics_service(db: DBSession) -> AssignmentMetricsService:
    return AssignmentMetricsService(db)


MetricsServiceDep = Annotated[AssignmentMetricsService, Depends(get_metrics_service)]


@router.get(
    "/metrics",
    response_model=AssignmentMetrics,
    summary="Aggregated assignment metrics for the analytics AI agent",
)
async def get_assignment_metrics(
    service: MetricsServiceDep,
    window_hours: int = Query(
        8, ge=1, le=168, description="Hours to look back for volume/resolution stats"
    ),
) -> AssignmentMetrics:
    """
    Return aggregated assignment metrics.

    Used by the analytics sub-agent to answer questions like:
    - How many assignments are active right now and in what state?
    - What's the average resolution time in the last shift?
    - How many incidents were created vs resolved in the last N hours?
    """
    return await service.get_metrics(window_hours=window_hours)


@router.post(
    "/",
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create new assignment",
)
async def create_assignment(
    data: AssignmentCreate,
    service: AssignmentServiceDep,
) -> AssignmentRead:
    """Create a new assignment of an adjuster to an incident."""
    assignment = await service.create_assignment(data)
    return AssignmentRead.model_validate(assignment)


@router.get(
    "/",
    response_model=PaginatedResponse[AssignmentRead],
    summary="Get all assignments",
)
async def get_assignments(
    service: AssignmentServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: str | None = Query(None, alias="status"),
) -> PaginatedResponse[AssignmentRead]:
    """Get all assignments with optional filtering."""
    items, total = await service.get_all_assignments(
        skip=skip,
        limit=limit,
        status=status_filter,
    )
    page = (skip // limit) + 1 if limit else 1
    return PaginatedResponse(
        items=[AssignmentRead.model_validate(asgn) for asgn in items],
        total=total,
        page=page,
        size=limit,
    )


@router.get(
    "/route",
    response_model=RouteResponse,
    summary="Compute a single point-to-point route",
)
async def compute_route(
    service: AssignmentServiceDep,
    provider: ProviderDep,
    origin_lat: float = Query(..., ge=-90, le=90),
    origin_lon: float = Query(..., ge=-180, le=180),
    destination_lat: float = Query(..., ge=-90, le=90),
    destination_lon: float = Query(..., ge=-180, le=180),
) -> RouteResponse:
    """
    Return the route geometry between two points using the active routing provider.

    The polyline uses precision-5 encoding (compatible with Leaflet's
    L.PolylineUtil.decode and the custom decodePolyline helper in the frontend).
    """
    return await service.compute_route(
        origin_lat, origin_lon, destination_lat, destination_lon, provider
    )


@router.get(
    "/by-incident/{incident_id}",
    response_model=list[AssignmentRead],
    summary="Get assignments for incident",
)
async def get_assignments_by_incident(
    incident_id: int,
    service: AssignmentServiceDep,
    limit: int = Query(100, ge=1, le=1000),
    active: bool = Query(False, description="Return only active (non-terminal) assignments"),
) -> list[AssignmentRead]:
    """Get assignments for a specific incident.

    Use ?active=true to retrieve only non-terminal assignments — avoids
    client-side filtering over the full assignment history.
    """
    assignments = await service.get_assignments_by_incident(incident_id, limit, active_only=active)
    return [AssignmentRead.model_validate(asgn) for asgn in assignments]


@router.get(
    "/by-adjuster/{adjuster_id}",
    response_model=list[AssignmentRead],
    summary="Get assignments for adjuster",
)
async def get_assignments_by_adjuster(
    adjuster_id: int,
    service: AssignmentServiceDep,
    limit: int = Query(100, ge=1, le=1000),
    active: bool = Query(False, description="Return only active (non-terminal) assignments"),
) -> list[AssignmentRead]:
    """Get assignments for a specific adjuster.

    Use ?active=true to retrieve only non-terminal assignments — avoids
    client-side filtering over the full assignment history.
    """
    assignments = await service.get_assignments_by_adjuster(adjuster_id, limit, active_only=active)
    return [AssignmentRead.model_validate(asgn) for asgn in assignments]


@router.get(
    "/{assignment_id}/history",
    response_model=list[AssignmentStatusHistoryRead],
    summary="Get status history for an assignment",
)
async def get_assignment_history(
    assignment_id: int,
    service: AssignmentServiceDep,
) -> list[AssignmentStatusHistoryRead]:
    """Return the immutable audit trail of status transitions for an assignment."""
    history = await service.get_assignment_history(assignment_id)
    return [AssignmentStatusHistoryRead.model_validate(entry) for entry in history]


@router.get(
    "/{assignment_id}",
    response_model=AssignmentRead,
    summary="Get assignment by ID",
)
async def get_assignment(
    assignment_id: int,
    service: AssignmentServiceDep,
) -> AssignmentRead:
    """Get a specific assignment by ID."""
    assignment = await service.get_assignment(assignment_id)
    return AssignmentRead.model_validate(assignment)


@router.patch(
    "/{assignment_id}",
    response_model=AssignmentRead,
    summary="Update assignment",
)
async def update_assignment(
    assignment_id: int,
    data: AssignmentUpdate,
    service: AssignmentServiceDep,
) -> AssignmentRead:
    """Update an assignment."""
    assignment = await service.update_assignment(assignment_id, data)
    return AssignmentRead.model_validate(assignment)


@router.post(
    "/optimize",
    response_model=OptimizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Optimize adjuster-to-incident assignments",
)
async def optimize_assignments(
    data: OptimizeRequest,
    service: AssignmentServiceDep,
    provider: ProviderDep,
) -> OptimizeResponse:
    """
    Solve the assignment problem optimally using OR-Tools LinearSumAssignment.

    Minimizes the total travel time across all assignments.
    Accepts explicit incident/adjuster lists, or queries the DB when `use_db=True`.

    Returns assignments with travel times and solver metrics.
    """
    return await service.optimize_assignments(data, provider)
