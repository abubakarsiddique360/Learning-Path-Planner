from __future__ import annotations

import json
from pathlib import Path

from learning_path_planner.cli import main

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
BACKEND = EXAMPLES / "backend-path.json"
CYCLIC = EXAMPLES / "cyclic-path.json"


def test_plan_text(capsys) -> None:
    assert main(["plan", str(BACKEND)]) == 0
    out = capsys.readouterr().out
    assert "Level 1" in out
    assert "critical path" in out


def test_plan_markdown(capsys) -> None:
    assert main(["plan", str(BACKEND), "--markdown"]) == 0
    assert "```mermaid" in capsys.readouterr().out


def test_plan_json(capsys) -> None:
    assert main(["plan", str(BACKEND), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["total_hours"] == 93.0


def test_order_lists_every_topic(capsys) -> None:
    assert main(["order", str(BACKEND)]) == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert len(lines) == 10
    assert lines[0].startswith(" 1. [L1] Python fundamentals")


def test_order_can_print_ids(capsys) -> None:
    assert main(["order", str(BACKEND), "--ids"]) == 0
    assert "python" in capsys.readouterr().out


def test_graph_command(capsys) -> None:
    assert main(["graph", str(BACKEND)]) == 0
    assert capsys.readouterr().out.startswith("flowchart LR")


def test_stats_command(capsys) -> None:
    assert main(["stats", str(BACKEND)]) == 0
    out = capsys.readouterr().out
    assert "total hours  : 93" in out
    assert "critical path: 59h" in out
    assert "ops" in out


def test_check_passes(capsys) -> None:
    assert main(["check", str(BACKEND)]) == 0
    assert "plannable" in capsys.readouterr().out


def test_check_detects_cycle(capsys) -> None:
    assert main(["check", str(CYCLIC)]) == 1
    assert "cycle detected" in capsys.readouterr().out


def test_check_json(capsys) -> None:
    assert main(["check", str(CYCLIC), "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_plan_on_cyclic_catalogue_fails(capsys) -> None:
    assert main(["plan", str(CYCLIC)]) == 1
    assert "cycle detected" in capsys.readouterr().err


def test_missing_file(tmp_path, capsys) -> None:
    assert main(["plan", str(tmp_path / "nope.json")]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_broken_json(tmp_path, capsys) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{nope}", encoding="utf-8")
    assert main(["plan", str(path)]) == 2
    assert "not valid JSON" in capsys.readouterr().err


def test_warnings_are_printed_by_check(tmp_path, capsys) -> None:
    path = tmp_path / "warn.json"
    path.write_text(json.dumps({"topics": [{"id": "a", "title": "", "hours": -3}]}), encoding="utf-8")
    assert main(["check", str(path)]) == 0
    assert "warning:" in capsys.readouterr().out
