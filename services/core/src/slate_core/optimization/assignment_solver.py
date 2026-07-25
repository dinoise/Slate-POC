"""OR-Tools LinearSumAssignment solver for adjuster-to-incident assignment."""

import logging
from dataclasses import dataclass

import numpy as np
from ortools.graph.python import linear_sum_assignment

# adjuster_optimizer is a shared library used both by notebooks and the API.
# When running inside the API, logging is already configured by setup_logging().
# When running standalone (e.g. tests), fall back to standard logging.
logger = logging.getLogger(__name__)

BIG_M = int(1e7)  # sentinel cost for unreachable or dummy pairs


@dataclass
class AssignmentResult:
    """Result of the assignment optimization."""

    adjuster_idx: int
    claim_idx: int
    travel_time_s: float

    @property
    def travel_time_min(self) -> float:
        return self.travel_time_s / 60


def _greedy_assignment(
    time_matrix: np.ndarray,
) -> tuple[list[AssignmentResult], list[int]]:
    """
    Greedy fallback: assign each claim to the nearest available adjuster.

    Used when OR-Tools does not return OPTIMAL.
    """
    n_adj, n_claims = time_matrix.shape
    available = set(range(n_adj))
    results: list[AssignmentResult] = []
    unassigned: list[int] = []

    best_times = np.nanmin(np.where(np.isinf(time_matrix), np.nan, time_matrix), axis=0)
    for ci in np.argsort(best_times):
        if not available:
            unassigned.append(int(ci))
            continue
        times = np.where([i in available for i in range(n_adj)], time_matrix[:, ci], np.inf)
        best_adj = int(np.argmin(times))
        best_t = times[best_adj]
        if np.isinf(best_t):
            unassigned.append(int(ci))
        else:
            results.append(AssignmentResult(best_adj, int(ci), float(best_t)))
            available.remove(best_adj)

    return results, unassigned


def solve(
    time_matrix: np.ndarray,
    big_m: int = BIG_M,
) -> tuple[list[AssignmentResult], list[int]]:
    """
    Solve the assignment problem optimally using OR-Tools LinearSumAssignment.

    Builds a square N×N cost matrix where N = n_claims:
    - Rows 0..n_adj-1: real adjusters with OSRM travel times (seconds, integer)
    - Rows n_adj..N-1: dummy adjusters absorbing unreachable claims (cost = big_m)

    Args:
        time_matrix: (n_adj, n_claims) matrix of travel times in seconds.
                     Use np.inf for unreachable pairs.
        big_m: Sentinel cost for dummy/unreachable assignments.

    Returns:
        Tuple of (assignments, unassigned_claim_indices).
        Falls back to greedy if solver does not reach OPTIMAL.
    """
    n_adj, n_claims = time_matrix.shape
    # Square matrix: N = max(n_adj, n_claims).
    # If n_claims > n_adj: dummy adjusters absorb unreachable claims.
    # If n_adj > n_claims: dummy claims absorb surplus adjusters.
    N = max(n_adj, n_claims)

    solver = linear_sum_assignment.SimpleLinearSumAssignment()

    # Real adjusters × real claims (inf → big_m)
    for adj_idx in range(n_adj):
        for claim_idx in range(n_claims):
            cost = time_matrix[adj_idx, claim_idx]
            c = big_m if np.isinf(cost) else int(round(cost))
            solver.add_arc_with_cost(adj_idx, claim_idx, c)

    # Dummy claims — absorb surplus adjusters when n_adj > n_claims
    for adj_idx in range(n_adj):
        for dummy_claim in range(n_claims, N):
            solver.add_arc_with_cost(adj_idx, dummy_claim, big_m)

    # Dummy adjusters — absorb surplus claims when n_claims > n_adj
    for dummy_adj in range(n_adj, N):
        for claim_idx in range(n_claims):
            solver.add_arc_with_cost(dummy_adj, claim_idx, big_m)

    # Dummy-to-dummy corner (needed when both sides have dummies, i.e. N > both)
    for dummy_adj in range(n_adj, N):
        for dummy_claim in range(n_claims, N):
            solver.add_arc_with_cost(dummy_adj, dummy_claim, 0)

    status = solver.solve()

    if status != solver.OPTIMAL:
        logger.warning(
            "OR-Tools did not reach OPTIMAL (status=%d). Falling back to greedy.", status
        )
        return _greedy_assignment(time_matrix)

    results: list[AssignmentResult] = []
    assigned_claims: set[int] = set()

    for adj_idx in range(n_adj):
        claim_idx = solver.right_mate(adj_idx)
        if claim_idx >= n_claims:
            # This adjuster was matched to a dummy claim — surplus adjuster, skip.
            continue
        raw = time_matrix[adj_idx, claim_idx]
        cost = big_m if np.isinf(raw) else int(round(raw))
        if cost < big_m:
            results.append(AssignmentResult(adj_idx, claim_idx, float(raw)))
            assigned_claims.add(claim_idx)

    # Claims not assigned to any real adjuster are unassigned
    unassigned: list[int] = [ci for ci in range(n_claims) if ci not in assigned_claims]

    logger.info(
        "OR-Tools assignment complete: assigned=%d, unassigned=%d, total_travel_s=%.0f",
        len(results),
        len(unassigned),
        sum(r.travel_time_s for r in results),
    )
    return results, unassigned
