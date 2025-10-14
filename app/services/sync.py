from __future__ import annotations

from typing import List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import select

from .hevy_client import fetch_latest_workouts, fetch_all_workouts, HevyWorkout
from ..db import get_session
from ..models import Workout, Exercise, WorkoutExercise, SetLog


scheduler = AsyncIOScheduler()


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
                    dbw = Workout(id=w.id, started_at=w.started_at, ended_at=w.ended_at, notes=w.notes)
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


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(sync_latest_workouts, CronTrigger(minute="*/15"))
    scheduler.start()


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
        async with get_session() as session:
            for w in workouts:
                exists = await session.exec(select(Workout).where(Workout.id == w.id))
                if exists.first() is None:
                    dbw = Workout(id=w.id, started_at=w.started_at, ended_at=w.ended_at, notes=w.notes)
                    session.add(dbw)
                    inserted += 1
                    print(f"[hevy] sync: adding workout {w.id} with {len(w.logs)} exercises")
                # Upsert exercises and sets
                for log in w.logs:
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
