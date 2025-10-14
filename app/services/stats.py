from __future__ import annotations

from datetime import datetime, timedelta, date
from typing import Any, Dict, List

from fastapi import APIRouter
from sqlmodel import select

from ..db import get_session
from ..models import Workout, Exercise, WorkoutExercise, SetLog

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


@router.get("/heatmap-year")
async def heatmap_year() -> Dict[str, Any]:
    # GitHub-style heatmap for past 365 days
    today = date.today()
    start_date = today - timedelta(days=364)
    
    # Create a dict for all days
    day_counts: Dict[str, int] = {}
    current = start_date
    while current <= today:
        day_counts[current.isoformat()] = 0
        current += timedelta(days=1)
    
    async with get_session() as session:
        result = await session.exec(
            select(Workout).where(Workout.started_at >= datetime.combine(start_date, datetime.min.time()))
        )
        workouts = result.all()
        for w in workouts:
            day_key = w.started_at.date().isoformat()
            if day_key in day_counts:
                day_counts[day_key] += 1
    
    # Convert to list of {date, count} for frontend
    days = [{"date": k, "count": v} for k, v in sorted(day_counts.items())]
    return {"days": days, "start_date": start_date.isoformat(), "end_date": today.isoformat()}


@router.get("/summary")
async def summary() -> Dict[str, Any]:
    # Overall summary stats
    async with get_session() as session:
        # Total workouts
        workout_result = await session.exec(select(Workout))
        total_workouts = len(workout_result.all())
        
        # Unique exercises (count distinct workout_exercises)
        workout_exercises = await session.exec(select(WorkoutExercise))
        unique_exercise_ids = set(we.exercise_id for we in workout_exercises.all())
        total_exercises = len(unique_exercise_ids)
        
        # Total sets
        sets_result = await session.exec(select(SetLog))
        all_sets = sets_result.all()
        total_sets = len(all_sets)
        
        # Total volume (weight * reps) - weight is in kg, convert to lbs
        total_volume = 0
        for s in all_sets:
            try:
                vol = float(s.weight) * int(s.reps)
                total_volume += vol
            except (TypeError, ValueError):
                continue
        
        # Weeks with at least 1 workout
        workouts_ordered = await session.exec(select(Workout).order_by(Workout.started_at))
        workouts_list = workouts_ordered.all()
        
        weeks_with_workout_current = 0
        weeks_with_workout_longest = 0
        if workouts_list:
            # Get unique weeks sorted chronologically
            workout_weeks = sorted(set((w.started_at.isocalendar().year, w.started_at.isocalendar().week) for w in workouts_list))
            
            # Count consecutive weeks from now going back
            today = date.today()
            current_year, current_week, _ = today.isocalendar()
            temp_year, temp_week = current_year, current_week
            
            while (temp_year, temp_week) in workout_weeks:
                weeks_with_workout_current += 1
                # Go back one week
                temp_date = date.fromisocalendar(temp_year, temp_week, 1) - timedelta(weeks=1)
                temp_year, temp_week, _ = temp_date.isocalendar()
            
            # Find longest streak of consecutive weeks
            if workout_weeks:
                current_streak = 1
                for i in range(1, len(workout_weeks)):
                    prev_year, prev_week = workout_weeks[i-1]
                    curr_year, curr_week = workout_weeks[i]
                    
                    # Check if consecutive weeks
                    prev_date = date.fromisocalendar(prev_year, prev_week, 1)
                    curr_date = date.fromisocalendar(curr_year, curr_week, 1)
                    
                    if (curr_date - prev_date).days <= 7:
                        current_streak += 1
                        weeks_with_workout_longest = max(weeks_with_workout_longest, current_streak)
                    else:
                        current_streak = 1
                weeks_with_workout_longest = max(weeks_with_workout_longest, current_streak)
        
        return {
            "total_workouts": total_workouts,
            "total_exercises": total_exercises,
            "total_sets": total_sets,
            "total_volume": round(total_volume, 1),
            "weeks_current": weeks_with_workout_current,
            "weeks_longest": weeks_with_workout_longest,
        }


@router.get("/top-exercises")
async def top_exercises(limit: int = 10) -> Dict[str, Any]:
    # Top exercises by frequency
    async with get_session() as session:
        workout_exercises = await session.exec(select(WorkoutExercise))
        we_list = workout_exercises.all()
        
        # Count by exercise
        exercise_counts: Dict[str, int] = {}
        for we in we_list:
            exercise_counts[we.exercise_id] = exercise_counts.get(we.exercise_id, 0) + 1
        
        # Get exercise names and sort
        top_items = []
        for ex_id, count in sorted(exercise_counts.items(), key=lambda x: x[1], reverse=True)[:limit]:
            ex_result = await session.exec(select(Exercise).where(Exercise.id == ex_id))
            ex = ex_result.first()
            if ex:
                top_items.append({"name": ex.name, "count": count})
        
        return {"exercises": top_items}
