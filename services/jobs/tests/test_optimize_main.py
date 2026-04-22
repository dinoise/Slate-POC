"""Tests for optimize/main.py — assignment optimization job.

Mocks DB session, asyncpg connection, and the OR-Tools solver so these
tests run without network access or a real database.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from slate_jobs.optimize.main import _run

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_adjuster(id: int, lat: float = 19.4, lon: float = -99.1):
    from collections import namedtuple

    Row = namedtuple("AdjusterRow", ["id", "latitude", "longitude"])
    return Row(id=id, latitude=lat, longitude=lon)


def _make_incident(id: int, lat: float = 19.5, lon: float = -99.2):
    from collections import namedtuple

    Row = namedtuple("IncidentRow", ["id", "latitude", "longitude"])
    return Row(id=id, latitude=lat, longitude=lon)


def _make_assignment_result(adjuster_idx: int, claim_idx: int, travel_time_min: float = 5.0):
    r = MagicMock()
    r.adjuster_idx = adjuster_idx
    r.claim_idx = claim_idx
    r.travel_time_min = travel_time_min
    return r


def _make_db_session(adjusters=None, incidents=None, assignment_id=1):
    """Build an AsyncMock DB session that returns the given adjusters/incidents."""
    session = AsyncMock()

    adjusters_result = MagicMock()
    adjusters_result.fetchall.return_value = adjusters or []

    incidents_result = MagicMock()
    incidents_result.fetchall.return_value = incidents or []

    insert_result = MagicMock()
    # Must be a plain int — json.dumps is called on this value in the notify payload
    insert_result.scalar_one.return_value = assignment_id

    # execute returns adjusters first, incidents second, then INSERT, then UPDATEs
    session.execute.side_effect = [
        adjusters_result,
        incidents_result,
        insert_result,  # INSERT INTO assignments RETURNING id
        AsyncMock(),  # UPDATE adjusters SET status
    ]
    session.commit = AsyncMock()
    return session


# ── Tests ─────────────────────────────────────────────────────────────────────


async def test_run_exits_early_when_no_adjusters() -> None:
    mock_session = _make_db_session(adjusters=[], incidents=[_make_incident(1)])

    with (
        patch("slate_jobs.optimize.main.async_session_maker") as mock_sm,
        patch("slate_jobs.optimize.main.solve") as mock_solver,
        patch("slate_jobs.optimize.main.asyncpg.connect", new_callable=AsyncMock),
        patch("slate_jobs.optimize.main.engine") as mock_engine,
    ):
        mock_sm.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sm.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_engine.dispose = AsyncMock()

        await _run()

        mock_solver.assert_not_called()


async def test_run_exits_early_when_no_incidents() -> None:
    mock_session = _make_db_session(adjusters=[_make_adjuster(1)], incidents=[])

    with (
        patch("slate_jobs.optimize.main.async_session_maker") as mock_sm,
        patch("slate_jobs.optimize.main.solve") as mock_solver,
        patch("slate_jobs.optimize.main.asyncpg.connect", new_callable=AsyncMock),
        patch("slate_jobs.optimize.main.engine") as mock_engine,
    ):
        mock_sm.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sm.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_engine.dispose = AsyncMock()

        await _run()

        mock_solver.assert_not_called()


async def test_run_calls_solver_with_cost_matrix() -> None:
    adjusters = [_make_adjuster(1, lat=19.4, lon=-99.1)]
    incidents = [_make_incident(10, lat=19.5, lon=-99.2)]

    assignment_result = _make_assignment_result(adjuster_idx=0, claim_idx=0)
    mock_notify = AsyncMock()
    mock_notify.execute = AsyncMock()
    mock_notify.close = AsyncMock()

    # Build session with explicit scalar_one return for INSERT
    session = AsyncMock()
    adj_result = MagicMock()
    adj_result.fetchall.return_value = adjusters
    inc_result = MagicMock()
    inc_result.fetchall.return_value = incidents
    insert_result = MagicMock()
    insert_result.scalar_one.return_value = 42
    session.execute.side_effect = [adj_result, inc_result, insert_result, AsyncMock()]
    session.commit = AsyncMock()

    with (
        patch("slate_jobs.optimize.main.async_session_maker") as mock_sm,
        patch(
            "slate_jobs.optimize.main.solve", return_value=([assignment_result], [])
        ) as mock_solver,
        patch(
            "slate_jobs.optimize.main.asyncpg.connect",
            new_callable=AsyncMock,
            return_value=mock_notify,
        ),
        patch("slate_jobs.optimize.main.engine") as mock_engine,
        patch("slate_jobs.optimize.main.settings") as mock_settings,
    ):
        mock_settings.DATABASE_URL = "postgresql+asyncpg://slate:slate@localhost/slate_test"
        mock_sm.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_engine.dispose = AsyncMock()

        await _run()

        mock_solver.assert_called_once()
        cost_matrix = mock_solver.call_args[0][0]
        assert cost_matrix.shape == (1, 1)  # 1 adjuster × 1 incident


async def test_run_sends_pg_notify_per_assignment() -> None:
    adjusters = [_make_adjuster(1), _make_adjuster(2)]
    incidents = [_make_incident(10), _make_incident(11)]

    session_load = AsyncMock()
    load_result_adj = MagicMock()
    load_result_adj.fetchall.return_value = adjusters
    load_result_inc = MagicMock()
    load_result_inc.fetchall.return_value = incidents
    session_load.execute.side_effect = [load_result_adj, load_result_inc]

    session_persist = AsyncMock()
    insert_r1 = MagicMock()
    insert_r1.scalar_one.return_value = 1
    insert_r2 = MagicMock()
    insert_r2.scalar_one.return_value = 2
    session_persist.execute.side_effect = [insert_r1, MagicMock(), insert_r2, MagicMock()]
    session_persist.commit = AsyncMock()

    results = [
        _make_assignment_result(adjuster_idx=0, claim_idx=0),
        _make_assignment_result(adjuster_idx=1, claim_idx=1),
    ]
    mock_notify = AsyncMock()
    mock_notify.execute = AsyncMock()
    mock_notify.close = AsyncMock()

    with (
        patch("slate_jobs.optimize.main.async_session_maker") as mock_sm,
        patch("slate_jobs.optimize.main.solve", return_value=(results, [])),
        patch(
            "slate_jobs.optimize.main.asyncpg.connect",
            new_callable=AsyncMock,
            return_value=mock_notify,
        ),
        patch("slate_jobs.optimize.main.engine") as mock_engine,
        patch("slate_jobs.optimize.main.settings") as mock_settings,
    ):
        mock_settings.DATABASE_URL = "postgresql+asyncpg://slate:slate@localhost/slate_test"
        mock_sm.return_value.__aenter__ = AsyncMock(side_effect=[session_load, session_persist])
        mock_sm.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_engine.dispose = AsyncMock()

        await _run()

        # One pg_notify call per assignment
        assert mock_notify.execute.call_count == 2


async def test_run_closes_notify_connection_on_success() -> None:
    adjusters = [_make_adjuster(1)]
    incidents = [_make_incident(10)]

    session_load = AsyncMock()
    r_adj = MagicMock()
    r_adj.fetchall.return_value = adjusters
    r_inc = MagicMock()
    r_inc.fetchall.return_value = incidents
    session_load.execute.side_effect = [r_adj, r_inc]

    session_persist = AsyncMock()
    r_insert = MagicMock()
    r_insert.scalar_one.return_value = 1
    session_persist.execute.side_effect = [r_insert, MagicMock()]
    session_persist.commit = AsyncMock()

    mock_notify = AsyncMock()
    mock_notify.execute = AsyncMock()
    mock_notify.close = AsyncMock()

    with (
        patch("slate_jobs.optimize.main.async_session_maker") as mock_sm,
        patch("slate_jobs.optimize.main.solve", return_value=([_make_assignment_result(0, 0)], [])),
        patch(
            "slate_jobs.optimize.main.asyncpg.connect",
            new_callable=AsyncMock,
            return_value=mock_notify,
        ),
        patch("slate_jobs.optimize.main.engine") as mock_engine,
        patch("slate_jobs.optimize.main.settings") as mock_settings,
    ):
        mock_settings.DATABASE_URL = "postgresql+asyncpg://slate:slate@localhost/slate_test"
        mock_sm.return_value.__aenter__ = AsyncMock(side_effect=[session_load, session_persist])
        mock_sm.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_engine.dispose = AsyncMock()

        await _run()

        mock_notify.close.assert_awaited_once()
