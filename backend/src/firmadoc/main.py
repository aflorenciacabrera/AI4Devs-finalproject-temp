from fastapi import FastAPI

app = FastAPI(title="Firmadoc")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
