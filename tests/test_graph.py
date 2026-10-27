from __future__ import annotations

from pathlib import Path

import pytest

from learning_path_planner.catalogue import Catalogue, parse_catalogue
from learning_path_planner.graph import (
    CycleError,
    critical_path,
    dependents,
    depths,
    find_cycle,
    hours_by_tag,
    levels,
    topological_order,
)

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
BACKEND = parse_catalogue((EXAMPLES / "backend-path.json").read_text(encoding="utf-8"))


def catalogue(*topics) -> Catalogue:
    return parse_catalogue({"title": "t", "topics": list(topics)})


def test_depths_follow_prerequisites() -> None:
    path = catalogue(
        {"id": "a", "title": "A"},
        {"id": "b", "title": "B", "requires": ["a"]},
        {"id": "c", "title": "C", "requires": ["b"]},
        {"id": "d", "title": "D"},
    )
    assert depths(path) == {"a": 1, "b": 2, "c": 3, "d": 1}


def test_depth_uses_the_longest_chain() -> None:
    path = catalogue(
        {"id": "a", "title": "A"},
        {"id": "b", "title": "B", "requires": ["a"]},
        {"id": "c", "title": "C", "requires": ["a", "b"]},
    )
    assert depths(path)["c"] == 3


def test_cycle_is_detected_with_members() -> None:
    path = parse_catalogue((EXAMPLES / "cyclic-path.json").read_text(encoding="utf-8"))
    cycle = find_cycle(path)
    assert set(cycle) == {"a", "b", "c"}
    with pytest.raises(CycleError, match="cycle detected"):
        depths(path)


def test_cycle_error_message_shows_the_loop() -> None:
    error = CycleError(["a", "b"])
    assert str(error) == "prerequisite cycle detected: a -> b -> a"


def test_topological_order_puts_prerequisites_first() -> None:
    order = topological_order(BACKEND)
    position = {topic_id: index for index, topic_id in enumerate(order)}
    for topic in BACKEND.topics:
        for requirement in topic.requires:
            assert position[requirement] < position[topic.id]


def test_topological_order_is_deterministic() -> None:
    assert topological_order(BACKEND) == topological_order(BACKEND)
    assert topological_order(BACKEND) == [
        "python",
        "sql",
        "http",
        "git",
        "testing",
        "api",
        "containers",
        "auth",
        "cache",
        "observability",
    ]


def test_topological_order_starts_with_roots() -> None:
    root_ids = {topic.id for topic in BACKEND.topics if not topic.requires}
    roots = [topic_id for topic_id in topological_order(BACKEND) if topic_id in root_ids]
    assert len(roots) == len(root_ids)
    assert topological_order(BACKEND)[: len(root_ids)] == sorted(
        root_ids, key=lambda topic_id: -BACKEND.by_id()[topic_id].hours
    )


def test_levels_group_parallel_work() -> None:
    grouped = levels(BACKEND)
    assert [level.index for level in grouped] == [1, 2, 3, 4, 5]
    assert {topic.id for topic in grouped[0].topics} == {"git", "python", "http", "sql"}
    assert [topic.id for topic in grouped[-1].topics] == ["observability"]
    assert grouped[0].hours == 40.0


def test_level_members_sorted_by_hours() -> None:
    first = levels(BACKEND)[0]
    hours = [topic.hours for topic in first.topics]
    assert hours == sorted(hours, reverse=True)


def test_critical_path_follows_the_longest_chain() -> None:
    path = critical_path(BACKEND)
    assert path.topic_ids == ("python", "testing", "api", "containers", "observability")
    assert path.hours == 59.0


def test_critical_path_of_single_topic() -> None:
    path = critical_path(catalogue({"id": "a", "title": "A", "hours": 3}))
    assert path.as_dict() == {"topics": ["a"], "hours": 3.0}


def test_critical_path_picks_the_heaviest_branch() -> None:
    path = catalogue(
        {"id": "root", "title": "Root", "hours": 1},
        {"id": "light", "title": "Light", "hours": 1, "requires": ["root"]},
        {"id": "heavy", "title": "Heavy", "hours": 9, "requires": ["root"]},
    )
    assert critical_path(path).topic_ids == ("root", "heavy")


def test_hours_by_tag() -> None:
    totals = hours_by_tag(BACKEND)
    assert totals["web"] == 29.0
    assert totals["ops"] == 17.0
    assert totals["language"] == 20.0
    assert next(iter(totals)) == "web"


def test_untagged_topics_are_grouped() -> None:
    assert hours_by_tag(catalogue({"id": "a", "title": "A", "hours": 2})) == {"untagged": 2.0}


def test_dependents_are_sorted() -> None:
    reverse = dependents(BACKEND)
    assert reverse["api"] == ["auth", "cache", "containers"]
    assert reverse["observability"] == []
