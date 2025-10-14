from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from .hevy_client import HevyClient

router = APIRouter()


@router.get("/debug/hevy")
async def debug_hevy() -> Dict[str, Any]:
    client = HevyClient()
    try:
        # Try both endpoints with a small limit
        r1 = await client._client.get("/v1/users/me/workouts", params={"limit": 5})
        d1 = {
            "status": r1.status_code,
            "json": (r1.json() if r1.headers.get("content-type", "").startswith("application/json") else None),
            "text": (await r1.aread()).decode(errors="ignore") if not r1.headers.get("content-type", "").startswith("application/json") else None,
        }
        r2 = await client._client.get("/v1/workouts", params={"limit": 5})
        d2 = {
            "status": r2.status_code,
            "json": (r2.json() if r2.headers.get("content-type", "").startswith("application/json") else None),
            "text": (await r2.aread()).decode(errors="ignore") if not r2.headers.get("content-type", "").startswith("application/json") else None,
        }
        return {"users_me_workouts": d1, "workouts": d2}
    finally:
        await client.close()

@router.get("/debug/auth")
async def debug_auth() -> Dict[str, Any]:
    from ..settings import get_settings
    s = get_settings()
    return {
        "hevy_auth_scheme": s.hevy_auth_scheme,
        "hevy_base_url": s.hevy_base_url,
        "has_token": bool(s.hevy_token),
        "has_api_key": bool(s.hevy_api_key),
    }

@router.get("/debug/backfill")
async def debug_backfill() -> Dict[str, Any]:
    from .hevy_client import HevyClient
    client = HevyClient()
    try:
        # Test first page with detailed logging
        resp = await client._client.get("/v1/workouts", params={"page": 1, "pageSize": 5})
        data = resp.json() if resp.status_code == 200 else None
        return {
            "status": resp.status_code,
            "headers": dict(resp.headers),
            "data_keys": list(data.keys()) if isinstance(data, dict) else "not_dict",
            "data_type": type(data).__name__,
            "data_sample": str(data)[:500] if data else None,
        }
    finally:
        await client.close()
