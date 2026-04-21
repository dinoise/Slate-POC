"""Business logic for Assignment operations."""

import time
from datetime import datetime

import numpy as np
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from slate_core.geospatial.base import RoutingProvider
from slate_core.optimization import assignment_solver

from ..core.enums import AdjusterStatus, AssignmentStatus, IncidentStatus
from ..core.exceptions import NotFoundError, ServiceUnavailableError, ValidationError
from ..core.logging import get_logger
from ..models import Assignment, AssignmentStatusHistory
from ..repositories.adjuster_repository import AdjusterRepository
from ..repositories.assignment_repository import AssignmentRepository
from ..repositories.incident_repository import IncidentRepository
from ..schemas.assignment import (
    AdjusterCoord,
    AssignmentCreate,
    AssignmentUpdate,
    CandidateResult,
    IncidentCoord,
    OptimizedAssignment,
    OptimizeRequest,
    OptimizeResponse,
    RouteResponse,
)

logger = get_logger(__name__)


class AssignmentService:
    """Service for Assignment business logic."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize service."""
        self.repository = AssignmentRepository(db)
        self.incident_repository = IncidentRepository(db)
        self.adjuster_repository = AdjusterRepository(db)

    async def create_assignment(self, data: AssignmentCreate) -> Assignment:
        """
        Create new assignment.

        Args:
            data: Assignment creation data

        Returns:
            Created assignment

        Raises:
            NotFoundError: If incident or adjuster not found
            ValidationError: If business rules violated
        """
        # Verify incident exists and is pending
        incident = await self.incident_repository.get_by_id(data.incident_id)
        if not incident:
            raise NotFoundError(f"Incident with id {data.incident_id} not found")

        # Verify adjuster exists and is available
        adjuster = await self.adjuster_repository.get_by_id(data.adjuster_id)
        if not adjuster:
            raise NotFoundError(f"Adjuster with id {data.adjuster_id} not found")

        if not adjuster.is_active:
            raise ValidationError(f"Adjuster {adjuster.id} is not active")

        if adjuster.status != "available":
            raise ValidationError(f"Adjuster {adjuster.id} is not available")

        # Check adjuster's current workload
        active_assignments = await self.repository.get_active_by_adjuster(data.adjuster_id)
        if len(active_assignments) >= adjuster.max_cases_per_day:
            raise ValidationError(
                f"Adjuster {adjuster.id} has reached max cases per day ({adjuster.max_cases_per_day})"
            )

        # Create assignment
        assignment = await self.repository.create(
            incident_id=data.incident_id,
            adjuster_id=data.adjuster_id,
            assigned_at=data.assigned_at,
            notes=data.notes,
            status=AssignmentStatus.ASSIGNED,
        )

        # Update incident status
        await self.incident_repository.update(data.incident_id, status=IncidentStatus.ASSIGNED)

        # Update adjuster status
        await self.adjuster_repository.update(data.adjuster_id, status=AdjusterStatus.BUSY)

        return assignment

    async def get_assignment(self, assignment_id: int) -> Assignment:
        """
        Get assignment by ID.

        Args:
            assignment_id: Assignment ID

        Returns:
            Assignment

        Raises:
            NotFoundError: If assignment not found
        """
        assignment = await self.repository.get_by_id(assignment_id)
        if not assignment:
            raise NotFoundError(f"Assignment with id {assignment_id} not found")
        return assignment

    async def get_all_assignments(
        self,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None,
    ) -> tuple[list[Assignment], int]:
        """Get paginated assignments with total count.

        Args:
            skip: Records to skip
            limit: Maximum records
            status: Optional status filter

        Returns:
            Tuple of (items, total)
        """
        if status:
            items = await self.repository.get_by_status(status, limit)
            return items, len(items)
        return await self.repository.get_all_paginated(skip=skip, limit=limit)

    async def update_assignment(
        self,
        assignment_id: int,
        data: AssignmentUpdate,
    ) -> Assignment:
        """
        Update assignment.

        Args:
            assignment_id: Assignment ID
            data: Update data

        Returns:
            Updated assignment

        Raises:
            NotFoundError: If assignment not found
        """
        # Check if exists
        assignment = await self.get_assignment(assignment_id)

        # Update
        updated = await self.repository.update(
            assignment_id,
            **data.model_dump(exclude_unset=True),
        )

        if not updated:
            raise NotFoundError(f"Assignment with id {assignment_id} not found")

        # Side-effects on terminal status transitions
        if data.status == AssignmentStatus.CANCELLED:
            await self.adjuster_repository.update(
                assignment.adjuster_id, status=AdjusterStatus.AVAILABLE
            )
            # Cancel the incident too — prevents it from re-entering the optimizer queue
            incident = await self.incident_repository.get_by_id(assignment.incident_id)
            if incident and incident.status != IncidentStatus.CANCELLED:
                await self.incident_repository.update(
                    assignment.incident_id, status=IncidentStatus.CANCELLED
                )

        elif data.status == AssignmentStatus.COMPLETED:
            await self.adjuster_repository.update(
                assignment.adjuster_id, status=AdjusterStatus.AVAILABLE
            )
            await self.incident_repository.update(
                assignment.incident_id, status=IncidentStatus.COMPLETED
            )

        return updated

    async def get_assignments_by_incident(
        self,
        incident_id: int,
        limit: int = 100,
    ) -> list[Assignment]:
        """Get assignments for an incident."""
        return await self.repository.get_by_incident(incident_id, limit)

    async def get_assignments_by_adjuster(
        self,
        adjuster_id: int,
        limit: int = 100,
    ) -> list[Assignment]:
        """Get assignments for an adjuster."""
        return await self.repository.get_by_adjuster(adjuster_id, limit)

    async def get_assignment_history(
        self,
        assignment_id: int,
    ) -> list[AssignmentStatusHistory]:
        """Return the status-change audit trail for an assignment.

        Raises:
            NotFoundError: If the assignment does not exist.
        """
        assignment = await self.repository.get(assignment_id)
        if not assignment:
            raise NotFoundError(f"Assignment with id {assignment_id} not found")
        return await self.repository.get_status_history(assignment_id)

    async def compute_route(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
        provider: RoutingProvider,
    ) -> RouteResponse:
        """Return the route geometry between two points using the active provider."""
        try:
            result = await provider.route(
                origin=(origin_lat, origin_lon),
                destination=(destination_lat, destination_lon),
            )
        except Exception as exc:
            raise ServiceUnavailableError(
                f"Routing provider '{provider.provider_name}' failed: {exc}"
            ) from exc

        return RouteResponse(
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            destination_lat=destination_lat,
            destination_lon=destination_lon,
            duration_s=result.duration_s,
            distance_m=result.distance_m,
            polyline=result.polyline,
            provider=result.provider,
            traffic_segments=[
                {"start_index": s.start_index, "end_index": s.end_index, "speed": s.speed}
                for s in result.traffic_segments
            ],
        )

    async def optimize_assignments(
        self, request: OptimizeRequest, provider: RoutingProvider
    ) -> OptimizeResponse:
        """
        Run OR-Tools LinearSumAssignment to optimally assign adjusters to incidents.

        Pipeline:
        1. Resolve incidents and adjusters (from request body or DB).
        2. Build OSRM travel-time matrix.
        3. Solve with OR-Tools (greedy fallback if not OPTIMAL).
        4. Optionally persist assignments to DB.

        Args:
            request: OptimizeRequest with incidents, adjusters, and options.

        Returns:
            OptimizeResponse with assignments and metrics.
        """
        # 1. Resolve incidents and adjusters
        if request.use_db:
            db_incidents = await self.incident_repository.get_by_status("pending", limit=500)
            # get_available returns (Adjuster, cur_lat, cur_lon) tuples —
            # use current position when available, else home_location.
            db_adjuster_rows = await self.adjuster_repository.get_available(limit=200)
            incidents = [
                IncidentCoord(
                    incident_id=inc.id,
                    latitude=inc.latitude,
                    longitude=inc.longitude,
                )
                for inc in db_incidents
            ]
            adjusters = [
                AdjusterCoord(
                    adjuster_id=adj.id,
                    latitude=cur_lat if cur_lat is not None else adj.home_latitude,
                    longitude=cur_lon if cur_lon is not None else adj.home_longitude,
                )
                for adj, cur_lat, cur_lon in db_adjuster_rows
            ]
        else:
            incidents = request.incidents
            adjusters = request.adjusters

        if not incidents or not adjusters:
            return OptimizeResponse(
                assignments=[],
                candidates=[],
                unassigned_incident_ids=[inc.incident_id for inc in incidents],
                total_travel_min=0.0,
                median_travel_min=0.0,
                p90_travel_min=0.0,
                solver_time_s=0.0,
                n_incidents=len(incidents),
                n_adjusters=len(adjusters),
            )

        # 2. Build travel-time matrix via configured routing provider
        adj_coords = [(a.latitude, a.longitude) for a in adjusters]
        inc_coords = [(i.latitude, i.longitude) for i in incidents]

        logger.info(
            "Building time matrix: %d adjusters × %d incidents (provider=%s)",
            len(adjusters),
            len(incidents),
            provider.provider_name,
        )
        try:
            time_matrix = await provider.table(adj_coords, inc_coords)
        except Exception as exc:
            logger.error("Routing provider '%s' failed: %s", provider.provider_name, exc)
            raise ServiceUnavailableError(
                f"Routing provider '{provider.provider_name}' is not reachable"
            ) from exc

        # 3. Apply max travel time cap — mark pairs over the limit as unreachable
        max_travel_s = request.max_travel_min * 60
        capped = np.isinf(time_matrix) | (time_matrix > max_travel_s)
        if capped.any():
            logger.debug(
                "Capping %d adjuster-incident pairs exceeding %.0f min",
                int(capped.sum()),
                request.max_travel_min,
            )
            time_matrix = np.where(capped, np.inf, time_matrix)

        # 4. Solve
        t0 = time.perf_counter()
        results, unassigned_indices = assignment_solver.solve(time_matrix)
        solver_time_s = time.perf_counter() - t0

        # 4. Build top-K candidates per incident (from raw matrix, no extra HTTP calls)
        all_candidates: list[CandidateResult] = []
        if request.top_k > 1:
            for inc_idx, incident in enumerate(incidents):
                # Column inc_idx of time_matrix = travel time from each adjuster to this incident
                col = time_matrix[:, inc_idx]
                # Sort adjuster indices by travel time, skip unreachable (inf)
                ranked = sorted(
                    (i for i in range(len(adjusters)) if not np.isinf(col[i])),
                    key=lambda i: col[i],
                )
                for rank, adj_idx in enumerate(ranked[: request.top_k], start=1):
                    t_s = float(col[adj_idx])
                    all_candidates.append(
                        CandidateResult(
                            incident_id=incident.incident_id,
                            adjuster_id=adjusters[adj_idx].adjuster_id,
                            travel_time_s=t_s,
                            travel_time_min=t_s / 60,
                            rank=rank,
                        )
                    )

        # 5. Persist (optional)
        optimized: list[OptimizedAssignment] = []
        for r in results:
            adjuster = adjusters[r.adjuster_idx]
            incident = incidents[r.claim_idx]
            db_id: int | None = None

            if request.persist:
                travel_min = round(r.travel_time_s / 60)
                try:
                    assignment = await self.repository.create(
                        incident_id=incident.incident_id,
                        adjuster_id=adjuster.adjuster_id,
                        assigned_at=datetime.now(),
                        travel_time_minutes=travel_min,
                        status=AssignmentStatus.ASSIGNED,
                    )
                except IntegrityError:
                    # Another concurrent optimizer run already assigned this
                    # incident (uq_one_active_assignment_per_incident violation).
                    # Skip silently — the first writer wins.
                    logger.warning(
                        "Skipping duplicate assignment for incident_id=%d "
                        "(already assigned by concurrent request)",
                        incident.incident_id,
                    )
                    continue
                db_id = assignment.id
                # Mark incident as assigned
                await self.incident_repository.update(
                    incident.incident_id, status=IncidentStatus.ASSIGNED
                )
                # Mark adjuster as busy
                await self.adjuster_repository.update(
                    adjuster.adjuster_id, status=AdjusterStatus.BUSY
                )

            optimized.append(
                OptimizedAssignment(
                    adjuster_id=adjuster.adjuster_id,
                    incident_id=incident.incident_id,
                    travel_time_s=r.travel_time_s,
                    travel_time_min=r.travel_time_min,
                    assignment_id=db_id,
                )
            )

        unassigned_ids = [incidents[i].incident_id for i in unassigned_indices]
        travel_mins = np.array([a.travel_time_min for a in optimized])

        logger.info(
            "Optimization complete: assigned=%d, unassigned=%d, solver_time=%.2fs",
            len(optimized),
            len(unassigned_ids),
            solver_time_s,
        )

        return OptimizeResponse(
            assignments=optimized,
            candidates=all_candidates,
            unassigned_incident_ids=unassigned_ids,
            total_travel_min=float(travel_mins.sum()) if len(travel_mins) else 0.0,
            median_travel_min=float(np.median(travel_mins)) if len(travel_mins) else 0.0,
            p90_travel_min=float(np.percentile(travel_mins, 90)) if len(travel_mins) else 0.0,
            solver_time_s=solver_time_s,
            n_incidents=len(incidents),
            n_adjusters=len(adjusters),
            routing_provider=provider.provider_name,
            traffic_aware=provider.supports_traffic,
        )
