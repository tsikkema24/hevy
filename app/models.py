from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class Workout(SQLModel, table=True):
    id: str = Field(primary_key=True)
    title: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    notes: Optional[str] = None


class Exercise(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str


class WorkoutExercise(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    workout_id: str = Field(foreign_key="workout.id")
    exercise_id: str = Field(foreign_key="exercise.id")


class SetLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    workout_exercise_id: int = Field(foreign_key="workoutexercise.id")
    weight: float
    reps: int
    rpe: Optional[float] = None
