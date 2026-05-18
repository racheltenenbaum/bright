import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.limiter import limiter
from src.routers import users, sun, shadow_analyze, routes, weather
from src.routers.routes import share_router

app = FastAPI(title="bright")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_frontend_origins = os.getenv("FRONTEND_URL", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(sun.router)
app.include_router(shadow_analyze.router)
app.include_router(routes.router)
app.include_router(share_router)
app.include_router(weather.router)


@app.get("/")
def root():
    return {"message": "Hello from bright"}


@app.get("/health")
def health():
    return {"status": "ok"}
