"""API tests driven by the scripted fake model."""

from __future__ import annotations

from fastapi.testclient import TestClient

import specs
from drafty.agent.fake_llm import FakeLLM, json_result, text_result, tool_call_result
from drafty.agent.router import RouteLabel
from drafty.api.main import create_app
from drafty.api.ratelimit import RateLimiter
from drafty.api.routes import EXAMPLES
from drafty.api.services import RunService
from drafty.storage.db import Database
from drafty.storage.files import LocalFileStore

LIMITS = {"revision_cap": 2, "parse_retries": 2, "invalid_drafts_before_cascade": 2}


def _pass_script() -> list:
    return [
        json_result(RouteLabel(label="new_brief")),
        json_result(specs.parsed_happy()),
        tool_call_result([("finish", {})]),
        text_result("Design is fine."),
    ]


def _service(
    standards,
    tmp_path,
    script,
    *,
    render: bool = False,
    rate_limiter: RateLimiter | None = None,
    daily_cap: int | None = None,
) -> RunService:
    fake = FakeLLM(script)
    return RunService(
        db=Database(tmp_path / "drafty.db"),
        standards=standards,
        llm_factory=lambda: fake,
        file_store=LocalFileStore(tmp_path),
        data_dir=tmp_path,
        limits=dict(LIMITS),
        render=render,
        rate_limiter=rate_limiter or RateLimiter(per_hour=100),
        daily_token_cap=daily_cap,
    )


def test_start_run_and_get_state(standards, tmp_path) -> None:
    service = _service(standards, tmp_path, _pass_script())
    client = TestClient(create_app(service))
    response = client.post("/api/runs", json={"brief": "a happy road"})
    assert response.status_code == 200
    run_id = response.json()["run_id"]
    service.wait(run_id)

    state = client.get(f"/api/runs/{run_id}").json()
    assert state["state"] == "done"
    assert state["spec"] is not None
    assert any(check["rule_id"] == "HYD-CAP" for check in state["checks"])


def test_events_stream_has_types(standards, tmp_path) -> None:
    service = _service(standards, tmp_path, _pass_script())
    client = TestClient(create_app(service))
    run_id = client.post("/api/runs", json={"brief": "a happy road"}).json()["run_id"]
    service.wait(run_id)

    body = client.get(f"/api/runs/{run_id}/events").text
    assert "event: done" in body
    assert "event: model_call" in body
    assert "event: state" in body


def test_answers_resume_run(standards, tmp_path) -> None:
    script = [
        json_result(RouteLabel(label="new_brief")),
        json_result(specs.parsed_with_questions()),
        text_result("What design rainfall should I use?"),
        json_result(specs.parsed_happy()),
        tool_call_result([("finish", {})]),
        text_result("done"),
    ]
    service = _service(standards, tmp_path, script)
    client = TestClient(create_app(service))
    run_id = client.post("/api/runs", json={"brief": "example road"}).json()["run_id"]
    service.wait(run_id)

    paused = client.get(f"/api/runs/{run_id}").json()
    assert paused["state"] == "awaiting_answers"
    assert paused["questions"]

    resumed = client.post(
        f"/api/runs/{run_id}/answers", json={"answers": {"rainfall": "100 mm/h, 10-year"}}
    )
    assert resumed.status_code == 200
    service.wait(run_id)
    assert client.get(f"/api/runs/{run_id}").json()["state"] == "done"


def test_download_files(standards, tmp_path) -> None:
    service = _service(standards, tmp_path, _pass_script(), render=True)
    client = TestClient(create_app(service))
    run_id = client.post("/api/runs", json={"brief": "a happy road"}).json()["run_id"]
    service.wait(run_id)

    for name in ("drawing.dxf", "schedule.csv", "quantities.json", "preview.svg"):
        response = client.get(f"/api/runs/{run_id}/files/{name}")
        assert response.status_code == 200, name
        assert response.content

    unknown = client.get(f"/api/runs/{run_id}/files/secrets.txt")
    assert unknown.status_code == 404


def test_rate_limit(standards, tmp_path) -> None:
    service = _service(standards, tmp_path, _pass_script(), rate_limiter=RateLimiter(per_hour=1))
    client = TestClient(create_app(service))
    assert client.post("/api/runs", json={"brief": "one"}).status_code == 200
    second = client.post("/api/runs", json={"brief": "two"})
    assert second.status_code == 429


def test_daily_cap(standards, tmp_path) -> None:
    service = _service(standards, tmp_path, _pass_script(), daily_cap=0)
    client = TestClient(create_app(service))
    response = client.post("/api/runs", json={"brief": "x"})
    assert response.status_code == 429
    assert "demo limit" in response.json()["detail"]


def test_run_failure_is_reported(standards, tmp_path) -> None:
    def _boom():
        raise RuntimeError("NEBIUS_API_KEY is not set")

    service = RunService(
        db=Database(tmp_path / "drafty.db"),
        standards=standards,
        llm_factory=_boom,
        file_store=LocalFileStore(tmp_path),
        data_dir=tmp_path,
        limits=dict(LIMITS),
        render=False,
        rate_limiter=RateLimiter(per_hour=100),
    )
    client = TestClient(create_app(service))
    run_id = client.post("/api/runs", json={"brief": "x"}).json()["run_id"]
    service.wait(run_id)
    state = client.get(f"/api/runs/{run_id}").json()
    assert state["state"] == "failed"
    assert "run failed" in state["message"]


def test_unknown_run_is_404(standards, tmp_path) -> None:
    client = TestClient(create_app(_service(standards, tmp_path, _pass_script())))
    assert client.get("/api/runs/r-nope").status_code == 404


def test_examples_are_listed() -> None:
    assert len(EXAMPLES) == 4
    assert all({"id", "title", "brief", "note"} <= set(example) for example in EXAMPLES)
