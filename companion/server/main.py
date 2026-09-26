"""FastAPI main application for Picoripi Companion Server."""
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from companion.server.api import create_api_router
from companion.server.config import (
    AUTH_TOKEN,
    CORS_ORIGINS,
    DEFAULT_DATA_DIR,
    DEFAULT_HOST,
    DEFAULT_PORT,
    WEB_DIR,
)
from companion.server.storage import StorageManager


def create_app(data_dir: Path = DEFAULT_DATA_DIR, auth_token: str = AUTH_TOKEN) -> FastAPI:
    app = FastAPI(
        title="Picoripi Companion API",
        description="Mobile companion server for Picoripi glossary review and synchronization",
        version="0.3.128-dev",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    storage = StorageManager(data_dir)
    api_router = create_api_router(storage, auth_token=auth_token)
    app.include_router(api_router)

    # Mount static assets for the mobile PWA
    if WEB_DIR.exists():
        app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

    return app


app = create_app()


def run():
    import uvicorn
    print(f"Starting Picoripi Companion Server on http://{DEFAULT_HOST}:{DEFAULT_PORT}")
    uvicorn.run(app, host=DEFAULT_HOST, port=DEFAULT_PORT)


if __name__ == "__main__":
    run()
