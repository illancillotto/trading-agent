from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI(title="Trading Agent API")

# Health check endpoint
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "message": "Trading Agent API is running"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    assets_dir = os.path.join(static_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.on_event("startup")
def on_startup():
    """Initialize services on startup"""
    print("Trading Agent API started")
    # TODO: Initialize database, services, etc.


@app.on_event("shutdown")
def on_shutdown():
    """Cleanup on shutdown"""
    print("Trading Agent API shutting down")
    # TODO: Cleanup services


# Serve frontend index.html for root and SPA routes
@app.get("/")
async def serve_root():
    """Serve the frontend index.html for root route"""
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    index_path = os.path.join(static_dir, "index.html")

    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        return {"message": "Frontend not built yet"}

# Catch-all route for SPA routing (must be last)
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve the frontend index.html for SPA routes that don't match API/static"""
    # Skip API and static routes
    if full_path.startswith("api") or full_path.startswith("static") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not found")

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    index_path = os.path.join(static_dir, "index.html")

    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        return {"message": "Frontend not built yet"}
