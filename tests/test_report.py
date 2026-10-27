from __future__ import annotations

from pathlib import Path

import pytest

from learning_path_planner.catalogue import parse_catalogue
from learning_path_planner.graph import CycleError
from learning_path_planner.report import PathReport, node_ids

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
BACKEND = parse_catalogue((EXAMPLES / "backend-path.json").read_text(encoding="utf-8"))
CYCLIC = parse_catalogue((EXAMPLES / "cyclic-path.json").read_text(encoding="utf-8"))


def test_node_ids_are_safe_and_unique() -> None:
    catalogue = parse_catalogue(
        {
            "topics": [
                {"id": "a-b", "title": "A"},
                {"id": "a b", "title": "B"},
                {"id": "9lives", "title": "C"},
                {"id": "ok", "title": "D"},
            ]
        }
    )
    aliases = node_ids(catalogue)
    assert len(set(aliases.values())) == 4
    assert aliases["ok"] == "ok"
    assert all(value.replace("_", "").isalnum() for value in aliases.values())


def test_text_report_summary() -> None:
    report = PathReport(catalogue=BACKEND, source="backend-path.json")
    text = report.render()
    assert "Backend engineer learning path" in text
    assert "10 topic(s)" in text
    assert "93h" in text
    assert "Level 5" in text
    assert "critical path 59h" in text


def test_text_report_indents_by_depth() -> None:
    text = PathReport(catalogue=BACKEND).render()
    root = next(line for line in text.splitlines() if line.strip().startswith("Python fundamentals"))
    deep = next(line for line in text.splitlines() if line.strip().startswith("Logs, metrics and traces"))
    assert len(deep) - len(deep.lstrip()) > len(root) - len(root.lstrip())
    assert "after containers" in deep


def test_markdown_report_sections() -> None:
    markdown = PathReport(catalogue=BACKEND).render_markdown()
    assert markdown.startswith("# Backend engineer learning path")
    assert "## Levels" in markdown
    assert "## Critical path" in markdown
    assert "```mermaid" in markdown
    assert "flowchart LR" in markdown
    assert "## Hours by tag" in markdown
    assert "- [ ] **Python fundamentals** - 20h" in markdown


def test_markdown_marks_tags_and_prerequisites() -> None:
    markdown = PathReport(catalogue=BACKEND).render_markdown()
    assert "`web`, `security`" in markdown
    assert "_after api_" in markdown


def test_mermaid_contains_edges_and_labels() -> None:
    mermaid = PathReport(catalogue=BACKEND).render_mermaid()
    assert mermaid.splitlines()[0] == "flowchart LR"
    assert 'python["Python fundamentals<br/>20h<br/>level 1"]' in mermaid
    assert "python --> testing" in mermaid
    assert "containers --> observability" in mermaid


def test_mermaid_has_one_edge_per_requirement() -> None:
    mermaid = PathReport(catalogue=BACKEND).render_mermaid()
    edges = [line for line in mermaid.splitlines() if "-->" in line]
    assert len(edges) == sum(len(topic.requires) for topic in BACKEND.topics)


def test_cycle_is_reported_not_raised() -> None:
    report = PathReport(catalogue=CYCLIC)
    assert report.ok is False
    assert set(report.cycle) == {"a", "b", "c"}
    assert "ERROR" in report.render()
    assert "Cannot plan" in report.render_markdown()
    with pytest.raises(CycleError):
        _ = report.order
    with pytest.raises(CycleError):
        report.render_mermaid()


def test_json_shape() -> None:
    payload = PathReport(catalogue=BACKEND, source="backend-path.json").as_dict()
    assert payload["ok"] is True
    assert payload["topics"] == 10
    assert payload["total_hours"] == 93.0
    assert payload["critical_path"]["hours"] == 59.0
    assert payload["levels"][0]["index"] == 1
    assert payload["hours_by_tag"]["ops"] == 17.0
    assert len(payload["catalogue"]) == 10


def test_json_for_cyclic_catalogue() -> None:
    payload = PathReport(catalogue=CYCLIC).as_dict()
    assert payload["ok"] is False
    assert payload["cycle"]
    assert "levels" not in payload


def test_warnings_are_surfaced() -> None:
    catalogue = parse_catalogue({"topics": [{"id": "a", "title": "", "hours": 0}]})
    report = PathReport(catalogue=catalogue)
    assert len(report.warnings) == 2
    assert "warning(s)" in report.render()
    assert "## Warnings" in report.render_markdown()
