from __future__ import annotations

import json
from pathlib import Path

import pytest

from learning_path_planner.catalogue import CatalogueError, parse_catalogue

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

SIMPLE = {
    "title": "Small path",
    "topics": [
        {"id": "a", "title": "Alpha", "hours": 4},
        {"id": "b", "title": "Beta", "hours": 2, "requires": ["a"], "tags": ["core"]},
    ],
}


def test_parses_topics() -> None:
    catalogue = parse_catalogue(SIMPLE)
    assert catalogue.title == "Small path"
    assert catalogue.ids == ["a", "b"]
    assert catalogue.total_hours == 6.0
    assert catalogue.topics[1].requires == ("a",)
    assert catalogue.topics[1].tags == ("core",)


def test_accepts_a_json_string() -> None:
    catalogue = parse_catalogue(json.dumps(SIMPLE))
    assert len(catalogue.topics) == 2


def test_default_title_and_hours() -> None:
    catalogue = parse_catalogue({"topics": [{"id": "a", "title": "Alpha"}]})
    assert catalogue.title == "Learning path"
    assert catalogue.topics[0].hours == 1.0


def test_missing_title_falls_back_to_id_with_warning() -> None:
    catalogue = parse_catalogue({"topics": [{"id": "a", "title": "  "}]})
    assert catalogue.topics[0].title == "a"
    assert "no title" in catalogue.warnings[0]


def test_non_positive_hours_are_warned_about() -> None:
    catalogue = parse_catalogue({"topics": [{"id": "a", "title": "A", "hours": 0}]})
    assert catalogue.topics[0].hours == 1.0
    assert "greater than zero" in catalogue.warnings[0]


def test_missing_id_is_fatal() -> None:
    with pytest.raises(CatalogueError, match="'id' is required"):
        parse_catalogue({"topics": [{"title": "no id"}]})


def test_duplicate_id_is_fatal() -> None:
    with pytest.raises(CatalogueError, match="duplicate topic id"):
        parse_catalogue({"topics": [{"id": "a", "title": "A"}, {"id": "a", "title": "B"}]})


def test_unknown_requirement_is_fatal() -> None:
    with pytest.raises(CatalogueError, match="unknown topic"):
        parse_catalogue({"topics": [{"id": "a", "title": "A", "requires": ["zzz"]}]})


def test_self_requirement_is_fatal() -> None:
    with pytest.raises(CatalogueError, match="requires itself"):
        parse_catalogue({"topics": [{"id": "a", "title": "A", "requires": ["a"]}]})


@pytest.mark.parametrize(
    "payload",
    [
        "{not json}",
        "[]",
        {"topics": []},
        {"topics": "nope"},
        {"title": 5, "topics": [{"id": "a", "title": "A"}]},
        {"topics": [{"id": "a", "title": "A", "hours": "long"}]},
        {"topics": [{"id": "a", "title": "A", "hours": True}]},
        {"topics": [{"id": "a", "title": "A", "requires": "b"}]},
        {"topics": [{"id": "a", "title": "A", "tags": [1]}]},
        {"topics": [{"id": "a", "title": 7}]},
        {"topics": ["a"]},
    ],
)
def test_invalid_documents(payload) -> None:
    with pytest.raises(CatalogueError):
        parse_catalogue(payload)


def test_example_catalogue_loads() -> None:
    catalogue = parse_catalogue((EXAMPLES / "backend-path.json").read_text(encoding="utf-8"))
    assert len(catalogue.topics) == 10
    assert catalogue.total_hours == 93.0
    assert catalogue.tags == ["data", "language", "ops", "performance", "quality", "security", "tooling", "web"]


def test_as_dict_shape() -> None:
    payload = parse_catalogue(SIMPLE).topics[1].as_dict()
    assert payload["id"] == "b"
    assert payload["requires"] == ["a"]
    assert payload["hours"] == 2.0
