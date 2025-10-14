from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx
from pydantic import BaseModel

from ..settings import get_settings


class HevyExercise(BaseModel):
    id: str
    name: str


class HevySet(BaseModel):
    weight: float
    reps: int
    rpe: Optional[float] = None


class HevyExerciseLog(BaseModel):
    exercise: HevyExercise
    sets: List[HevySet]


class HevyWorkout(BaseModel):
    id: str
    title: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime]
    notes: Optional[str] = None
    logs: List[HevyExerciseLog] = []


class HevyClient:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.hevy_base_url).rstrip("/")

        # Auth config: prefer HEVY_AUTH_SCHEME
        auth_scheme = (settings.hevy_auth_scheme or "bearer").lower()
        token = settings.hevy_token
        api_key_val = api_key or settings.hevy_api_key

        headers: Dict[str, str] = {"Accept": "application/json"}
        if auth_scheme == "bearer" and token:
            headers["Authorization"] = f"Bearer {token}"
        elif auth_scheme == "x-api-key" and api_key_val:
            # Set common variants observed in docs and gateways
            headers["api-key"] = api_key_val
            headers["x-api-key"] = api_key_val
            headers["X-Api-Key"] = api_key_val
        elif token:  # fallback to bearer if token provided
            headers["Authorization"] = f"Bearer {token}"
        elif api_key_val:  # fallback to API key variants if only key provided
            headers["api-key"] = api_key_val
            headers["x-api-key"] = api_key_val
            headers["X-Api-Key"] = api_key_val

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get_workouts(self, page: int = 1, page_size: int = 50) -> Dict[str, Any] | List[Any]:
        params: Dict[str, Any] = {"page": page, "pageSize": page_size}
        resp = await self._client.get("/v1/workouts", params=params)
        if resp.status_code == 401:
            # Retry with different header variants and query param
            settings = get_settings()
            api_key_val = settings.hevy_api_key
            token = settings.hevy_token
            # Try Authorization: Api-Key
            alt_headers: Dict[str, str] = {"Accept": "application/json"}
            if api_key_val:
                alt_headers.update({
                    "Authorization": f"Api-Key {api_key_val}",
                    "x-api-key": api_key_val,
                    "X-Api-Key": api_key_val,
                })
                # Also try api_key as query param on retry
                params_with_key = dict(params)
                params_with_key["api_key"] = api_key_val
                resp2 = await self._client.get("/v1/workouts", params=params_with_key, headers=alt_headers)
                if resp2.status_code < 400:
                    return resp2.json()
            if token:
                alt_headers["Authorization"] = f"Bearer {token}"
                resp3 = await self._client.get("/v1/workouts", params=params, headers=alt_headers)
                if resp3.status_code < 400:
                    return resp3.json()
        resp.raise_for_status()
        return resp.json()

    async def get_workout_detail(self, workout_id: str) -> Dict[str, Any]:
        resp = await self._client.get(f"/v1/workouts/{workout_id}")
        resp.raise_for_status()
        return resp.json()


async def fetch_latest_workouts(limit: int = 50, include_logs: bool = True) -> List[HevyWorkout]:
    client = HevyClient()
    try:
        # Paginate via page/pageSize across general endpoint
        items: List[Dict[str, Any]] = []
        fetched_pages = 0
        page = 1
        page_size = min(max(1, limit), 50)
        collected = 0
        while collected < limit:
            resp = await client._client.get("/v1/workouts", params={"page": page, "pageSize": page_size})
            if resp.status_code == 401:
                # Attempt same auth fallbacks as above inside pagination loop
                settings = get_settings()
                api_key_val = settings.hevy_api_key
                token = settings.hevy_token
                alt_headers: Dict[str, str] = {"Accept": "application/json"}
                if api_key_val:
                    alt_headers.update({
                        "Authorization": f"Api-Key {api_key_val}",
                        "api-key": api_key_val,
                        "x-api-key": api_key_val,
                        "X-Api-Key": api_key_val,
                    })
                    resp2 = await client._client.get("/v1/workouts", params={"page": page, "pageSize": page_size}, headers=alt_headers)
                    if resp2.status_code < 400:
                        resp = resp2
                if resp.status_code == 401 and token:
                    alt_headers["Authorization"] = f"Bearer {token}"
                    resp3 = await client._client.get("/v1/workouts", params={"page": page, "pageSize": page_size}, headers=alt_headers)
                    if resp3.status_code < 400:
                        resp = resp3

            resp.raise_for_status()
            data = resp.json()
            try:
                size_hint = len(data) if isinstance(data, list) else len(data.keys()) if isinstance(data, dict) else 0
                keys = list(data.keys())[:5] if isinstance(data, dict) else "list"
                print(f"[hevy] page status={resp.status_code} size={size_hint} keys={keys}")
            except Exception:
                pass

            page_items: List[Dict[str, Any]] = []
            if isinstance(data, dict):
                if isinstance(data.get("items"), list):
                    page_items = data["items"]
                elif isinstance(data.get("workouts"), list):
                    page_items = data["workouts"]
                elif isinstance(data.get("data"), list):
                    page_items = data["data"]
            elif isinstance(data, list):
                page_items = data

            items.extend(page_items)
            fetched_pages += 1
            collected += len(page_items)
            if len(page_items) == 0:
                break
            page += 1
        workouts: List[HevyWorkout] = []
        def _parse_dt(value: Optional[str]) -> Optional[datetime]:
            if not value:
                return None
            # Normalize ISO 8601 with possible trailing Z
            v = value.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(v)
            except ValueError:
                return None

        for raw in items:
            started = raw.get("start_time") or raw.get("started_at") or raw.get("startTime")
            ended = raw.get("end_time") or raw.get("ended_at") or raw.get("endTime")
            logs: List[HevyExerciseLog] = []
            # Try to parse inline logs if present
            raw_logs = raw.get("exercises") or raw.get("logs") or raw.get("exerciseLogs") or []
            try:
                for idx, rl in enumerate(raw_logs):
                    # Exercise can be nested or have title field
                    ex = rl.get("exercise") or {}
                    ex_id = str(rl.get("exercise_template_id") or ex.get("exercise_template_id") or ex.get("id") or ex.get("exerciseId") or ex.get("_id") or ex.get("uuid") or "").strip()
                    ex_name = str(rl.get("title") or ex.get("title") or ex.get("name") or rl.get("name") or rl.get("exerciseName") or "Unknown").strip()
                    
                    sets_list = rl.get("sets") or rl.get("set") or []
                    sets: List[HevySet] = []
                    for s in sets_list:
                        weight_kg = float(s.get("weight_kg") or s.get("weight") or 0)
                        reps = int(s.get("reps") or s.get("rep") or 0)
                        rpe = s.get("rpe")
                        sets.append(HevySet(weight=weight_kg, reps=reps, rpe=rpe))
                    if ex_id or ex_name != "Unknown":
                        logs.append(HevyExerciseLog(exercise=HevyExercise(id=ex_id or ex_name, name=ex_name), sets=sets))
            except Exception as e:
                print(f"[hevy] error parsing logs: {e}")
                import traceback
                traceback.print_exc()
                logs = []

            # If no logs, try fetching detail
            if include_logs and not logs:
                try:
                    detail = await client.get_workout_detail(str(raw.get("id")))
                    dlogs = detail.get("logs") or detail.get("exerciseLogs") or detail.get("exercises") or []
                    for rl in dlogs:
                        ex = rl.get("exercise") or {}
                        ex_id = str(ex.get("id") or ex.get("exerciseId") or ex.get("_id") or ex.get("uuid") or ex.get("name", "")).strip()
                        ex_name = str(ex.get("name") or rl.get("name") or rl.get("exerciseName") or "Unknown").strip()
                        sets_list = rl.get("sets") or rl.get("set") or []
                        sets: List[HevySet] = []
                        for s in sets_list:
                            weight = float(s.get("weight") or s.get("kg") or s.get("lbs") or 0)
                            reps = int(s.get("reps") or s.get("rep") or 0)
                            rpe = s.get("rpe")
                            sets.append(HevySet(weight=weight, reps=reps, rpe=rpe))
                        if ex_id or ex_name:
                            logs.append(HevyExerciseLog(exercise=HevyExercise(id=ex_id or ex_name, name=ex_name), sets=sets))
                except Exception:
                    pass

            workout = HevyWorkout(
                id=str(raw.get("id")),
                title=raw.get("title"),
                started_at=_parse_dt(str(started)) or datetime.utcnow(),
                ended_at=_parse_dt(ended if isinstance(ended, str) else None),
                notes=raw.get("notes"),
                logs=logs,
            )
            workouts.append(workout)
        try:
            print(f"[hevy] fetched {len(items)} items over {fetched_pages} page(s), parsed {len(workouts)} workouts")
        except Exception:
            pass
        return workouts
    except Exception:
        # On any API/parse error, return empty list so callers can degrade gracefully
        return []
    finally:
        await client.close()


async def fetch_all_workouts(include_logs: bool = True, page_size: int = 50) -> List[HevyWorkout]:
    client = HevyClient()
    try:
        items: List[Dict[str, Any]] = []
        fetched_pages = 0
        page = 1
        print(f"[hevy] fetch_all_workouts: starting with page_size={page_size}")
        while True:
            resp = await client._client.get("/v1/workouts", params={"page": page, "pageSize": 5})
            if resp.status_code == 404:
                print(f"[hevy] fetch_all_workouts: stopping at page {page} (404 - end of data)")
                break
            if resp.status_code == 401:
                settings = get_settings()
                api_key_val = settings.hevy_api_key
                token = settings.hevy_token
                alt_headers: Dict[str, str] = {"Accept": "application/json"}
                if api_key_val:
                    alt_headers.update({
                        "Authorization": f"Api-Key {api_key_val}",
                        "api-key": api_key_val,
                        "x-api-key": api_key_val,
                        "X-Api-Key": api_key_val,
                    })
                    resp2 = await client._client.get("/v1/workouts", params={"page": page, "pageSize": page_size}, headers=alt_headers)
                    if resp2.status_code < 400:
                        resp = resp2
                if resp.status_code == 401 and token:
                    alt_headers["Authorization"] = f"Bearer {token}"
                    resp3 = await client._client.get("/v1/workouts", params={"page": page, "pageSize": page_size}, headers=alt_headers)
                    if resp3.status_code < 400:
                        resp = resp3

            resp.raise_for_status()
            data = resp.json()
            if page == 1:
                print(f"[hevy] PAGE 1 SAMPLE: {str(data)[:500]}")
            page_items: List[Dict[str, Any]] = []
            if isinstance(data, dict):
                if isinstance(data.get("workouts"), list):
                    page_items = data["workouts"]
                elif isinstance(data.get("items"), list):
                    page_items = data["items"]
                elif isinstance(data.get("data"), list):
                    page_items = data["data"]
                else:
                    # Unknown dict shape; log keys
                    try:
                        print(f"[hevy] backfill page={page} status={resp.status_code} keys={list(data.keys())}")
                    except Exception:
                        pass
            elif isinstance(data, list):
                page_items = data

            items.extend(page_items)
            fetched_pages += 1
            try:
                print(f"[hevy] backfill page={page} status={resp.status_code} page_items={len(page_items)} total={len(items)}")
            except Exception:
                pass
            if len(page_items) == 0:
                print(f"[hevy] fetch_all_workouts: stopping at page {page} (empty page)")
                break
            page += 1

        # Reuse parsing from above
        workouts: List[HevyWorkout] = []
        def _parse_dt(value: Optional[str]) -> Optional[datetime]:
            if not value:
                return None
            v = value.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(v)
            except ValueError:
                return None

        for raw in items:
            started = raw.get("start_time") or raw.get("started_at") or raw.get("startTime")
            ended = raw.get("end_time") or raw.get("ended_at") or raw.get("endTime")
            logs: List[HevyExerciseLog] = []
            raw_logs = raw.get("exercises") or raw.get("logs") or raw.get("exerciseLogs") or []
            
            try:
                for rl in raw_logs:
                    ex = rl.get("exercise") or {}
                    # Use exercise_template_id and title from the exercise log directly
                    ex_id = str(rl.get("exercise_template_id") or ex.get("exercise_template_id") or ex.get("id") or ex.get("exerciseId") or ex.get("_id") or ex.get("uuid") or "").strip()
                    ex_name = str(rl.get("title") or ex.get("title") or ex.get("name") or rl.get("name") or rl.get("exerciseName") or "Unknown").strip()
                    
                    sets_list = rl.get("sets") or rl.get("set") or []
                    sets: List[HevySet] = []
                    for s in sets_list:
                        # Use weight_kg field
                        weight = float(s.get("weight_kg") or s.get("weight") or s.get("kg") or s.get("lbs") or 0)
                        reps = int(s.get("reps") or s.get("rep") or 0)
                        rpe = s.get("rpe")
                        sets.append(HevySet(weight=weight, reps=reps, rpe=rpe))
                    if ex_id or ex_name != "Unknown":
                        logs.append(HevyExerciseLog(exercise=HevyExercise(id=ex_id or ex_name, name=ex_name), sets=sets))
            except Exception as e:
                print(f"[hevy] error parsing exercise in backfill: {e}")
                import traceback
                traceback.print_exc()
                logs = []

            if include_logs and not logs:
                try:
                    detail = await client.get_workout_detail(str(raw.get("id")))
                    dlogs = detail.get("logs") or detail.get("exerciseLogs") or detail.get("exercises") or []
                    for rl in dlogs:
                        ex = rl.get("exercise") or {}
                        ex_id = str(ex.get("id") or ex.get("exerciseId") or ex.get("_id") or ex.get("uuid") or ex.get("name", "")).strip()
                        ex_name = str(ex.get("name") or rl.get("name") or rl.get("exerciseName") or "Unknown").strip()
                        sets_list = rl.get("sets") or rl.get("set") or []
                        sets: List[HevySet] = []
                        for s in sets_list:
                            weight = float(s.get("weight") or s.get("kg") or s.get("lbs") or 0)
                            reps = int(s.get("reps") or s.get("rep") or 0)
                            rpe = s.get("rpe")
                            sets.append(HevySet(weight=weight, reps=reps, rpe=rpe))
                        if ex_id or ex_name:
                            logs.append(HevyExerciseLog(exercise=HevyExercise(id=ex_id or ex_name, name=ex_name), sets=sets))
                except Exception:
                    pass

            workouts.append(
                HevyWorkout(
                    id=str(raw.get("id")),
                    title=raw.get("title"),
                    started_at=_parse_dt(str(started)) or datetime.utcnow(),
                    ended_at=_parse_dt(ended if isinstance(ended, str) else None),
                    notes=raw.get("notes"),
                    logs=logs,
                )
            )
        print(f"[hevy] fetch_all_workouts: parsed {len(workouts)} workouts from {len(items)} items")
        return workouts
    except Exception as e:
        print(f"[hevy] fetch_all_workouts: error {e}")
        return []
    finally:
        await client.close()
