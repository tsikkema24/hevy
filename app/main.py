from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import APIRouter
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from .settings import get_settings
from .db import init_db
from .services.sync import start_scheduler, sync_latest_workouts, sync_all_workouts
from .services.stats import router as stats_router
from .services.debug import router as debug_router

app = FastAPI(title="Hevy Dashboard")

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
app.include_router(stats_router, prefix="/api")
app.include_router(debug_router, prefix="/api")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "dashboard.html", {"request": request}
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    return templates.TemplateResponse(
        "admin.html", {"request": request}
    )


@app.get("/insights", response_class=HTMLResponse)
async def insights(request: Request):
    return templates.TemplateResponse(
        "insights.html", {"request": request}
    )


@app.get("/routines", response_class=HTMLResponse)
async def routines(request: Request):
    return templates.TemplateResponse(
        "routines.html", {"request": request}
    )


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()
    start_scheduler()


@app.post("/sync-now")
async def sync_now(request: Request):
    try:
        inserted = await sync_latest_workouts(limit=50)
        url = request.url_for("admin")
        redirect_url = str(url) + f"?synced={inserted}"
        return RedirectResponse(url=redirect_url, status_code=303)
    except Exception:
        url = request.url_for("admin")
        return RedirectResponse(url=str(url) + "?error=sync", status_code=303)


@app.post("/sync-all")
async def sync_all(request: Request):
    try:
        inserted = await sync_all_workouts(page_size=50)
        url = request.url_for("admin")
        return RedirectResponse(url=str(url) + f"?backfilled={inserted}", status_code=303)
    except Exception:
        url = request.url_for("admin")
        return RedirectResponse(url=str(url) + "?error=backfill", status_code=303)


@app.post("/reset-db")
async def reset_db(request: Request):
    try:
        from .db import engine
        from .models import SQLModel
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
            await conn.run_sync(SQLModel.metadata.create_all)
        url = request.url_for("admin")
        return RedirectResponse(url=str(url) + "?reset=1", status_code=303)
    except Exception:
        url = request.url_for("admin")
        return RedirectResponse(url=str(url) + "?error=reset", status_code=303)
