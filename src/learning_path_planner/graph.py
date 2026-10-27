"""Ordering, dependency depth and critical path over a topic catalogue."""

from __future__ import annotations

from dataclasses import dataclass

from learning_path_planner.catalogue import Catalogue, Topic


class CycleError(ValueError):
    """Raised when the prerequisite graph contains a cycle."""

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        joined = " -> ".join([*cycle, cycle[0]]) if cycle else "unknown"
        super().__init__(f"prerequisite cycle detected: {joined}")


def _requirements(catalogue: Catalogue, topic: Topic) -> tuple[str, ...]:
    known = catalogue.by_id()
    return tuple(requirement for requirement in topic.requires if requirement in known)


def depths(catalogue: Catalogue) -> dict[str, int]:
    """Longest distance from a root, so every prerequisite sits on a lower level."""
    resolved: dict[str, int] = {}
    stack: list[str] = []
    topics = catalogue.by_id()

    def visit(topic_id: str) -> int:
        if topic_id in resolved:
            return resolved[topic_id]
        if topic_id in stack:
            start = stack.index(topic_id)
            raise CycleError(stack[start:])
        stack.append(topic_id)
        requirement_depths = [visit(requirement) for requirement in _requirements(catalogue, topics[topic_id])]
        stack.pop()
        depth = 1 + max(requirement_depths, default=0)
        resolved[topic_id] = depth
        return depth

    for topic_id in catalogue.ids:
        visit(topic_id)
    return resolved


def find_cycle(catalogue: Catalogue) -> list[str]:
    """Ids that take part in a cycle, or an empty list when the graph is acyclic."""
    try:
        depths(catalogue)
    except CycleError as exc:
        return exc.cycle
    return []


def topological_order(catalogue: Catalogue) -> list[str]:
    """Deterministic order: level first, then longer topics, then id."""
    level = depths(catalogue)
    ordered = sorted(catalogue.topics, key=lambda topic: (level[topic.id], -topic.hours, topic.id))
    return [topic.id for topic in ordered]


@dataclass(frozen=True)
class Level:
    index: int
    topics: tuple[Topic, ...]

    @property
    def hours(self) -> float:
        return sum(topic.hours for topic in self.topics)


def levels(catalogue: Catalogue) -> list[Level]:
    """Group topics into study waves; everything inside a wave can be learned in parallel."""
    depth = depths(catalogue)
    buckets: dict[int, list[Topic]] = {}
    for topic in catalogue.topics:
        buckets.setdefault(depth[topic.id], []).append(topic)

    grouped: list[Level] = []
    for index in sorted(buckets):
        members = sorted(buckets[index], key=lambda topic: (-topic.hours, topic.id))
        grouped.append(Level(index=index, topics=tuple(members)))
    return grouped


@dataclass(frozen=True)
class Path:
    topic_ids: tuple[str, ...]
    hours: float

    def as_dict(self) -> dict:
        return {"topics": list(self.topic_ids), "hours": self.hours}


def critical_path(catalogue: Catalogue) -> Path:
    """Longest chain of dependent topics, i.e. the shortest time the whole plan can take."""
    order = topological_order(catalogue)
    topics = catalogue.by_id()
    best: dict[str, float] = {}
    previous: dict[str, str | None] = {}

    for topic_id in order:
        topic = topics[topic_id]
        candidates = [(best[requirement], requirement) for requirement in _requirements(catalogue, topic)]
        if candidates:
            weight, predecessor = max(candidates, key=lambda pair: (pair[0], pair[1]))
            best[topic_id] = weight + topic.hours
            previous[topic_id] = predecessor
        else:
            best[topic_id] = topic.hours
            previous[topic_id] = None

    endpoint = max(order, key=lambda topic_id: (best[topic_id], topic_id))
    chain: list[str] = []
    cursor: str | None = endpoint
    while cursor is not None:
        chain.append(cursor)
        cursor = previous[cursor]
    chain.reverse()
    return Path(topic_ids=tuple(chain), hours=best[endpoint])


def hours_by_tag(catalogue: Catalogue) -> dict[str, float]:
    totals: dict[str, float] = {}
    for topic in catalogue.topics:
        for tag in topic.tags or ("untagged",):
            totals[tag] = totals.get(tag, 0.0) + topic.hours
    return dict(sorted(totals.items(), key=lambda pair: (-pair[1], pair[0])))


def dependents(catalogue: Catalogue) -> dict[str, list[str]]:
    """Reverse edges: which topics become available once a topic is finished."""
    reverse: dict[str, list[str]] = {topic.id: [] for topic in catalogue.topics}
    for topic in catalogue.topics:
        for requirement in _requirements(catalogue, topic):
            reverse[requirement].append(topic.id)
    for key in reverse:
        reverse[key].sort()
    return reverse
