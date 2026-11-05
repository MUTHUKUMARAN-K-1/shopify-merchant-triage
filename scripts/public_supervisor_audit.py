"""Publish call/check evidence without customer-level tool results or prose."""

import json
import sys
from pathlib import Path


def public_audit(report):
    # JSON round-trip keeps the original model values/choices while copying.
    report = json.loads(json.dumps(report))
    for row in report["results"]:
        specialist = row.get("specialist", {})
        specialist.pop("response", None)
        for call in specialist.get("tool_calls", []):
            call.pop("result", None)
    report["publication"] = "Customer-level tool results and free-text final responses omitted; decisions, arguments, status, hashes and checks retained."
    return report


def summary(report):
    lines = ["PUBLIC CALL/CHECK EXCERPT — customer-level results and narrative omitted"]
    for row in report["results"]:
        lines.append(f"{row['merchant_name']} ({row['id']}) | {row['shop_domain']}")
        if "decision" not in row:
            lines.append(f"ERROR: {row['error']}")
            continue
        decision = row["decision"]
        lines.append(f"Route: {decision['route']} | expected: {row['expected_route']}")
        lines.append(f"Reason: {decision['reason']}")
        lines.append(f"Confidence: {decision['confidence']} (uncalibrated)")
        specialist = row["specialist"]
        lines.append(f"Agent: {specialist['agent']} | status: {specialist['status']}")
        for call in specialist["tool_calls"]:
            lines.append(f"  {call['effect'].upper()} {call['tool']} {json.dumps(call['arguments'], ensure_ascii=False)} | status={call['status']} | store_check={call.get('checked_against_store', False)}")
            if "error" in call:
                lines.append(f"    Error: {call['error']}")
        for name, passed in (row.get("fixture_checks") or {}).get("checks", {}).items():
            lines.append(f"  CHECK {name}: {'PASS' if passed else 'FAIL'}")
        lines.append(f"Case: {'PASS' if row['passed'] else 'NOT PASSED'}")
    lines.append(f"Summary: {report['passed']}/{report['total']} passed; missing fixtures: {report['fixture_missing']}")
    return "\n".join(lines)


if __name__ == "__main__":
    report = public_audit(json.loads(Path(sys.argv[1]).read_text()))
    Path(sys.argv[2]).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(summary(report))
