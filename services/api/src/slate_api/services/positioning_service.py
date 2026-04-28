"""Greedy positioning algorithm — uses demand_predictions DB table."""

import math

import h3
import pandas as pd
from geoalchemy2.functions import ST_GeomFromText, ST_MakePoint, ST_SetSRID
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.adjuster import Adjuster
from ..models.adjuster_position import AdjusterPosition
from ..repositories.adjuster_position_repository import AdjusterPositionRepository
from ..repositories.demand_prediction_repository import DemandPredictionRepository
from ..schemas.recommendation import (
    RecommendationItem,
    RecommendationRequest,
    RecommendationResponse,
)

SPEED_KMH = 40.0
DEMAND_LIMIT = 5000


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def _neighbour_penalty(
    hex_id: str, reserved: set[str], hex_demand: dict[str, float], k_rings: int
) -> float:
    """Sum of pred_abs of reserved hexagons within k_rings H3 rings of hex_id.

    This implements the spatial penalty term from the p-median objective:
        penalty = Σ demand(hex') for hex' ∈ grid_disk(hex_id, k_rings) ∩ reserved

    A high penalty means the candidate is close to already-covered hexagons,
    discouraging concentration and promoting geographic dispersion.
    """
    neighbours = h3.grid_disk(hex_id, k_rings)
    return sum(hex_demand.get(n, 0.0) for n in neighbours if n in reserved)


def _greedy(
    adj_df: pd.DataFrame,
    demand_df: pd.DataFrame,
    radio_km: float,
    umbral_gain: float,
    spread_factor: float = 0.0,
    spread_rings: int = 3,
) -> list[dict]:
    """Greedy positioning with optional p-median-inspired dispersion penalty.

    Scoring function per candidate hex:
        score = pred_abs - spread_factor * neighbour_penalty(hex, reserved, k_rings)

    With spread_factor=0 this reduces to the original demand-only greedy.
    With spread_factor>0 candidates near already-reserved hexagons are penalised,
    pushing adjusters to spread across the territory (p-median spirit).
    """
    demand_sorted = demand_df.sort_values("pred_abs", ascending=False).reset_index(drop=True)
    hex_demand = demand_df.set_index("h3_r8")["pred_abs"].to_dict()

    # Pre-reserve every hex that is already occupied by an adjuster so that
    # no other adjuster can move into an already-covered cell.
    reserved: set[str] = {h for h in adj_df["h3_r8"].dropna() if h}

    results = []

    for _, adj in adj_df.iterrows():
        current_hex = adj.get("h3_r8")
        current_demand = hex_demand.get(current_hex, 0.0) if current_hex else 0.0
        best = None
        best_score = umbral_gain  # minimum net score to trigger a move
        best_gain = 0.0
        best_dist = 0.0

        for _, hex_row in demand_sorted.iterrows():
            # Skip occupied hexes (including this adjuster's own current hex)
            if hex_row["h3_r8"] in reserved:
                continue
            dist = _haversine_km(adj["lat"], adj["lon"], hex_row["lat"], hex_row["lon"])
            if dist > radio_km:
                continue

            raw_gain = hex_row["pred_abs"] - current_demand

            # p-median-inspired dispersion penalty: subtract the demand weight
            # of neighbouring reserved hexagons scaled by spread_factor.
            penalty = 0.0
            if spread_factor > 0.0:
                penalty = spread_factor * _neighbour_penalty(
                    hex_row["h3_r8"], reserved, hex_demand, spread_rings
                )

            score = raw_gain - penalty
            if score > best_score:
                best_score = score
                best_gain = raw_gain
                best = hex_row
                best_dist = dist

        if best is not None:
            # Free the adjuster's current hex so a subsequent adjuster can move there
            if current_hex:
                reserved.discard(current_hex)
            reserved.add(best["h3_r8"])
            results.append(
                {
                    "adjuster_id": int(adj["adjuster_id"]),
                    "adjuster_name": adj["adjuster_name"],
                    "current_hex": current_hex,
                    "recommended_hex": best["h3_r8"],
                    "recommended_lat": float(best["lat"]),
                    "recommended_lon": float(best["lon"]),
                    "demand_gain": round(float(best_gain), 2),
                    "distance_km": round(best_dist, 2),
                    "eta_min": round(best_dist / SPEED_KMH * 60, 1),
                    "reason": f"demanda predicha {best['pred_abs']:.1f} siniestros, sin cobertura actual",
                }
            )

    return results


class PositioningService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._pos_repo = AdjusterPositionRepository(db)
        self._demand_repo = DemandPredictionRepository(db)

    async def _seed_initial_scenario(self) -> list[AdjusterPosition]:
        """Populate scenario='initial' from home_lat/lon of all available adjusters.

        Called automatically by recommend() when 'initial' has no rows so that
        the optimizer never fails on first use. Only seeds adjusters whose
        status is 'available' and is_active is True — busy/offline adjusters
        are intentionally excluded because the optimizer only moves available ones.
        """
        from ..repositories.adjuster_repository import AdjusterRepository

        adj_repo = AdjusterRepository(self._db)
        # get_available() without lat/lon returns all available adjusters
        rows = await adj_repo.get_available(limit=500)
        if not rows:
            return []

        new_positions: list[AdjusterPosition] = []
        for adjuster, _cur_lat, _cur_lon in rows:
            lat = adjuster.home_latitude
            lon = adjuster.home_longitude
            h3_r8 = h3.latlng_to_cell(lat, lon, 8)
            wkt = f"POINT({lon} {lat})"
            new_positions.append(
                AdjusterPosition(
                    adjuster_id=adjuster.id,
                    lat=lat,
                    lon=lon,
                    location=ST_GeomFromText(wkt, 4326),
                    h3_r8=h3_r8,
                    scenario="initial",
                    source="home_location",
                    demand_score=None,
                    cluster_id=None,
                    hora_num=None,
                    dia_semana_num=None,
                )
            )
        await self._pos_repo.bulk_insert(new_positions)
        return new_positions

    async def recommend(self, req: RecommendationRequest) -> RecommendationResponse:
        positions = await self._pos_repo.get_by_scenario(req.scenario)
        if not positions:
            if req.scenario == "initial":
                positions = await self._seed_initial_scenario()
            if not positions:
                raise ValueError(f"Scenario '{req.scenario}' has no positions")

        adj_df = pd.DataFrame(
            [
                {
                    "adjuster_id": p.adjuster_id,
                    "adjuster_name": p.adjuster.full_name
                    if p.adjuster
                    else f"Ajustador {p.adjuster_id}",
                    "lat": p.lat,
                    "lon": p.lon,
                    "h3_r8": p.h3_r8,
                }
                for p in positions
            ]
        )

        demand_preds = await self._demand_repo.get_by_slot(
            hora_num=req.hora_num,
            dia_semana_num=req.dia_semana_num,
            limit=DEMAND_LIMIT,
        )
        if not demand_preds:
            raise ValueError(
                f"No demand predictions found for hora_num={req.hora_num}, dia_semana_num={req.dia_semana_num}. "
                "Run scripts/generate_demand_predictions.py first."
            )

        demand_df = pd.DataFrame(
            [
                {
                    "h3_r8": p.h3_r8,
                    "pred_abs": p.pred_abs,
                    "lat": p.lat,
                    "lon": p.lon,
                }
                for p in demand_preds
            ]
        )

        raw = _greedy(
            adj_df,
            demand_df,
            req.radio_km,
            req.umbral_gain,
            spread_factor=req.spread_factor,
            spread_rings=req.spread_rings,
        )

        saved_as = None
        if req.save_as_scenario and raw:
            saved_as = req.save_as_scenario
            await self._save_recommendations(req, positions, raw, saved_as)

        items: list[RecommendationItem] = [RecommendationItem(**r) for r in raw]
        return RecommendationResponse(
            scenario_source=req.scenario,
            hora_num=req.hora_num,
            dia_semana_num=req.dia_semana_num,
            total_adjusters=len(positions),
            adjusters_to_move=len(items),
            recommendations=items,
            saved_as=saved_as,
        )

    async def _save_recommendations(
        self,
        req: RecommendationRequest,
        original_positions: list[AdjusterPosition],
        recs: list[dict],
        scenario_name: str,
    ) -> None:
        await self._pos_repo.delete_scenario(scenario_name)

        rec_by_adjuster_id = {r["adjuster_id"]: r for r in recs}

        new_positions: list[AdjusterPosition] = []
        for orig in original_positions:
            if orig.adjuster_id in rec_by_adjuster_id:
                rec = rec_by_adjuster_id[orig.adjuster_id]
                lat = rec["recommended_lat"]
                lon = rec["recommended_lon"]
                h3_r8 = h3.latlng_to_cell(lat, lon, 8)
                source = "greedy_optimizer"
                demand_score = rec["demand_gain"]
                cluster_id = None
            else:
                lat = orig.lat
                lon = orig.lon
                h3_r8 = orig.h3_r8
                source = orig.source
                demand_score = orig.demand_score
                cluster_id = orig.cluster_id

            wkt = f"POINT({lon} {lat})"
            new_positions.append(
                AdjusterPosition(
                    adjuster_id=orig.adjuster_id,
                    lat=lat,
                    lon=lon,
                    location=ST_GeomFromText(wkt, 4326),
                    h3_r8=h3_r8,
                    scenario=scenario_name,
                    source=source,
                    demand_score=demand_score,
                    cluster_id=cluster_id,
                    hora_num=req.hora_num,
                    dia_semana_num=req.dia_semana_num,
                )
            )

        await self._pos_repo.bulk_insert(new_positions)

        # Update home_location on adjusters that moved so that
        # GET /adjusters/available/ reflects their new position
        for rec in recs:
            lat = rec["recommended_lat"]
            lon = rec["recommended_lon"]
            await self._db.execute(
                update(Adjuster)
                .where(Adjuster.id == rec["adjuster_id"])
                .values(
                    home_latitude=lat,
                    home_longitude=lon,
                    home_location=ST_SetSRID(ST_MakePoint(lon, lat), 4326),
                )
            )
        await self._db.commit()
