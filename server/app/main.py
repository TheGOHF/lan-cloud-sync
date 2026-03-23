from fastapi import FastAPI

from server.app.api.routes import router
from server.app.db.session import init_db


app = FastAPI(title="LAN Cloud Sync Server")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(router)
