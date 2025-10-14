from __future__ import annotations

from datetime import datetime, timedelta, date
from typing import Any, Dict, List
from collections import Counter

from fastapi import APIRouter
from sqlmodel import select

from ..db import get_session
from ..models import Workout, Exercise, WorkoutExercise, SetLog

router = APIRouter()

# Conversion constant
KG_TO_LBS = 2.20462

# Muscle group categorization based on exercise names
MUSCLE_GROUPS = {
    'Chest': ['bench press', 'chest fly', 'chest press', 'push up', 'dip', 'pec'],
    'Back': ['row', 'pull up', 'pulldown', 'lat pull', 'deadlift', 'shrug'],
    'Shoulders': ['shoulder press', 'lateral raise', 'front raise', 'overhead press', 'military press', 'arnold press'],
    'Biceps': ['curl', 'bicep', 'hammer curl', 'preacher curl', 'concentration curl', 'spider curl'],
    'Triceps': ['tricep', 'skull crusher', 'pushdown', 'tricep extension', 'overhead extension', 'close grip', 'dip'],
    'Legs': ['squat', 'leg press', 'leg curl', 'leg extension', 'lunge', 'calf', 'hip thrust'],
    'Core': ['crunch', 'plank', 'ab', 'sit up', 'russian twist', 'leg raise'],
    'Cardio': ['run', 'bike', 'treadmill', 'elliptical', 'rowing'],
}

def categorize_exercise(exercise_name: str) -> str:
    """Categorize an exercise based on its name"""
    name_lower = exercise_name.lower()
    
    # Check biceps first (more specific patterns)
    biceps_keywords = MUSCLE_GROUPS.get('Biceps', [])
    if any(keyword in name_lower for keyword in biceps_keywords):
        # Exclude tricep exercises that might have 'curl' in the name
        if 'tricep' not in name_lower:
            return 'Biceps'
    
    # Check triceps
    triceps_keywords = MUSCLE_GROUPS.get('Triceps', [])
    if any(keyword in name_lower for keyword in triceps_keywords):
        return 'Triceps'
    
    # Check other muscle groups
    for muscle_group, keywords in MUSCLE_GROUPS.items():
        if muscle_group in ['Biceps', 'Triceps']:
            continue  # Already checked above
        if any(keyword in name_lower for keyword in keywords):
            return muscle_group
    
    return 'Other'


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
                weight_lbs = float(s.weight) * KG_TO_LBS
                vol = weight_lbs * int(s.reps)
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
                top_items.append({"id": ex.id, "name": ex.name, "count": count})
        
        return {"exercises": top_items}


@router.get("/workout-split")
async def workout_split() -> Dict[str, Any]:
    """
    Get workout split breakdown by muscle groups
    Returns both workout counts and volume per muscle group
    """
    async with get_session() as session:
        # Get all workout exercises with their exercise info
        workout_exercises = await session.exec(select(WorkoutExercise))
        we_list = workout_exercises.all()
        
        # Get all exercises to map IDs to names
        exercises = await session.exec(select(Exercise))
        exercise_map = {ex.id: ex.name for ex in exercises.all()}
        
        # Count workouts per muscle group (unique workout_id per group)
        muscle_group_workouts: Dict[str, set] = {}
        muscle_group_exercises: Dict[str, int] = {}
        
        # For volume calculation, we need sets
        all_sets = await session.exec(select(SetLog))
        sets_by_we_id = {}
        for s in all_sets.all():
            if s.workout_exercise_id not in sets_by_we_id:
                sets_by_we_id[s.workout_exercise_id] = []
            sets_by_we_id[s.workout_exercise_id].append(s)
        
        muscle_group_volume: Dict[str, float] = {}
        
        for we in we_list:
            exercise_name = exercise_map.get(we.exercise_id, "Unknown")
            muscle_group = categorize_exercise(exercise_name)
            
            # Track workouts per muscle group
            if muscle_group not in muscle_group_workouts:
                muscle_group_workouts[muscle_group] = set()
                muscle_group_exercises[muscle_group] = 0
                muscle_group_volume[muscle_group] = 0.0
            
            muscle_group_workouts[muscle_group].add(we.workout_id)
            muscle_group_exercises[muscle_group] += 1
            
            # Calculate volume for this exercise
            if we.id in sets_by_we_id:
                for s in sets_by_we_id[we.id]:
                    try:
                        weight_lbs = float(s.weight) * KG_TO_LBS
                        vol = weight_lbs * int(s.reps)
                        muscle_group_volume[muscle_group] += vol
                    except (TypeError, ValueError):
                        continue
        
        # Convert to list format sorted by workout count
        splits = []
        for muscle_group in muscle_group_workouts:
            splits.append({
                "name": muscle_group,
                "workout_count": len(muscle_group_workouts[muscle_group]),
                "exercise_count": muscle_group_exercises[muscle_group],
                "total_volume": round(muscle_group_volume[muscle_group], 1),
            })
        
        # Sort by workout count descending
        splits.sort(key=lambda x: x["workout_count"], reverse=True)
        
        return {"splits": splits}


@router.get("/exercise/{exercise_id}/progress")
async def exercise_progress(exercise_id: str) -> Dict[str, Any]:
    """
    Get historical progress data for a specific exercise
    Returns volume over time and PR tracking
    """
    async with get_session() as session:
        # Get exercise name
        ex_result = await session.exec(select(Exercise).where(Exercise.id == exercise_id))
        exercise = ex_result.first()
        
        if not exercise:
            return {"error": "Exercise not found"}
        
        # Get all workout_exercises for this exercise
        we_result = await session.exec(
            select(WorkoutExercise).where(WorkoutExercise.exercise_id == exercise_id)
        )
        workout_exercises = we_result.all()
        
        # Get workout dates
        workout_ids = [we.workout_id for we in workout_exercises]
        workouts_result = await session.exec(
            select(Workout).where(Workout.id.in_(workout_ids))
        )
        workout_map = {w.id: w for w in workouts_result.all()}
        
        # Get all sets for these workout exercises
        we_ids = [we.id for we in workout_exercises]
        sets_result = await session.exec(
            select(SetLog).where(SetLog.workout_exercise_id.in_(we_ids))
        )
        all_sets = sets_result.all()
        
        # Group sets by workout_exercise_id
        sets_by_we = {}
        for s in all_sets:
            if s.workout_exercise_id not in sets_by_we:
                sets_by_we[s.workout_exercise_id] = []
            sets_by_we[s.workout_exercise_id].append(s)
        
        # Calculate volume and max weight per workout
        workout_data = []
        max_weight_ever = 0
        
        for we in workout_exercises:
            if we.id in sets_by_we and we.workout_id in workout_map:
                workout = workout_map[we.workout_id]
                sets = sets_by_we[we.id]
                
                # Calculate total volume for this workout
                total_volume = 0
                max_weight = 0
                total_reps = 0
                
                for s in sets:
                    try:
                        weight_kg = float(s.weight)
                        weight_lbs = weight_kg * KG_TO_LBS
                        reps = int(s.reps)
                        total_volume += weight_lbs * reps
                        max_weight = max(max_weight, weight_lbs)
                        total_reps += reps
                        max_weight_ever = max(max_weight_ever, weight_lbs)
                    except (TypeError, ValueError):
                        continue
                
                workout_data.append({
                    "date": workout.started_at.date().isoformat(),
                    "volume": round(total_volume, 1),
                    "max_weight": round(max_weight, 1),
                    "total_reps": total_reps,
                    "sets": len(sets),
                })
        
        # Sort by date
        workout_data.sort(key=lambda x: x["date"])
        
        # Calculate PRs (when max_weight increases)
        prs = []
        current_pr = 0
        for data in workout_data:
            if data["max_weight"] > current_pr:
                current_pr = data["max_weight"]
                prs.append({
                    "date": data["date"],
                    "weight": current_pr,
                })
        
        return {
            "exercise_name": exercise.name,
            "exercise_id": exercise_id,
            "workout_count": len(workout_data),
            "current_pr": round(max_weight_ever, 1) if max_weight_ever > 0 else None,
            "history": workout_data,
            "prs": prs,
        }


@router.get("/volume-trends")
async def volume_trends(weeks: int = 12) -> Dict[str, Any]:
    """
    Get volume trend analysis by muscle group over the past N weeks
    Shows whether training volume is progressing for each muscle group
    """
    async with get_session() as session:
        # Get all workouts from the past N weeks
        now = datetime.utcnow()
        start_date = now - timedelta(weeks=weeks)
        
        workouts_result = await session.exec(
            select(Workout).where(Workout.started_at >= start_date).order_by(Workout.started_at)
        )
        workouts = workouts_result.all()
        
        if not workouts:
            return {"weeks": [], "muscle_groups": {}}
        
        # Get all exercises for categorization
        exercises_result = await session.exec(select(Exercise))
        exercise_map = {ex.id: ex.name for ex in exercises_result.all()}
        
        # Get all workout exercises
        workout_exercises_result = await session.exec(select(WorkoutExercise))
        workout_exercises = workout_exercises_result.all()
        
        # Get all sets
        sets_result = await session.exec(select(SetLog))
        all_sets = sets_result.all()
        
        # Group sets by workout_exercise_id
        sets_by_we = {}
        for s in all_sets:
            if s.workout_exercise_id not in sets_by_we:
                sets_by_we[s.workout_exercise_id] = []
            sets_by_we[s.workout_exercise_id].append(s)
        
        # Create workout_id to week mapping
        workout_to_week = {}
        week_labels = []
        week_set = set()
        
        for w in workouts:
            iso = w.started_at.isocalendar()
            week_key = f"{iso.year}-W{iso.week:02d}"
            workout_to_week[w.id] = week_key
            if week_key not in week_set:
                week_set.add(week_key)
                week_labels.append(week_key)
        
        week_labels.sort()
        
        # Track volume per muscle group per week
        # muscle_groups_data[muscle_group][week] = total_volume
        muscle_groups_data = {}
        
        for we in workout_exercises:
            if we.workout_id not in workout_to_week:
                continue
                
            week_key = workout_to_week[we.workout_id]
            exercise_name = exercise_map.get(we.exercise_id, "Unknown")
            muscle_group = categorize_exercise(exercise_name)
            
            # Initialize muscle group if needed
            if muscle_group not in muscle_groups_data:
                muscle_groups_data[muscle_group] = {week: 0.0 for week in week_labels}
            
            # Calculate volume for this exercise
            if we.id in sets_by_we:
                for s in sets_by_we[we.id]:
                    try:
                        weight_lbs = float(s.weight) * KG_TO_LBS
                        vol = weight_lbs * int(s.reps)
                        muscle_groups_data[muscle_group][week_key] += vol
                    except (TypeError, ValueError):
                        continue
        
        # Format data for frontend
        # Focus on main muscle groups
        main_muscle_groups = ['Chest', 'Biceps', 'Triceps', 'Back', 'Shoulders', 'Legs']
        
        muscle_group_trends = {}
        for muscle_group in main_muscle_groups:
            if muscle_group in muscle_groups_data:
                weekly_volumes = [
                    round(muscle_groups_data[muscle_group].get(week, 0.0), 1) 
                    for week in week_labels
                ]
                
                # Calculate trend (simple linear regression or % change)
                # We'll use % change from first half to second half
                if len(weekly_volumes) >= 4:
                    mid = len(weekly_volumes) // 2
                    first_half_avg = sum(weekly_volumes[:mid]) / mid if mid > 0 else 0
                    second_half_avg = sum(weekly_volumes[mid:]) / (len(weekly_volumes) - mid) if (len(weekly_volumes) - mid) > 0 else 0
                    
                    if first_half_avg > 0:
                        trend_percentage = ((second_half_avg - first_half_avg) / first_half_avg) * 100
                    else:
                        trend_percentage = 0
                    
                    trend_direction = "increasing" if trend_percentage > 5 else "decreasing" if trend_percentage < -5 else "stable"
                else:
                    trend_percentage = 0
                    trend_direction = "stable"
                
                muscle_group_trends[muscle_group] = {
                    "weekly_volumes": weekly_volumes,
                    "trend_percentage": round(trend_percentage, 1),
                    "trend_direction": trend_direction,
                    "total_volume": round(sum(weekly_volumes), 1),
                    "avg_weekly_volume": round(sum(weekly_volumes) / len(weekly_volumes), 1) if weekly_volumes else 0
                }
        
        return {
            "weeks": week_labels,
            "muscle_groups": muscle_group_trends,
            "weeks_analyzed": len(week_labels)
        }


@router.get("/workout-predictions")
async def workout_predictions() -> Dict[str, Any]:
    """
    AI-based workout predictions with recommended weights for next session
    Analyzes recent performance and suggests progressive overload
    """
    async with get_session() as session:
        # Get all exercises
        exercises_result = await session.exec(select(Exercise))
        exercise_map = {ex.id: ex.name for ex in exercises_result.all()}
        
        # Get recent workouts (last 8 weeks for pattern analysis)
        cutoff_date = datetime.utcnow() - timedelta(weeks=8)
        workouts_result = await session.exec(
            select(Workout).where(Workout.started_at >= cutoff_date).order_by(Workout.started_at.desc())
        )
        recent_workouts = workouts_result.all()
        
        if not recent_workouts:
            return {"predictions": [], "message": "Need at least 8 weeks of data for predictions"}
        
        # Get all workout exercises and sets
        we_result = await session.exec(select(WorkoutExercise))
        all_we = we_result.all()
        
        sets_result = await session.exec(select(SetLog))
        all_sets = sets_result.all()
        
        # Group sets by workout_exercise_id
        sets_by_we = {}
        for s in all_sets:
            if s.workout_exercise_id not in sets_by_we:
                sets_by_we[s.workout_exercise_id] = []
            sets_by_we[s.workout_exercise_id].append(s)
        
        # Analyze exercise patterns - find most frequent exercises
        exercise_frequency = {}
        exercise_history = {}  # exercise_id -> list of (date, max_weight, avg_weight, total_volume, sets)
        
        for we in all_we:
            if we.exercise_id not in exercise_frequency:
                exercise_frequency[we.exercise_id] = 0
                exercise_history[we.exercise_id] = []
            exercise_frequency[we.exercise_id] += 1
            
            # Get workout date
            workout = next((w for w in recent_workouts if w.id == we.workout_id), None)
            if not workout or we.id not in sets_by_we:
                continue
            
            sets = sets_by_we[we.id]
            if not sets:
                continue
            
            weights = []
            total_volume = 0
            total_reps = 0
            
            for s in sets:
                try:
                    weight_kg = float(s.weight)
                    weight_lbs = weight_kg * KG_TO_LBS
                    reps = int(s.reps)
                    weights.append(weight_lbs)
                    total_volume += weight_lbs * reps
                    total_reps += reps
                except (TypeError, ValueError):
                    continue
            
            if weights:
                exercise_history[we.exercise_id].append({
                    "date": workout.started_at,
                    "max_weight": max(weights),
                    "avg_weight": sum(weights) / len(weights),
                    "total_volume": total_volume,
                    "sets": len(sets),
                    "total_reps": total_reps
                })
        
        # Get top 8 most frequent exercises
        top_exercises = sorted(exercise_frequency.items(), key=lambda x: x[1], reverse=True)[:8]
        
        predictions = []
        for ex_id, freq in top_exercises:
            if ex_id not in exercise_history or len(exercise_history[ex_id]) < 2:
                continue
            
            history = sorted(exercise_history[ex_id], key=lambda x: x["date"])
            recent_sessions = history[-5:]  # Last 5 sessions
            
            # Calculate trends
            recent_max_weights = [s["max_weight"] for s in recent_sessions]
            recent_volumes = [s["total_volume"] for s in recent_sessions]
            
            current_max = recent_max_weights[-1]
            avg_sets = sum(s["sets"] for s in recent_sessions) / len(recent_sessions)
            avg_reps_per_set = sum(s["total_reps"] for s in recent_sessions) / sum(s["sets"] for s in recent_sessions)
            
            # Calculate progression rate
            if len(recent_max_weights) >= 3:
                # Linear regression for weight progression
                weights_trend = recent_max_weights[-1] - recent_max_weights[0]
                sessions_count = len(recent_max_weights)
                progression_per_session = weights_trend / (sessions_count - 1) if sessions_count > 1 else 0
            else:
                progression_per_session = 0
            
            # Predict next workout weights
            # Conservative approach: 2.5-5 lbs increase if progressing, maintain if stable
            if progression_per_session > 0.5:
                # Progressing well - suggest small increase
                recommended_weight = current_max + 2.5
                confidence = "high"
                reason = "Consistent progression detected"
            elif progression_per_session > -0.5:
                # Stable - suggest same weight with volume increase
                recommended_weight = current_max
                confidence = "medium"
                reason = "Maintain weight, focus on volume/form"
            else:
                # Regressing - suggest deload
                recommended_weight = current_max * 0.9
                confidence = "medium"
                reason = "Consider deload or form check"
            
            # Round to nearest 2.5 lbs
            recommended_weight = round(recommended_weight / 2.5) * 2.5
            
            # Calculate recommended sets and reps
            recommended_sets = int(round(avg_sets))
            recommended_reps = int(round(avg_reps_per_set))
            
            # Determine muscle group for context
            exercise_name = exercise_map.get(ex_id, "Unknown")
            muscle_group = categorize_exercise(exercise_name)
            
            predictions.append({
                "exercise_id": ex_id,
                "exercise_name": exercise_name,
                "muscle_group": muscle_group,
                "current_max_weight": round(current_max, 1),
                "recommended_weight": round(recommended_weight, 1),
                "recommended_sets": recommended_sets,
                "recommended_reps": recommended_reps,
                "confidence": confidence,
                "reason": reason,
                "sessions_analyzed": len(recent_sessions),
                "progression_rate": round(progression_per_session, 2)
            })
        
        return {
            "predictions": predictions,
            "total_exercises": len(predictions),
            "analysis_period": "Last 8 weeks"
        }


@router.get("/deload-detection")
async def deload_detection() -> Dict[str, Any]:
    """
    Detect when a deload week might be beneficial
    Analyzes volume trends, performance drops, and fatigue indicators
    """
    async with get_session() as session:
        # Get workouts from last 6 weeks
        cutoff_date = datetime.utcnow() - timedelta(weeks=6)
        workouts_result = await session.exec(
            select(Workout).where(Workout.started_at >= cutoff_date).order_by(Workout.started_at)
        )
        workouts = workouts_result.all()
        
        if len(workouts) < 6:
            return {
                "needs_deload": False,
                "confidence": "low",
                "reason": "Insufficient data (need at least 6 workouts)",
                "recommendations": []
            }
        
        # Get all exercises
        exercises_result = await session.exec(select(Exercise))
        exercise_map = {ex.id: ex.name for ex in exercises_result.all()}
        
        # Get workout exercises and sets
        we_result = await session.exec(select(WorkoutExercise))
        all_we = we_result.all()
        
        sets_result = await session.exec(select(SetLog))
        all_sets = sets_result.all()
        
        # Map sets to workout exercises
        sets_by_we = {}
        for s in all_sets:
            if s.workout_exercise_id not in sets_by_we:
                sets_by_we[s.workout_exercise_id] = []
            sets_by_we[s.workout_exercise_id].append(s)
        
        # Analyze weekly volumes and performance
        workout_weeks = {}
        for w in workouts:
            week_key = f"{w.started_at.isocalendar().year}-W{w.started_at.isocalendar().week:02d}"
            if week_key not in workout_weeks:
                workout_weeks[week_key] = {
                    "total_volume": 0,
                    "total_sets": 0,
                    "workouts": [],
                    "avg_weights": []
                }
            workout_weeks[week_key]["workouts"].append(w.id)
        
        # Calculate volume per week
        for we in all_we:
            workout = next((w for w in workouts if w.id == we.workout_id), None)
            if not workout or we.id not in sets_by_we:
                continue
            
            week_key = f"{workout.started_at.isocalendar().year}-W{workout.started_at.isocalendar().week:02d}"
            if week_key not in workout_weeks:
                continue
            
            sets = sets_by_we[we.id]
            for s in sets:
                try:
                    weight_kg = float(s.weight)
                    weight_lbs = weight_kg * KG_TO_LBS
                    reps = int(s.reps)
                    workout_weeks[week_key]["total_volume"] += weight_lbs * reps
                    workout_weeks[week_key]["total_sets"] += 1
                    workout_weeks[week_key]["avg_weights"].append(weight_lbs)
                except (TypeError, ValueError):
                    continue
        
        # Sort weeks chronologically
        sorted_weeks = sorted(workout_weeks.items())
        
        if len(sorted_weeks) < 4:
            return {
                "needs_deload": False,
                "confidence": "low",
                "reason": "Need at least 4 weeks of data",
                "recommendations": []
            }
        
        # Analyze trends
        weekly_volumes = [week_data["total_volume"] for _, week_data in sorted_weeks]
        weekly_sets = [week_data["total_sets"] for _, week_data in sorted_weeks]
        
        # Check for volume drop (indicator of fatigue)
        recent_4_weeks = weekly_volumes[-4:]
        if len(recent_4_weeks) >= 4:
            first_2_avg = sum(recent_4_weeks[:2]) / 2
            last_2_avg = sum(recent_4_weeks[2:]) / 2
            volume_drop_pct = ((last_2_avg - first_2_avg) / first_2_avg * 100) if first_2_avg > 0 else 0
        else:
            volume_drop_pct = 0
        
        # Check for high volume accumulation
        avg_volume = sum(weekly_volumes) / len(weekly_volumes) if weekly_volumes else 0
        recent_avg = sum(weekly_volumes[-2:]) / 2 if len(weekly_volumes) >= 2 else 0
        volume_spike = ((recent_avg - avg_volume) / avg_volume * 100) if avg_volume > 0 else 0
        
        # Deload decision logic
        deload_indicators = []
        deload_score = 0
        
        # Indicator 1: Volume drop > 15% (possible fatigue)
        if volume_drop_pct < -15:
            deload_indicators.append(f"Volume decreased by {abs(volume_drop_pct):.1f}% in recent weeks")
            deload_score += 2
        
        # Indicator 2: Very high volume (>30% above average)
        if volume_spike > 30:
            deload_indicators.append(f"Volume is {volume_spike:.1f}% above your average")
            deload_score += 2
        
        # Indicator 3: Consecutive weeks of high volume (4+ weeks)
        if len(sorted_weeks) >= 4:
            high_volume_weeks = sum(1 for v in weekly_volumes[-4:] if v > avg_volume * 1.1)
            if high_volume_weeks >= 3:
                deload_indicators.append(f"{high_volume_weeks} consecutive weeks above average volume")
                deload_score += 1
        
        # Determine deload recommendation
        needs_deload = deload_score >= 2
        confidence = "high" if deload_score >= 3 else "medium" if deload_score >= 2 else "low"
        
        recommendations = []
        if needs_deload:
            recommendations = [
                "Reduce volume by 40-50% for the next week",
                "Maintain intensity (weight) but reduce sets and reps",
                "Focus on technique and recovery",
                "Ensure adequate sleep and nutrition",
                "Consider active recovery (light cardio, mobility work)"
            ]
            reason = "Multiple fatigue indicators detected. A deload week would support recovery and future progress."
        elif deload_score == 1:
            recommendations = [
                "Monitor performance closely",
                "Ensure recovery is prioritized (sleep, nutrition)",
                "Consider a deload if performance drops further"
            ]
            reason = "Some fatigue indicators present. Continue training but watch for additional signs."
        else:
            recommendations = [
                "Training volume appears sustainable",
                "Continue current programming",
                "Plan a deload week every 4-6 weeks as preventive maintenance"
            ]
            reason = "No immediate deload needed. Keep up the good work!"
        
        return {
            "needs_deload": needs_deload,
            "confidence": confidence,
            "deload_score": deload_score,
            "reason": reason,
            "indicators": deload_indicators,
            "recommendations": recommendations,
            "weekly_volumes": [round(v, 1) for v in weekly_volumes],
            "volume_change_pct": round(volume_drop_pct, 1),
            "weeks_analyzed": len(sorted_weeks)
        }


@router.get("/next-workout")
async def next_workout() -> Dict[str, Any]:
    """
    Suggest what to train next based on recovery time and training frequency
    Analyzes recent workout patterns and recommends muscle groups to focus on
    """
    async with get_session() as session:
        # Get ALL workouts to find true last trained dates
        all_workouts_result = await session.exec(
            select(Workout).order_by(Workout.started_at.desc())
        )
        all_workouts = all_workouts_result.all()
        
        # Also track recent workouts (last 2 weeks) for frequency calculation
        cutoff_date = datetime.utcnow() - timedelta(days=14)
        recent_workouts = [w for w in all_workouts if w.started_at >= cutoff_date]
        
        if not all_workouts:
            return {
                "suggested_focus": ["Full Body"],
                "priority": "high",
                "reason": "No workouts found. Time to get started!",
                "muscle_group_status": {},
                "ready_to_train": []
            }
        
        # Get all exercises
        exercises_result = await session.exec(select(Exercise))
        exercise_map = {ex.id: ex.name for ex in exercises_result.all()}
        
        # Get workout exercises
        we_result = await session.exec(select(WorkoutExercise))
        all_we = we_result.all()
        
        # Create workout lookup
        workout_map = {w.id: w for w in all_workouts}
        
        # Track last trained date and frequency per muscle group
        muscle_group_last_trained: Dict[str, datetime] = {}
        muscle_group_frequency: Dict[str, int] = {}
        muscle_group_workouts_recent: Dict[str, List[datetime]] = {}
        
        for we in all_we:
            workout = workout_map.get(we.workout_id)
            if not workout:
                continue
            
            exercise_name = exercise_map.get(we.exercise_id, "Unknown")
            muscle_group = categorize_exercise(exercise_name)
            
            # Track last trained across ALL workouts
            if muscle_group not in muscle_group_last_trained:
                muscle_group_last_trained[muscle_group] = workout.started_at
                muscle_group_frequency[muscle_group] = 0
                muscle_group_workouts_recent[muscle_group] = []
            else:
                if workout.started_at > muscle_group_last_trained[muscle_group]:
                    muscle_group_last_trained[muscle_group] = workout.started_at
            
            # Track frequency only for recent workouts (past 2 weeks)
            if workout.started_at >= cutoff_date:
                if workout.started_at not in muscle_group_workouts_recent[muscle_group]:
                    muscle_group_workouts_recent[muscle_group].append(workout.started_at)
                    muscle_group_frequency[muscle_group] += 1
        
        # Calculate days since last trained for each muscle group
        now = datetime.utcnow()
        main_muscle_groups = ['Chest', 'Biceps', 'Triceps', 'Back', 'Shoulders', 'Legs']
        
        muscle_group_status = {}
        for mg in main_muscle_groups:
            if mg in muscle_group_last_trained:
                days_since = (now - muscle_group_last_trained[mg]).total_seconds() / 86400
                frequency = muscle_group_frequency.get(mg, 0)
                
                # Determine recovery status
                if days_since >= 5:
                    status = "rested"
                    priority = "high"
                elif days_since >= 3:
                    status = "recovered"
                    priority = "medium"
                elif days_since >= 1:
                    status = "recovering"
                    priority = "low"
                else:
                    status = "fatigued"
                    priority = "rest"
                
                muscle_group_status[mg] = {
                    "days_since_trained": round(days_since, 1),
                    "status": status,
                    "priority": priority,
                    "frequency_2_weeks": frequency,
                    "last_trained": muscle_group_last_trained[mg].date().isoformat()
                }
            else:
                muscle_group_status[mg] = {
                    "days_since_trained": 999,
                    "status": "untrained",
                    "priority": "high",
                    "frequency_2_weeks": 0,
                    "last_trained": None
                }
        
        # Determine what to train next
        ready_groups = [
            mg for mg, status in muscle_group_status.items()
            if status["priority"] in ["high", "medium"]
        ]
        
        # Sort by days since trained (most recovered first)
        ready_groups.sort(key=lambda mg: muscle_group_status[mg]["days_since_trained"], reverse=True)
        
        # Check deload status
        deload_data = await deload_detection()
        needs_deload = deload_data.get("needs_deload", False)
        
        if needs_deload:
            suggested_focus = ["Active Recovery"]
            priority = "high"
            reason = "Deload week recommended. Focus on lighter weights, reduced volume, and recovery."
        elif not ready_groups:
            suggested_focus = ["Rest Day"]
            priority = "medium"
            reason = "All muscle groups are still recovering. Consider active recovery or a rest day."
        else:
            # Suggest top 2-3 muscle groups that are most recovered
            suggested_focus = ready_groups[:3]
            
            top_mg = suggested_focus[0]
            days = muscle_group_status[top_mg]["days_since_trained"]
            
            if days >= 5:
                priority = "high"
                reason = f"{top_mg} hasn't been trained in {int(days)} days - optimal time to train!"
            elif days >= 3:
                priority = "medium"
                reason = f"{top_mg} is recovered and ready for training."
            else:
                priority = "low"
                reason = f"{top_mg} is available but other muscle groups may be more rested."
        
        # Get workout predictions for suggested muscle groups
        predictions_data = await workout_predictions()
        relevant_predictions = []
        
        for pred in predictions_data.get("predictions", []):
            if pred["muscle_group"] in suggested_focus:
                relevant_predictions.append({
                    "exercise": pred["exercise_name"],
                    "muscle_group": pred["muscle_group"],
                    "weight": pred["recommended_weight"],
                    "sets": pred["recommended_sets"],
                    "reps": pred["recommended_reps"]
                })
        
        # Get recent workout history to show routines
        recent_workout_history = []
        for workout in all_workouts[:6]:  # Last 6 workouts
            # Get exercises for this workout
            workout_exercises = [we for we in all_we if we.workout_id == workout.id]
            
            exercises_list = []
            for we in workout_exercises:
                exercise_name = exercise_map.get(we.exercise_id, "Unknown")
                muscle_group = categorize_exercise(exercise_name)
                
                # Get sets for this exercise
                sets = []
                for s in all_we:
                    if s.id == we.id:
                        # This is a hack to get sets - we need to query them
                        break
                
                exercises_list.append({
                    "name": exercise_name,
                    "muscle_group": muscle_group
                })
            
            recent_workout_history.append({
                "id": workout.id,
                "date": workout.started_at.date().isoformat(),
                "title": getattr(workout, 'title', 'Workout'),
                "exercises": exercises_list,
                "exercise_count": len(exercises_list)
            })
        
        return {
            "suggested_focus": suggested_focus,
            "priority": priority,
            "reason": reason,
            "muscle_group_status": muscle_group_status,
            "ready_to_train": ready_groups,
            "recommended_exercises": relevant_predictions[:6],  # Top 6 exercises
            "needs_deload": needs_deload,
            "recent_workouts": recent_workout_history
        }
