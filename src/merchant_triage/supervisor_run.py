"""Run isolated supervisor cases and report actual tool/store evidence."""

import copy
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from . import mock_admin
from .admin_tools import changed_paths, digest
from .models import SupportCase
from .openrouter import TriageError


def load_cases(path):
    raw = path.read_bytes()
    try:
        if path.suffix.lower() == ".csv":
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = [{"id": r["ticket_id"], "merchant_name": r["merchant_name"],
                         "shop_domain": r["shop_domain"], "message": r["subject"] + "\n\n" + r["message_body"],
                         "expected_route": r["expected_route"]} for r in csv.DictReader(stream)]
        else:
            rows = json.loads(raw)
        if not isinstance(rows, list) or not rows:
            raise ValueError("No cases")
        cases = [SupportCase.model_validate(row) for row in rows]
        if len({case.id for case in cases}) != len(cases):
            raise ValueError("Duplicate IDs")
    except (ValueError, KeyError, TypeError):
        raise ValueError("Invalid supervisor cases: expected unique id, merchant_name, shop_domain, message, expected_route") from None
    return cases, hashlib.sha256(raw).hexdigest()


def verify_demo(case_id, before, after, calls):
    """Independent end-state checks only for explicitly authored fixture demos."""
    if case_id == "fixture-maria-shipping":
        domain = "azulejo-ceramica-lisboa.myshopify.com"
        old, new = before[domain], after[domain]
        rates = {r["id"]: r["price"] for z in new["delivery_profile"]["zones"] for r in z["rates"]}
        writes = [c for c in calls if c.get("effect") == "write"]
        checks = {
            "eu_standard_corrected_from_zero_to_14_90": rates["rate_eu_standard"] == 14.90,
            "domestic_rate_preserved_at_4_90": rates["rate_pt_ctt"] == 4.90,
            "all_existing_orders_unchanged": old["orders"] == new["orders"],
            "billing_unchanged": old["billing_charges"] == new["billing_charges"],
            "exactly_one_targeted_shipping_write": len(writes) == 1 and writes[0]["tool"] == "update_shipping_rate" and writes[0]["arguments"]["rate_id"] == "rate_eu_standard",
            "all_40_affected_orders_discovered": any(c["tool"] == "list_orders" and c.get("status") == "completed" and {r["order_id"] for r in c["result"] if r["shipping_title"] == "EU Standard" and r["shipping_price"] == 0} == {f"#{i}" for i in range(1160, 1200)} for c in calls),
            "historical_rate_evidence_read": any(c["tool"] == "get_order" and c["arguments"]["order_id"] == "#1158" and c.get("status") == "completed" for c in calls),
        }
    elif case_id == "fixture-billing-duplicate":
        domain = "northwind-coffee-roasters.myshopify.com"
        old, new = before[domain], after[domain]
        credits = [c for c in new["billing_charges"] if c["type"] == "credit"]
        writes = [c for c in calls if c.get("effect") == "write"]
        checks = {
            "one_duplicate_charge_credited_19_99": len(credits) == 1 and credits[0]["amount"] == -19.99 and credits[0]["credits_charge_id"] in {"chg_nw_5502", "chg_nw_5503"},
            "original_charge_lines_preserved": new["billing_charges"][:3] == old["billing_charges"],
            "active_subscription_not_cancelled": old["app_subscriptions"] == new["app_subscriptions"],
            "orders_unchanged": old["orders"] == new["orders"],
            "exactly_one_billing_credit_write": len(writes) == 1 and writes[0]["tool"] == "issue_billing_credit",
        }
    else:
        return None
    checks["other_shops_unchanged"] = all(before[d] == after[d] for d in before if d != domain)
    return {"checks": checks, "passed": all(checks.values())}


def run_supervisor(graph, cases, dataset_sha256):
    rows = []
    for case in cases:
        mock_admin.reset_store()
        before = copy.deepcopy(mock_admin.FIXTURES)
        row = {"id": case.id, "merchant_name": case.merchant_name, "shop_domain": case.shop_domain,
               "expected_route": case.expected_route, "fixture_available": case.shop_domain in before}
        try:
            # Labels and source expected fixes/tool calls never enter graph state.
            result = graph.invoke({"message": case.message, "shop_domain": case.shop_domain,
                                   "merchant_name": case.merchant_name})
            specialist = result["specialist_result"]
            calls = specialist["tool_calls"]
            state_check = verify_demo(case.id, before, mock_admin.FIXTURES, calls)
            row.update(decision=result["decision"].model_dump(), actual_route=result["route"],
                       requested_model=result["requested_model"], resolved_model=result["resolved_model"],
                       specialist=specialist, fixture_checks=state_check,
                       changed_paths=changed_paths(before, mock_admin.FIXTURES),
                       before_sha256=digest(before), after_sha256=digest(mock_admin.FIXTURES),
                       call_log=copy.deepcopy(mock_admin.CALL_LOG))
            row["route_passed"] = result["route"] == case.expected_route
            row["passed"] = (row["route_passed"] and specialist["status"] == "completed"
                and bool(calls) and all(c.get("checked_against_store") and c.get("call_log_matches") for c in calls)
                and (state_check is None or state_check["passed"]))
        except TriageError as exc:
            row.update(passed=False, error=str(exc))
        rows.append(row)
    mock_admin.reset_store()
    return {"evaluated_at": datetime.now(timezone.utc).isoformat(), "dataset_sha256": dataset_sha256,
            "mode": "mock_admin_only", "total": len(rows), "passed": sum(r["passed"] for r in rows),
            "fixture_missing": sum(not r["fixture_available"] for r in rows), "results": rows}


def render_summary(report):
    lines = []
    for row in report["results"]:
        lines.append(f"{row['merchant_name']} ({row['id']}) | {row['shop_domain']}")
        if "decision" not in row:
            lines.append(f"ERROR: {row['error']}")
            continue
        lines.append(f"Route: {row['actual_route']} | expected: {row['expected_route']}")
        lines.append(f"Reason: {row['decision']['reason']}")
        if "confidence" in row["decision"]:
            lines.append(f"Confidence: {row['decision']['confidence']} (uncalibrated)")
        specialist = row["specialist"]
        lines.append(f"Agent: {specialist['agent']} | status: {specialist['status']}")
        for call in specialist["tool_calls"]:
            checked = call.get("checked_against_store", False)
            lines.append(f"  {call['effect'].upper()} {call['tool']} {json.dumps(call['arguments'], ensure_ascii=False)} | status={call['status']} | store_check={checked}")
            if "error" in call:
                lines.append(f"    Error: {call['error']}")
        lines.append(f"Response: {specialist['response']}")
        if row["fixture_checks"]:
            for name, passed in row["fixture_checks"]["checks"].items():
                lines.append(f"  CHECK {name}: {'PASS' if passed else 'FAIL'}")
        lines.append(f"Case: {'PASS' if row['passed'] else 'NOT PASSED'}")
    lines.append(f"Summary: {report['passed']}/{report['total']} passed; missing fixtures: {report['fixture_missing']}")
    return "\n".join(lines)
