"""Explicit specialist bindings and checked execution of the supplied mock API."""

import copy
import hashlib
import inspect
import json
from dataclasses import dataclass
from typing import Callable, Literal, get_type_hints

from pydantic import ConfigDict, ValidationError, create_model

from . import mock_admin
from .models import Route


TOOL_OWNERS = {
    "get_shop": ("shared", "read"),
    "get_app_subscriptions": ("billing", "read"),
    "list_billing_charges": ("billing", "read"),
    "cancel_app_subscription": ("billing", "write"),
    "issue_billing_credit": ("billing", "write"),
    "get_order": ("orders", "read"),
    "list_orders": ("orders", "read"),
    "list_order_transactions": ("orders", "read"),
    "calculate_refund": ("orders", "read"),
    "get_delivery_profile": ("orders", "read"),
    "create_refund": ("orders", "write"),
    "update_shipping_rate": ("orders", "write"),
    "recalculate_order_shipping": ("orders", "write"),
    "update_order_shipping_address": ("orders", "write"),
    "cancel_order": ("orders", "write"),
    "add_order_note": ("orders", "write"),
}


class ToolBoundaryError(ValueError):
    pass


class WriteLimitError(ToolBoundaryError):
    """A proposed write exceeded the current fixture's permitted balance."""


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def changed_paths(before, after, path=""):
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        return [p for key in sorted(before.keys() | after.keys())
                for p in changed_paths(before.get(key), after.get(key), f"{path}/{key}")]
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        return [p for i, (left, right) in enumerate(zip(before, after))
                for p in changed_paths(left, right, f"{path}/{i}")]
    return [path or "/"]


@dataclass(frozen=True)
class BoundAdminTool:
    name: str
    owner: str
    effect: Literal["read", "write"]
    function: Callable
    arguments_model: type

    def schema(self):
        parameters = self.arguments_model.model_json_schema()
        if "order_id" in parameters.get("properties", {}):
            parameters["properties"]["order_id"]["description"] = (
                "Exact mock order ID including its leading #, for example '#1187'. "
                "Preserve the ID returned by reads or written in the merchant message."
            )
        for field in ("created_on_min", "created_on_max"):
            if field in parameters.get("properties", {}):
                parameters["properties"][field]["description"] = (
                    "Inclusive calendar date in YYYY-MM-DD format, for example '2024-11-29'. "
                    "Date only: do not send a time, timezone or ISO datetime."
                )
        return {"type": "function", "function": {
            "name": self.name,
            "description": f"[{self.effect.upper()}] {inspect.getdoc(self.function)}",
            "parameters": parameters,
        }}


def bind_tools(role: Route) -> tuple[BoundAdminTool, ...]:
    if role not in {"billing", "orders"}:
        raise ToolBoundaryError("Unknown specialist role")
    tools = []
    for name, (owner, effect) in TOOL_OWNERS.items():
        if owner not in {role, "shared"}:
            continue
        function = getattr(mock_admin, name)
        hints = get_type_hints(function)
        fields = {key: (hints[key], ... if parameter.default is inspect.Parameter.empty else parameter.default)
                  for key, parameter in inspect.signature(function).parameters.items()}
        model = create_model(f"{name}_arguments", __config__=ConfigDict(extra="forbid", strict=True, allow_inf_nan=False), **fields)
        tools.append(BoundAdminTool(name, owner, effect, function, model))
    return tuple(tools)


def check_result(name, args, result, before, after):
    """Check each actual return value against pre/post-call fixture data."""
    if TOOL_OWNERS[name][1] == "read" and before != after:
        return False
    if name == "get_shop":
        return result == before["shop"]
    if name == "get_delivery_profile":
        return result == before["delivery_profile"]
    if name == "get_app_subscriptions":
        return result == before["app_subscriptions"]
    if name == "list_billing_charges":
        return result == [c for c in before["billing_charges"]
                          if not args["billing_period"] or c["billing_period"] == args["billing_period"]]
    if name == "list_orders":
        expected = []
        for order in before["orders"].values():
            day = order["created_at"][:10]
            shipping = order["shipping_lines"][0]
            if args["created_on_min"] and day < args["created_on_min"]:
                continue
            if args["created_on_max"] and day > args["created_on_max"]:
                continue
            if args["shipping_rate_title"] and shipping["title"] != args["shipping_rate_title"]:
                continue
            expected.append({"order_id": order["order_id"], "created_at": order["created_at"],
                "customer_name": order["customer"]["name"], "destination_country": order["shipping_address"]["country_code"],
                "shipping_title": shipping["title"], "shipping_price": shipping["price"],
                "total_price": order["total_price"], "currency": order["currency"],
                "financial_status": order["financial_status"], "fulfillment_status": order["fulfillment_status"]})
        return result == sorted(expected, key=lambda item: item["created_at"])
    if name == "get_order":
        return result == before["orders"][args["order_id"]]
    if name == "list_order_transactions":
        return result == before["orders"][args["order_id"]]["transactions"]
    if name == "calculate_refund":
        order = before["orders"][args["order_id"]]
        available = round(sum(t["amount"] for t in order["transactions"] if t["kind"] == "sale" and t["status"] == "success")
                          - sum(r["amount"] for r in order["refunds"]), 2)
        remaining = round(available - args["amount"], 2)
        return result == {"order_id": args["order_id"], "currency": order["currency"],
            "amount": round(args["amount"], 2), "refundable_before": available,
            "refundable_after": remaining, "parent_transaction_id": order["transactions"][0]["id"],
            "resulting_financial_status": "refunded" if remaining == 0 else "partially_refunded"}
    if name == "update_shipping_rate":
        previous = next(r for z in before["delivery_profile"]["zones"] for r in z["rates"] if r["id"] == args["rate_id"])
        zone, rate = next((z, r) for z in after["delivery_profile"]["zones"] for r in z["rates"] if r["id"] == args["rate_id"])
        expected = copy.deepcopy(before)
        target = next(r for z in expected["delivery_profile"]["zones"] for r in z["rates"] if r["id"] == args["rate_id"])
        target.update(price=round(args["price"], 2), updated_at=rate["updated_at"])
        return after == expected and result == {**rate, "zone": zone["name"], "previous_price": previous["price"]}
    if name == "issue_billing_credit":
        expected = copy.deepcopy(before)
        expected["billing_charges"].append(result)
        return (after == expected and result["type"] == "credit" and result["amount"] == -round(args["amount"], 2)
                and result["credits_charge_id"] == args["charge_id"] and result["description"] == args["description"])
    if name == "cancel_app_subscription":
        expected = copy.deepcopy(before)
        target = next(s for s in expected["app_subscriptions"] if s["id"] == args["subscription_id"])
        target.update(status="cancelled", cancelled_on=result["cancelled_on"])
        return after == expected and result == target
    order_id = args["order_id"]
    old_order, new_order = before["orders"][order_id], after["orders"][order_id]
    expected = copy.deepcopy(before)
    target = expected["orders"][order_id]
    if name == "update_order_shipping_address":
        target["shipping_address"].update(args["address"])
        return after == expected and result == target["shipping_address"]
    if name == "cancel_order":
        target.update(cancelled_at=new_order["cancelled_at"], cancel_reason=args["reason"])
    elif name == "add_order_note":
        target["note"] = f"{old_order['note']}\n{args['note']}".strip()
        return after == expected and result == {"order_id": order_id, "note": target["note"]}
    elif name == "recalculate_order_shipping":
        rate = next(r for z in before["delivery_profile"]["zones"] for r in z["rates"] if r["id"] == old_order["shipping_lines"][0]["rate_id"])
        target["shipping_lines"][0]["price"] = rate["price"]
        target["total_price"] = round(target["subtotal_price"] + rate["price"], 2)
        target["total_outstanding"] = round(max(0, target["total_price"] - sum(t["amount"] for t in target["transactions"] if t["kind"] == "sale")), 2)
    elif name == "create_refund":
        target["refunds"].append(result)
        if len(new_order["transactions"]) != len(old_order["transactions"]) + 1:
            return False
        transaction = new_order["transactions"][-1]
        target["transactions"].append(transaction)
        remaining = round(sum(t["amount"] for t in old_order["transactions"] if t["kind"] == "sale" and t["status"] == "success") - sum(r["amount"] for r in target["refunds"]), 2)
        target["financial_status"] = "refunded" if remaining == 0 else "partially_refunded"
        return (after == expected and result["amount"] == round(args["amount"], 2)
                and result["reason"] == args["reason"] and result["notify_customer"] == args["notify_customer"]
                and transaction["kind"] == "refund" and transaction["amount"] == result["amount"])
    else:
        return False
    return after == expected and result == target


class ToolSession:
    """Per-ticket capability boundary; the model never receives FIXTURES."""

    def __init__(self, tools: tuple[BoundAdminTool, ...], shop_domain: str):
        self.tools = {t.name: t for t in tools}
        self.shop_domain = shop_domain
        self.audit = []
        self.shop_verified = False
        self.seen_orders, self.seen_rates, self.seen_charges, self.seen_subscriptions = set(), set(), set(), set()

    def _observe(self, value):
        if isinstance(value, list):
            for item in value:
                self._observe(item)
        elif isinstance(value, dict):
            for key, target in [("order_id", self.seen_orders), ("rate_id", self.seen_rates)]:
                if key in value:
                    target.add(value[key])
            if "id" in value:
                if "billed_on" in value:
                    self.seen_charges.add(value["id"])
                elif "activated_on" in value:
                    self.seen_subscriptions.add(value["id"])
                elif "updated_at" in value and "price" in value:
                    self.seen_rates.add(value["id"])
            for item in value.values():
                self._observe(item)

    def _check_write_limit(self, name, args):
        """Enforce the supplied mock's monetary ceilings BEFORE dispatch."""
        store = mock_admin.FIXTURES[self.shop_domain]
        if name == "issue_billing_credit":
            charge = next((c for c in store["billing_charges"] if c["id"] == args["charge_id"] and c["type"] != "credit"), None)
            if charge is None:
                raise ToolBoundaryError("Credit target must be an existing non-credit charge")
            already = sum(-c["amount"] for c in store["billing_charges"]
                          if c["type"] == "credit" and c.get("credits_charge_id") == args["charge_id"])
            available = round(charge["amount"] - already, 2)
            kind = "remaining_charge_balance"
        elif name == "create_refund":
            order = store["orders"][args["order_id"]]
            captured = sum(t["amount"] for t in order["transactions"] if t["kind"] == "sale" and t["status"] == "success")
            available = round(captured - sum(r["amount"] for r in order["refunds"]), 2)
            kind = "remaining_refundable_balance"
        else:
            return
        requested = round(args["amount"], 2)
        if requested <= 0 or requested > available:
            error = f"Write blocked before execution: amount {requested:.2f} must be positive and at most the {kind} {available:.2f}."
            self.audit.append({"tool": name, "effect": "write", "arguments": args,
                "status": "blocked", "executed": False, "checked_against_store": True,
                "limit_kind": kind, "available": available, "requested": requested, "error": error})
            raise WriteLimitError(error)

    def execute(self, name, arguments):
        if name not in self.tools:
            raise ToolBoundaryError(f"Tool {name!r} is not bound to this specialist")
        tool = self.tools[name]
        try:
            args = tool.arguments_model.model_validate(arguments).model_dump()
        except ValidationError:
            raise ToolBoundaryError("Tool arguments failed strict schema validation") from None
        if args["shop_domain"] != self.shop_domain:
            raise ToolBoundaryError("Cross-store tool call blocked")
        if name != "get_shop" and not self.shop_verified:
            raise ToolBoundaryError("Read get_shop successfully before any other call")
        if tool.effect == "write":
            for key, seen in [("order_id", self.seen_orders), ("rate_id", self.seen_rates),
                              ("charge_id", self.seen_charges), ("subscription_id", self.seen_subscriptions)]:
                if key in args and args[key] not in seen:
                    raise ToolBoundaryError(f"Read and verify {key} before writing")
            if name == "issue_billing_credit" and not args["charge_id"]:
                raise ToolBoundaryError("A verified charge_id is required for a credit")
            self._check_write_limit(name, args)
        before = copy.deepcopy(mock_admin.FIXTURES.get(self.shop_domain))
        log_start = len(mock_admin.CALL_LOG)
        try:
            result = tool.function(**args)
        except mock_admin.ToolError as exc:
            unchanged = before == mock_admin.FIXTURES.get(self.shop_domain)
            # A not-found read can be checked against store absence just as a
            # successful read can be checked against the returned record.
            expected_missing = (name == "get_shop" and before is None) or (
                name in {"get_order", "list_order_transactions", "calculate_refund"}
                and before is not None and args["order_id"] not in before["orders"]
            )
            log_checked = mock_admin.CALL_LOG[log_start:] == [{"tool": name, "args": args,
                                                             "timestamp": mock_admin.CALL_LOG[-1]["timestamp"]}]
            self.audit.append({"tool": name, "effect": tool.effect, "arguments": args,
                               "status": "tool_error", "error": str(exc), "store_changed": not unchanged,
                               "checked_against_store": unchanged and expected_missing,
                               "call_log_matches": log_checked})
            raise
        after = copy.deepcopy(mock_admin.FIXTURES[self.shop_domain])
        checked = check_result(name, args, result, before, after)
        log_checked = mock_admin.CALL_LOG[log_start:] == [{"tool": name, "args": args,
                                                         "timestamp": mock_admin.CALL_LOG[-1]["timestamp"]}]
        self.audit.append({"tool": name, "effect": tool.effect, "arguments": args, "result": result,
                           "status": "completed", "checked_against_store": checked,
                           "call_log_matches": log_checked, "before_sha256": digest(before),
                           "after_sha256": digest(after), "changed_paths": changed_paths(before, after)})
        if not checked or not log_checked:
            raise ToolBoundaryError("Tool result or call log did not match fixture data")
        self.shop_verified = self.shop_verified or name == "get_shop"
        self._observe(result)
        return result
