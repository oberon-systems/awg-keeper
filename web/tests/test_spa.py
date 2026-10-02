"""The built interface: the clients' stats page is its own entry."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from awg_panel.app import create_app
from awg_panel.config import Settings


def _client(settings: Settings, tmp_path: Path) -> TestClient:
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("panel")
    (static / "stats.html").write_text("stats")
    return TestClient(create_app(settings.model_copy(update={"static_dir": static})))


def test_stats_is_its_own_page(settings: Settings, tmp_path: Path) -> None:
    assert _client(settings, tmp_path).get("/stats").text == "stats"


def test_any_other_path_is_the_panel(settings: Settings, tmp_path: Path) -> None:
    client = _client(settings, tmp_path)
    assert client.get("/").text == "panel"
    assert client.get("/profiles").text == "panel"
