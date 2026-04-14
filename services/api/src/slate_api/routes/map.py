"""Map and simulation interface routes."""
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["map"])
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/", response_class=HTMLResponse)
async def index_view(request: Request) -> HTMLResponse:
    """Serve navigation index."""
    return templates.TemplateResponse(request, "index.html")


@router.get("/map", response_class=HTMLResponse)
async def map_view(request: Request) -> HTMLResponse:
    """Serve interactive demo map."""
    return templates.TemplateResponse(request, "map.html")


@router.get("/reporter", response_class=HTMLResponse)
async def reporter_view(request: Request) -> HTMLResponse:
    """Serve incident reporter interface."""
    return templates.TemplateResponse(request, "reporter.html")


@router.get("/adjuster", response_class=HTMLResponse)
async def adjuster_view(request: Request) -> HTMLResponse:
    """Serve adjuster real-time assignment interface."""
    return templates.TemplateResponse(request, "adjuster.html")


@router.get("/admin", response_class=HTMLResponse)
async def admin_view(request: Request) -> HTMLResponse:
    """Serve user management admin interface."""
    return templates.TemplateResponse(request, "admin.html")
