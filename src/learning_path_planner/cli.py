"""Command line entry point: plan, order, graph, stats, check."""

from __future__ import annotations

import argparse
import json
import sys

from learning_path_planner.catalogue import CatalogueError, load_catalogue
from learning_path_planner.graph import CycleError
from learning_path_planner.report import PathReport


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="learn-plan",
        description="Order a topic catalogue by prerequisites and print a study plan.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="full study plan with levels and critical path")
    plan.add_argument("file")
    plan.add_argument("--markdown", action="store_true", help="markdown, including a Mermaid graph")
    plan.add_argument("--json", action="store_true")

    order = sub.add_parser("order", help="one numbered line per topic in study order")
    order.add_argument("file")
    order.add_argument("--ids", action="store_true", help="print ids instead of titles")

    graph_cmd = sub.add_parser("graph", help="Mermaid flowchart of the prerequisites")
    graph_cmd.add_argument("file")

    stats = sub.add_parser("stats", help="totals, levels and hours per tag")
    stats.add_argument("file")

    check = sub.add_parser("check", help="validate the catalogue, exit 1 when it cannot be planned")
    check.add_argument("file")
    check.add_argument("--json", action="store_true")

    return parser


def _load(path: str) -> PathReport:
    return PathReport(catalogue=load_catalogue(path), source=path.split("\\")[-1].split("/")[-1])


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        report = _load(args.file)
    except CatalogueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.command == "check":
        if args.json:
            print(json.dumps(report.as_dict(), indent=2))
        elif report.cycle:
            print(f"error: {CycleError(report.cycle)}")
        else:
            print(f"catalogue is plannable: {len(report.catalogue.topics)} topics, no cycles")
        if report.warnings and not args.json:
            for warning in report.warnings:
                print(f"  warning: {warning}")
        return 0 if report.ok else 1

    if not report.ok:
        print(f"error: {CycleError(report.cycle)}", file=sys.stderr)
        return 1

    if args.command == "order":
        topics = report.catalogue.by_id()
        level = {level.index: level for level in report.levels}
        depth = {}
        for index, group in level.items():
            for topic in group.topics:
                depth[topic.id] = index
        for position, topic_id in enumerate(report.order, start=1):
            label = topic_id if args.ids else topics[topic_id].title
            print(f"{position:>2}. [L{depth[topic_id]}] {label} ({topics[topic_id].hours:g}h)")
        return 0

    if args.command == "graph":
        print(report.render_mermaid())
        return 0

    if args.command == "stats":
        print(f"title        : {report.catalogue.title}")
        print(f"topics       : {len(report.catalogue.topics)}")
        print(f"total hours  : {report.catalogue.total_hours:g}")
        print(f"levels       : {len(report.levels)}")
        print(f"critical path: {report.critical.hours:g}h")
        print("hours by tag :")
        for tag, hours in report.tag_hours.items():
            print(f"  {tag:<16}{hours:>7g}h")
        return 0

    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
    elif args.markdown:
        print(report.render_markdown())
    else:
        print(report.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
