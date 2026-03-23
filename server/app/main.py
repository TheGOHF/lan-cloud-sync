from fastapi import FastAPI

from app.api.routes import router
from app.db.session import init_db


app = FastAPI(title="LAN Cloud Sync Server")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(router)
