from __future__ import annotations

import os
import json
from typing import List
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlmodel import select

from .hevy_client import fetch_latest_workouts, fetch_all_workouts, HevyWorkout
from ..db import get_session
from ..models import Workout, Exercise, WorkoutExercise, SetLog


scheduler = AsyncIOScheduler()
SETTINGS_FILE = Path("settings.json")


async def sync_latest_workouts(limit: int = 50) -> int:
    try:
        workouts: List[HevyWorkout] = await fetch_latest_workouts(limit=limit, include_logs=True)
        if not workouts:
            try:
                print("[hevy] sync: no workouts returned from API")
            except Exception:
                pass
            return 0

        inserted = 0
        async with get_session() as session:
            for w in workouts:
                exists = await session.exec(select(Workout).where(Workout.id == w.id))
                if exists.first() is None:
                    dbw = Workout(id=w.id, title=w.title, started_at=w.started_at, ended_at=w.ended_at, notes=w.notes)
                    session.add(dbw)
                    inserted += 1
                else:
                    dbw = exists.first()

                # Upsert exercises and sets
                for log in w.logs:
                    # exercise
                    ex_q = await session.exec(select(Exercise).where(Exercise.id == log.exercise.id))
                    db_ex = ex_q.first()
                    if db_ex is None:
                        db_ex = Exercise(id=log.exercise.id, name=log.exercise.name)
                        session.add(db_ex)
                    # relation
                    rel_q = await session.exec(
                        select(WorkoutExercise).where(
                            WorkoutExercise.workout_id == w.id,
                            WorkoutExercise.exercise_id == db_ex.id,
                        )
                    )
                    db_rel = rel_q.first()
                    if db_rel is None:
                        db_rel = WorkoutExercise(workout_id=w.id, exercise_id=db_ex.id)
                        session.add(db_rel)
                        await session.flush()
                    # sets: insert all (id autoinc)
                    for s in log.sets:
                        session.add(
                            SetLog(
                                workout_exercise_id=db_rel.id,
                                weight=s.weight,
                                reps=s.reps,
                                rpe=s.rpe,
                            )
                        )
            await session.commit()
        try:
            print(f"[hevy] sync: inserted {inserted} new workouts (fetched {len(workouts)})")
        except Exception:
            pass
        return inserted
    except Exception:
        return 0


async def sync_all_workouts(page_size: int = 50) -> int:
    try:
        workouts: List[HevyWorkout] = await fetch_all_workouts(include_logs=True, page_size=page_size)
        if not workouts:
            try:
                print("[hevy] backfill: no workouts returned from API")
            except Exception:
                pass
            return 0

        inserted = 0
        updated = 0
        async with get_session() as session:
            for w in workouts:
                exists = await session.exec(select(Workout).where(Workout.id == w.id))
                if exists.first() is None:
                    dbw = Workout(id=w.id, title=w.title, started_at=w.started_at, ended_at=w.ended_at, notes=w.notes)
                    session.add(dbw)
                    inserted += 1
                    print(f"[hevy] sync: adding workout {w.id} ({w.title or 'Untitled'}) with {len(w.logs)} exercises")
                else:
                    updated += 1
                    if updated <= 3:
                        print(f"[hevy] sync: updating workout {w.id} ({w.title or 'Untitled'}) with {len(w.logs)} exercises")
                # Upsert exercises and sets
                for log in w.logs:
                    if inserted + updated <= 3:
                        print(f"[hevy] sync:   exercise: {log.exercise.name} ({log.exercise.id}) with {len(log.sets)} sets")
                    ex_q = await session.exec(select(Exercise).where(Exercise.id == log.exercise.id))
                    db_ex = ex_q.first()
                    if db_ex is None:
                        db_ex = Exercise(id=log.exercise.id, name=log.exercise.name)
                        session.add(db_ex)
                    rel_q = await session.exec(
                        select(WorkoutExercise).where(
                            WorkoutExercise.workout_id == w.id,
                            WorkoutExercise.exercise_id == db_ex.id,
                        )
                    )
                    db_rel = rel_q.first()
                    if db_rel is None:
                        db_rel = WorkoutExercise(workout_id=w.id, exercise_id=db_ex.id)
                        session.add(db_rel)
                        await session.flush()
                    for s in log.sets:
                        session.add(
                            SetLog(
                                workout_exercise_id=db_rel.id,
                                weight=s.weight,
                                reps=s.reps,
                                rpe=s.rpe,
                            )
                        )
            await session.commit()
            print(f"[hevy] backfill: committed {inserted} new workouts to database")
        try:
            print(f"[hevy] backfill: inserted {inserted} new workouts (fetched {len(workouts)})")
        except Exception:
            pass
        return inserted
    except Exception as e:
        print(f"[hevy] backfill: error {e}")
        return 0


def get_sync_interval() -> int:
    """Get the current sync interval in minutes from settings file"""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
                return settings.get('sync_interval_minutes', 15)
        except Exception:
            pass
    return 15  # default to 15 minutes


def update_sync_interval(interval_minutes: int) -> None:
    """Update the sync interval and reschedule the job"""
    # Save to settings file
    settings = {}
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
        except Exception:
            pass
    
    settings['sync_interval_minutes'] = interval_minutes
    
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f)
    
    # Reschedule the job
    if scheduler.running:
        scheduler.remove_job('sync_workouts')
        scheduler.add_job(
            sync_latest_workouts,
            IntervalTrigger(minutes=interval_minutes),
            id='sync_workouts',
            replace_existing=True
        )
        print(f"[hevy] scheduler: updated sync interval to {interval_minutes} minutes")


def start_scheduler():
    """Start the background scheduler with the configured interval"""
    if not scheduler.running:
        interval = get_sync_interval()
        scheduler.add_job(
            sync_latest_workouts,
            IntervalTrigger(minutes=interval),
            id='sync_workouts',
            replace_existing=True
        )
        scheduler.start()
        print(f"[hevy] scheduler: started with {interval} minute interval")
