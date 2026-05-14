from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routers import users

app = FastAPI(title="bright")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)


@app.get("/")
def root():
    return {"message": "Hello from bright"}


@app.get("/health")
def health():
    return {"status": "ok"}
