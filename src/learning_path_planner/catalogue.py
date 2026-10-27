"""Read and validate a learning path catalogue."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

DEFAULT_HOURS = 1.0


class CatalogueError(ValueError):
    """Raised when a catalogue cannot be read or is structurally invalid."""


@dataclass(frozen=True)
class Topic:
    id: str
    title: str
    hours: float = DEFAULT_HOURS
    requires: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "hours": self.hours,
            "requires": list(self.requires),
            "tags": list(self.tags),
            "note": self.note,
        }


@dataclass
class Catalogue:
    title: str
    topics: list[Topic] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ids(self) -> list[str]:
        return [topic.id for topic in self.topics]

    def by_id(self) -> dict[str, Topic]:
        return {topic.id: topic for topic in self.topics}

    @property
    def total_hours(self) -> float:
        return sum(topic.hours for topic in self.topics)

    @property
    def tags(self) -> list[str]:
        found: set[str] = set()
        for topic in self.topics:
            found.update(topic.tags)
        return sorted(found)


def _text(value: Any, field_name: str, topic_id: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise CatalogueError(f"topic '{topic_id}': {field_name} must be a string")
    return value.strip()


def _string_list(value: Any, field_name: str, topic_id: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise CatalogueError(f"topic '{topic_id}': {field_name} must be a list of strings")
    items: list[str] = []
    for entry in value:
        if not isinstance(entry, str) or not entry.strip():
            raise CatalogueError(f"topic '{topic_id}': every entry in {field_name} must be a non-empty string")
        items.append(entry.strip())
    return tuple(items)


def _hours(value: Any, topic_id: str, warnings: list[str]) -> float:
    if value is None:
        return DEFAULT_HOURS
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise CatalogueError(f"topic '{topic_id}': hours must be a number")
    if value <= 0:
        warnings.append(f"topic '{topic_id}': hours must be greater than zero, using {DEFAULT_HOURS:g}")
        return DEFAULT_HOURS
    return float(value)


def parse_catalogue(payload: str | dict) -> Catalogue:
    """Parse a catalogue and enforce the structural rules.

    Duplicate ids and unknown prerequisites are fatal because they make the
    ordering ambiguous. Cosmetic problems are collected as warnings instead.
    """
    document: Any = payload
    if isinstance(payload, str):
        try:
            document = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise CatalogueError(f"catalogue is not valid JSON: {exc.msg} at line {exc.lineno}") from exc

    if not isinstance(document, dict):
        raise CatalogueError("catalogue must be a JSON object with a 'topics' list")

    raw_topics = document.get("topics")
    if not isinstance(raw_topics, list) or not raw_topics:
        raise CatalogueError("catalogue needs a non-empty 'topics' list")

    warnings: list[str] = []
    topics: list[Topic] = []
    seen: set[str] = set()

    for position, raw in enumerate(raw_topics, start=1):
        if not isinstance(raw, dict):
            raise CatalogueError(f"topic #{position} must be an object")
        topic_id = _text(raw.get("id"), "id", f"#{position}")
        if not topic_id:
            raise CatalogueError(f"topic #{position}: 'id' is required")
        if topic_id in seen:
            raise CatalogueError(f"duplicate topic id '{topic_id}'")
        seen.add(topic_id)

        title = _text(raw.get("title"), "title", topic_id)
        if not title:
            warnings.append(f"topic '{topic_id}': no title, using the id instead")
            title = topic_id

        topics.append(
            Topic(
                id=topic_id,
                title=title,
                hours=_hours(raw.get("hours"), topic_id, warnings),
                requires=_string_list(raw.get("requires"), "requires", topic_id),
                tags=_string_list(raw.get("tags"), "tags", topic_id),
                note=_text(raw.get("note"), "note", topic_id),
            )
        )

    known = {topic.id for topic in topics}
    for topic in topics:
        if topic.id in topic.requires:
            raise CatalogueError(f"topic '{topic.id}' requires itself")
        unknown = [requirement for requirement in topic.requires if requirement not in known]
        if unknown:
            raise CatalogueError(f"topic '{topic.id}' requires unknown topic(s): {', '.join(sorted(unknown))}")

    raw_title = document.get("title")
    if raw_title is not None and not isinstance(raw_title, str):
        raise CatalogueError("'title' must be a string")
    name = (raw_title or "Learning path").strip() or "Learning path"

    return Catalogue(title=name, topics=topics, warnings=warnings)


def load_catalogue(path: str) -> Catalogue:
    from pathlib import Path

    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise CatalogueError(f"cannot read {path}: {exc.strerror or exc}") from exc
    return parse_catalogue(text)
