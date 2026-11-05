"""Scripted model replies + real supplied mock functions; no network/API key.

This checks wiring, capability boundaries and store effects, not LLM quality.
The plans are intentionally explicit fixture integration scenarios.
"""

import json
from pathlib import Path

from merchant_triage.models import RouteDecision
from merchant_triage.openrouter import Classification
from merchant_triage.specialists import build_supervisor_graph
from merchant_triage.supervisor_run import load_cases, render_summary, run_supervisor

ROOT = Path(__file__).resolve().parents[1]


class ScriptedTriage:
    def __init__(self):
        self.decisions = iter(["orders", "billing"])

    def classify(self, message):
        return Classification(RouteDecision(route=next(self.decisions),
            reason="Scripted offline decision for branch/store-effect testing; not model inference."),
            "scripted-offline", "scripted-offline")


class ScriptedTools:
    def __init__(self):
        self.plans = {}
        self.sequence = 0

    def reply(self, messages, tools):
        context = json.loads(messages[1]["content"])
        domain = context["trusted_context"]["shop_domain"]
        if domain not in self.plans:
            args = {"shop_domain": domain}
            if domain == "azulejo-ceramica-lisboa.myshopify.com":
                plan = [("get_shop", args), ("get_delivery_profile", args),
                    ("get_order", {**args, "order_id": "#1158"}),
                    ("list_orders", {**args, "created_on_min": "2024-11-29", "created_on_max": "2024-12-02", "shipping_rate_title": "EU Standard"}),
                    ("update_shipping_rate", {**args, "rate_id": "rate_eu_standard", "price": 14.90})]
            elif domain == "northwind-coffee-roasters.myshopify.com":
                plan = [("get_shop", args), ("get_app_subscriptions", args),
                    ("list_billing_charges", {**args, "billing_period": "2024-11"}),
                    ("issue_billing_credit", {**args, "charge_id": "chg_nw_5503", "amount": 19.99,
                        "description": "Credit one duplicate November ReviewStream Growth charge"})]
            else:
                plan = [("get_shop", args)]
            self.plans[domain] = iter(plan + [None])
        action = next(self.plans[domain])
        if action is None:
            return {"role": "assistant", "content": "Scripted mock actions completed; see checked call results and independent end-state assertions."}, "scripted-offline"
        name, arguments = action
        assert name in {tool["function"]["name"] for tool in tools}
        self.sequence += 1
        return {"role": "assistant", "content": None, "tool_calls": [{
            "id": f"scripted-{self.sequence}", "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments)}}]}, "scripted-offline"


def run():
    reports = ROOT / "reports/runs"
    reports.mkdir(parents=True, exist_ok=True)
    for source, selected_ids, name in [
        ("data/supervisor_demo_tickets.json", None, "stage2-offline-fixture"),
        ("data/source/shopify_merchant_tickets.csv", {"SUP-48213", "SUP-48197"}, "stage2-offline-original"),
    ]:
        cases, digest = load_cases(ROOT / source)
        if selected_ids:
            cases = sorted((case for case in cases if case.id in selected_ids), key=lambda case: case.id, reverse=True)
        graph = build_supervisor_graph(ScriptedTriage(), ScriptedTools())
        report = run_supervisor(graph, cases, digest)
        report["model_mode"] = "scripted_offline_no_network"
        report["claims"] = "Integration/store effects only; routing and tool selection are scripted, not live model evidence."
        # Publish check outcomes and hashes, not another copy of customer/address
        # data from raw tool returns. Full values were checked locally in memory.
        for row in report["results"]:
            for call in row.get("specialist", {}).get("tool_calls", []):
                if "result" in call:
                    del call["result"]
                    call["result_publication"] = "omitted; checked locally against pre/post-call fixtures"
        (reports / f"{name}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        summary = render_summary(report)
        (reports / f"{name}.txt").write_text(summary + "\n", encoding="utf-8")
        print(f"\n=== {name}: SCRIPTED OFFLINE, NO MODEL CALL ===\n{summary}")
        if selected_ids:
            assert report["fixture_missing"] == 2 and report["passed"] == 0
            assert all(row["route_passed"] and not row["changed_paths"] and row["specialist"]["status"] == "needs_human" for row in report["results"])
        else:
            assert report["passed"] == report["total"] == 2


if __name__ == "__main__":
    run()
