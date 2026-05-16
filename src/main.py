from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routers import users, sun, shadow_analyze, routes, weather

app = FastAPI(title="bright")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(sun.router)
app.include_router(shadow_analyze.router)
app.include_router(routes.router)
app.include_router(weather.router)


@app.get("/")
def root():
    return {"message": "Hello from bright"}


@app.get("/health")
def health():
    return {"status": "ok"}
