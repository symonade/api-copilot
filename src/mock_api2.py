from fastapi import FastAPI

app = FastAPI(title="Scheduler API (Mock)")


@app.get("/status")
def status():
    return {"service": "scheduler", "ok": True}


@app.get("/schedules")
def list_schedules():
    return [
        {"id": "SCH-1", "projectId": "PROJ-ABC123", "milestone": "Concrete pour", "date": "2025-11-05"}
    ]

