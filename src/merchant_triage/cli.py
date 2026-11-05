import argparse
import json
import sys
from pathlib import Path

from .evaluate import evaluate, load_tickets
from .graph import build_graph
from .openrouter import OpenRouterClassifier, TriageError


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Route Shopify merchant tickets with LangGraph and OpenRouter.")
    commands = parser.add_subparsers(dest="command", required=True)
    route = commands.add_parser("route")
    route.add_argument("message")
    check = commands.add_parser("evaluate")
    check.add_argument("dataset", type=Path)
    check.add_argument("--ticket-id", help="Evaluate exactly one ID, e.g. Maria's original case ID.")
    check.add_argument("--output", type=Path, help="Optional report; may contain ticket information.")
    validate = commands.add_parser("validate", help="Check a test set without a key or model call.")
    validate.add_argument("dataset", type=Path)
    validate.add_argument("--ticket-id", help="Require an exact record ID to exist.")
    args = parser.parse_args(argv)
    try:
        # Validate the dataset and selection before attempting an API call.
        if args.command in {"evaluate", "validate"}:
            tickets, digest = load_tickets(args.dataset)
            if args.ticket_id:
                tickets = [t for t in tickets if t.id == args.ticket_id]
                if not tickets:
                    raise ValueError("Requested ticket ID does not exist in the supplied test set.")
            if args.command == "validate":
                print(json.dumps({
                    "status": "valid",
                    "selected_tickets": len(tickets),
                    "dataset_sha256": digest,
                    "expected_routes": {
                        route: sum(t.expected_route == route for t in tickets)
                        for route in ("billing", "orders")
                    },
                    "model_called": False,
                }, indent=2))
                return 0
        graph = build_graph(OpenRouterClassifier.from_env())
        if args.command == "route":
            result = graph.invoke({"message": args.message})
            # Avoid echoing the full merchant message in terminal output.
            print(json.dumps({k: v for k, v in result.items() if k != "message"}, indent=2))
            return 0
        report = evaluate(graph, tickets, digest)
        rendered = json.dumps(report, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 0 if report["passed"] == report["total"] else 1
    except (TriageError, ValueError, OSError) as exc:
        # Dataset validation errors are intentionally sanitized by load_tickets.
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
