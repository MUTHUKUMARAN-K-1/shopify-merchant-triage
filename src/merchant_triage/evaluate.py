import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from .models import Ticket
from .openrouter import TriageError


def load_tickets(path: Path) -> tuple[list[Ticket], str]:
    raw = path.read_bytes()
    try:
        records = json.loads(raw)
        if not isinstance(records, list) or not records:
            raise ValueError("Expected a nonempty JSON array")
        tickets = [Ticket.model_validate(record) for record in records]
        if len({t.id for t in tickets}) != len(tickets):
            raise ValueError("Duplicate ticket IDs")
    except (ValueError, TypeError, ValidationError):
        raise ValueError("Test set must be a nonempty JSON array with unique id, message and expected_route fields.") from None
    return tickets, hashlib.sha256(raw).hexdigest()


def evaluate(graph, tickets: list[Ticket], dataset_sha256: str) -> dict:
    if not tickets:
        raise ValueError("Cannot evaluate an empty test set.")
    rows = []
    for ticket in tickets:
        # Deliberately send only the message, never the expected route or ID.
        try:
            result = graph.invoke({"message": ticket.message})
            rows.append({
                "id": ticket.id,
                "expected_route": ticket.expected_route,
                "actual_route": result["route"],
                "reason": result["reason"],
                "requested_model": result["requested_model"],
                "resolved_model": result["resolved_model"],
                "passed": result["route"] == ticket.expected_route,
                "status": "completed",
            })
        except TriageError as exc:
            rows.append({"id": ticket.id, "expected_route": ticket.expected_route,
                         "passed": False, "status": "error", "error": str(exc)})
    passed = sum(row["passed"] for row in rows)
    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_sha256": dataset_sha256,
        "total": len(rows), "passed": passed,
        "errors": sum(row["status"] == "error" for row in rows),
        "route_accuracy": passed / len(rows),
        "results": rows,
    }
