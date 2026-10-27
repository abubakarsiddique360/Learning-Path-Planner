"""Render a catalogue as a text summary, a markdown study plan or a Mermaid graph."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from learning_path_planner import graph
from learning_path_planner.catalogue import Catalogue

UNSAFE_NODE_RE = re.compile(r"[^A-Za-z0-9_]")


def node_ids(catalogue: Catalogue) -> dict[str, str]:
    """Mermaid-safe aliases that stay readable and never collide."""
    aliases: dict[str, str] = {}
    used: set[str] = set()
    for position, topic in enumerate(catalogue.topics, start=1):
        alias = UNSAFE_NODE_RE.sub("_", topic.id)
        if not alias or alias[0].isdigit():
            alias = f"t_{position}_{alias}"
        base = alias
        counter = 2
        while alias in used:
            alias = f"{base}_{counter}"
            counter += 1
        used.add(alias)
        aliases[topic.id] = alias
    return aliases


def _hours(value: float) -> str:
    return f"{value:g}h"


@dataclass
class PathReport:
    catalogue: Catalogue
    source: str = "catalogue"
    cycle: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cycle = graph.find_cycle(self.catalogue)

    @property
    def ok(self) -> bool:
        return not self.cycle

    def _require_acyclic(self) -> None:
        if self.cycle:
            raise graph.CycleError(self.cycle)

    @property
    def order(self) -> list[str]:
        self._require_acyclic()
        return graph.topological_order(self.catalogue)

    @property
    def levels(self) -> list[graph.Level]:
        self._require_acyclic()
        return graph.levels(self.catalogue)

    @property
    def critical(self) -> graph.Path:
        self._require_acyclic()
        return graph.critical_path(self.catalogue)

    @property
    def tag_hours(self) -> dict[str, float]:
        return graph.hours_by_tag(self.catalogue)

    @property
    def warnings(self) -> list[str]:
        return list(self.catalogue.warnings)

    def as_dict(self) -> dict:
        payload = {
            "source": self.source,
            "title": self.catalogue.title,
            "topics": len(self.catalogue.topics),
            "total_hours": self.catalogue.total_hours,
            "warnings": self.warnings,
            "cycle": self.cycle,
            "ok": self.ok,
        }
        if not self.ok:
            return payload
        payload.update(
            {
                "order": self.order,
                "levels": [
                    {
                        "index": level.index,
                        "hours": level.hours,
                        "topics": [topic.id for topic in level.topics],
                    }
                    for level in self.levels
                ],
                "critical_path": self.critical.as_dict(),
                "hours_by_tag": self.tag_hours,
                "catalogue": [topic.as_dict() for topic in self.catalogue.topics],
            }
        )
        return payload

    def render(self) -> str:
        lines = [
            f"{self.catalogue.title}  -  {len(self.catalogue.topics)} topic(s), "
            f"{self.catalogue.total_hours:g}h in total",
        ]
        if not self.ok:
            lines.append("")
            lines.append(f"ERROR: {graph.CycleError(self.cycle)}")
            return "\n".join(lines)

        paths = self.levels
        critical = self.critical
        lines.append(f"{len(paths)} level(s)   critical path {_hours(critical.hours)}: {self._chain(critical)}")
        depth = graph.depths(self.catalogue)

        for level in paths:
            names = ", ".join(topic.id for topic in level.topics)
            lines.append("")
            lines.append(f"Level {level.index}  ({_hours(level.hours)} in parallel)  [{names}]")
            for topic in level.topics:
                requires = f"  after {', '.join(topic.requires)}" if topic.requires else ""
                padding = "  " * min(depth[topic.id] - 1, 2)
                lines.append(f"  {padding}{topic.title:<34}{_hours(topic.hours):>7}{requires}")

        if self.warnings:
            lines.append("")
            lines.append(f"{len(self.warnings)} warning(s)")
            lines.extend(f"  {warning}" for warning in self.warnings)
        return "\n".join(lines)

    def _chain(self, path: graph.Path) -> str:
        topics = self.catalogue.by_id()
        return " -> ".join(topics[topic_id].title for topic_id in path.topic_ids)

    def render_markdown(self) -> str:
        if not self.ok:
            return f"# {self.catalogue.title}\n\n**Cannot plan:** {graph.CycleError(self.cycle)}\n"

        lines = [f"# {self.catalogue.title}", ""]
        critical = self.critical
        lines.append(
            f"**{len(self.catalogue.topics)} topics - {self.catalogue.total_hours:g} hours - "
            f"{len(self.levels)} levels - critical path {_hours(critical.hours)}**"
        )
        lines += ["", "## Levels", "", "| Level | Topics | Hours |", "| --- | --- | --- |"]
        for level in self.levels:
            names = ", ".join(topic.title for topic in level.topics)
            lines.append(f"| {level.index} | {names} | {_hours(level.hours)} |")

        for level in self.levels:
            lines += ["", f"## Level {level.index}", ""]
            for topic in level.topics:
                suffix = f" _after {', '.join(topic.requires)}_" if topic.requires else ""
                tags = f" `{'`, `'.join(topic.tags)}`" if topic.tags else ""
                lines.append(f"- [ ] **{topic.title}** - {_hours(topic.hours)}{tags}{suffix}")

        lines += ["", "## Critical path", ""]
        lines.append(f"{self._chain(critical)} - **{_hours(critical.hours)}**")
        lines += ["", "```mermaid", "flowchart LR", self._mermaid_body(), "```"]

        lines += ["", "## Hours by tag", "", "| Tag | Hours |", "| --- | --- |"]
        lines += [f"| {tag} | {_hours(hours)} |" for tag, hours in self.tag_hours.items()]
        if self.warnings:
            lines += ["", "## Warnings", ""]
            lines += [f"- {warning}" for warning in self.warnings]
        return "\n".join(lines)

    def _mermaid_body(self) -> str:
        aliases = node_ids(self.catalogue)
        depth = graph.depths(self.catalogue)
        lines: list[str] = []
        for topic in self.catalogue.topics:
            alias = aliases[topic.id]
            lines.append(f'  {alias}["{topic.title}<br/>{_hours(topic.hours)}<br/>level {depth[topic.id]}"]')
        for topic in self.catalogue.topics:
            for requirement in topic.requires:
                lines.append(f"  {aliases[requirement]} --> {aliases[topic.id]}")
        return "\n".join(lines)

    def render_mermaid(self) -> str:
        self._require_acyclic()
        return "\n".join(["flowchart LR", self._mermaid_body()])
