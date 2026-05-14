from fastapi import FastAPI

app = FastAPI(title="bright")


@app.get("/")
def root():
    return {"message": "Hello from bright"}


@app.get("/health")
def health():
    return {"status": "ok"}
