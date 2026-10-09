"""HTTP routes for runs, files and example briefs."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from drafty.api.sse import event_stream

router = APIRouter(prefix="/api")

FILE_MEDIA_TYPES = {
    "drawing.dxf": "application/octet-stream",
    "preview.svg": "image/svg+xml",
    "schedule.csv": "text/csv",
    "quantities.json": "application/json",
}

EXAMPLES = [
    {
        "id": "residential",
        "title": "Residential access road (example from the design docs)",
        "brief": (
            "300 m gravel access road in a residential area, 6 m carriageway with 1 m shoulders, "
            "falling from 1,185 m at the start to 1,179 m at the end. Lined trapezoidal drains on "
            "both sides, discharging to an existing channel at the low end. A 600 mm pipe culvert "
            "at chainage 150 to take the right drain across. Each side collects about 1.2 ha of "
            "roofs and compounds. Test rainfall: 100 mm/h, 10-year return period."
        ),
        "note": "Test rainfall is an example input, not a design value.",
    },
    {
        "id": "market",
        "title": "Market street, one large catchment",
        "brief": (
            "400 m tarmac road through a market area, 7 m carriageway, 1.5 m walkways. Falls 1% "
            "the whole way. Left side takes runoff from about 3.5 ha of roofs and paved yards. "
            "Right side about 0.8 ha. Drains discharge to the river channel at the low end. "
            "Test rainfall: 100 mm/h, 10-year return period."
        ),
        "note": "Test rainfall is an example input, not a design value.",
    },
    {
        "id": "hillside",
        "title": "Steep hillside road",
        "brief": (
            "250 m hillside access road, 5 m carriageway with 0.5 m shoulders, falling 8% from "
            "1,320 m to 1,300 m. Concrete drains both sides. Test rainfall: 120 mm/h, 25-year "
            "return period."
        ),
        "note": "Test rainfall is an example input, not a design value.",
    },
    {
        "id": "flat",
        "title": "Very flat road",
        "brief": (
            "180 m flat road on the valley floor, 6 m carriageway, 1 m shoulders, level at about "
            "95 m. Drains both sides need a fall to the outlet at the low end. "
            "Test rainfall: 90 mm/h, 5-year return period."
        ),
        "note": "Test rainfall is an example input, not a design value.",
    },
]


class RunRequest(BaseModel):
    brief: str


class AnswersRequest(BaseModel):
    answers: dict[str, str] | str


def _service(request: Request):
    return request.app.state.service


@router.post("/runs")
def start_run(request: Request, payload: RunRequest) -> dict:
    service = _service(request)
    if not payload.brief.strip():
        raise HTTPException(status_code=422, detail="brief must not be empty")
    client_ip = request.client.host if request.client else "unknown"
    service.rate_limiter.check(client_ip, service.daily_used)
    return {"run_id": service.start(payload.brief)}


@router.get("/runs/{run_id}")
def get_run(run_id: str, request: Request) -> dict:
    run = _service(request).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@router.get("/runs/{run_id}/events")
def run_events(
    run_id: str,
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    service = _service(request)
    if service.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="run not found")
    last = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0
    return StreamingResponse(
        event_stream(service.db, run_id, last_event_id=last),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@router.post("/runs/{run_id}/answers")
def answer_run(run_id: str, payload: AnswersRequest, request: Request) -> dict:
    service = _service(request)
    run = service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    if run["state"] != "awaiting_answers":
        raise HTTPException(status_code=409, detail="run is not waiting for answers")
    service.resume(run_id, payload.answers)
    return {"status": "resumed"}


@router.get("/runs/{run_id}/files/{name}")
def get_file(run_id: str, name: str, request: Request) -> FileResponse:
    service = _service(request)
    if name not in FILE_MEDIA_TYPES:
        raise HTTPException(status_code=404, detail="unknown file")
    if not service.file_store.exists(run_id, name):
        raise HTTPException(status_code=404, detail="file not ready")
    return FileResponse(
        service.file_store.local_path(run_id, name),
        media_type=FILE_MEDIA_TYPES[name],
        filename=name,
    )


@router.get("/examples")
def list_examples() -> dict:
    return {"examples": EXAMPLES}
