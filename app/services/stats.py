from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

from fastapi import APIRouter
from sqlmodel import select

from ..db import get_session
from ..models import Workout

router = APIRouter()


@router.get("/weekly-workouts")
async def weekly_workouts() -> Dict[str, List]:
    # Past 12 weeks summary of workout counts
    now = datetime.utcnow()
    start = now - timedelta(weeks=12)
    buckets: Dict[str, int] = {}

    # Initialize week buckets (ISO week format YYYY-Www)
    for i in range(12):
        week_start = (start + timedelta(weeks=i)).isocalendar()
        key = f"{week_start.year}-W{week_start.week:02d}"
        buckets[key] = 0

    async with get_session() as session:
        result = await session.exec(select(Workout).where(Workout.started_at >= start))
        workouts = result.all()
        for w in workouts:
            iso = w.started_at.isocalendar()
            key = f"{iso.year}-W{iso.week:02d}"
            if key not in buckets:
                buckets[key] = 0
            buckets[key] += 1

    labels = sorted(buckets.keys())
    data = [buckets[k] for k in labels]
    return {"labels": labels, "data": data}
