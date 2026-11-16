from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

app = FastAPI()


@app.get("/probe")
def probe() -> dict[str, str]:
    return {"status": "ready"}


with TestClient(app) as client:
    response = client.get("/probe")
if response.status_code != 200 or response.json() != {"status": "ready"}:
    raise SystemExit("local FastAPI/TestClient runtime returned an invalid probe response")
