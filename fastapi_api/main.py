import os

# ───────────────────────────────────────────────
# ✅ Bootstrap Django *before* anything else
# ───────────────────────────────────────────────
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "paulines.settings")

import django
django.setup()

# ───────────────────────────────────────────────
# Now safe to import everything else
# ───────────────────────────────────────────────
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.wsgi import WSGIMiddleware
from fastapi.staticfiles import StaticFiles
from django.core.wsgi import get_wsgi_application
from django.conf import settings


from fastapi_api.core.exceptions import register_exception_handlers
from fastapi_api.core.standard_response import StandardResponse
from fastapi_api.api.v1.router import api_router  # ✅ correct import


# ───────────────────────────────────────────────
# FastAPI app
# ───────────────────────────────────────────────
app = FastAPI(
    title="Paulines Missal Unified API",
    version="1.0",
    description="Unified API combining Django Admin + FastAPI Missal endpoints",
    root_path="/api",  # ✅ crucial line for /api/docs to exist
)

# ───────────────────────────────────────────────
# CORS Middleware
# ───────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve Django collected static files
app.mount(
    "/static",
    StaticFiles(directory=str(settings.STATIC_ROOT)),
    name="static",
)
# ───────────────────────────────────────────────
# Mount Django Admin
# ───────────────────────────────────────────────
django_app = get_wsgi_application()
app.mount("/admin", WSGIMiddleware(django_app))

# ───────────────────────────────────────────────
# Exception Handlers
# ───────────────────────────────────────────────
register_exception_handlers(app)

# ───────────────────────────────────────────────
# Routers (centralized API registry)
# ───────────────────────────────────────────────
app.include_router(api_router)

# ───────────────────────────────────────────────
# Root Endpoint
# ───────────────────────────────────────────────
@app.get("/")
async def root():
    return StandardResponse.ok(
        message="Paulines Missal unified server is running.",
        data={
            "admin": "/admin/",
            "readings_api": "/api/v1/readings",
            "search_api": "/api/v1/readings/search",
            "season_api": "/api/v1/readings/season/{season_name}",
        },
    )
