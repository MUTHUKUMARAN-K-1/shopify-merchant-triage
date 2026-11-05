"""
Mock Shopify Admin API tools for the merchant support agents.

Plain Python functions over an in-memory FIXTURES store. They mirror Admin API
resources: shop, orders, transactions, refunds, delivery profiles and rates,
app subscriptions, billing charges and order notes. Every call is appended to
CALL_LOG. reset_store() restores the fixtures and clears the log between
tickets.
"""

import copy
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional


class ToolError(Exception):
    """Raised when a call cannot be completed. The message is written for the agent to read."""


CALL_LOG: List[Dict[str, Any]] = []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _make_order(
    order_id: str,
    created_at: str,
    customer: str,
    address: Dict[str, str],
    line_items: List[Dict[str, Any]],
    shipping: Dict[str, Any],
    currency: str,
    fulfillment_status: str = "fulfilled",
) -> Dict[str, Any]:
    subtotal = round(sum(item["price"] * item["quantity"] for item in line_items), 2)
    total = round(subtotal + shipping["price"], 2)
    number = order_id.lstrip("#")
    return {
        "order_id": order_id,
        "created_at": created_at,
        "customer": {"name": customer},
        "line_items": line_items,
        "subtotal_price": subtotal,
        "shipping_lines": [{**shipping, "currency": currency}],
        "total_price": total,
        "total_outstanding": 0.0,
        "currency": currency,
        "shipping_address": {"name": customer, **address},
        "financial_status": "paid",
        "fulfillment_status": fulfillment_status,
        "cancelled_at": None,
        "cancel_reason": None,
        "note": "",
        "refunds": [],
        "transactions": [
            {
                "id": f"txn_{number}_1",
                "kind": "sale",
                "status": "success",
                "amount": total,
                "currency": currency,
                "gateway": "shopify_payments",
                "processed_at": created_at,
            }
        ],
    }


def _lisbon_orders() -> Dict[str, Dict[str, Any]]:
    destinations = [
        ("ES", "Madrid", "28012", "Calle de Atocha"),
        ("FR", "Lyon", "69002", "Rue de la République"),
        ("DE", "Berlin", "10115", "Invalidenstraße"),
        ("NL", "Utrecht", "3511 LX", "Oudegracht"),
        ("IT", "Milano", "20121", "Via Solferino"),
        ("BE", "Gent", "9000", "Veldstraat"),
        ("IE", "Dublin", "D02 X285", "Camden Street"),
        ("AT", "Wien", "1070", "Neubaugasse"),
    ]
    products = [
        ("Azulejo tile set, Lisboa blue (6)", 42.00),
        ("Hand-painted serving platter", 58.00),
        ("Sardine wall plate", 24.50),
        ("Espresso cup pair, cobalt", 19.00),
        ("Tile coaster set (4)", 16.00),
    ]
    first_names = ["Lucía", "Camille", "Jonas", "Sanne", "Giulia",
                   "Thomas", "Aoife", "Stefan", "Inès", "Pieter"]
    last_names = ["Moreno", "Laurent", "Becker", "de Vries",
                  "Ricci", "Peeters", "Byrne", "Huber"]
    days = ["2024-11-29", "2024-11-30", "2024-12-01", "2024-12-02"]

    orders: Dict[str, Dict[str, Any]] = {}
    for i in range(40):
        country, city, zip_code, street = destinations[i % len(destinations)]
        title, price = products[i % len(products)]
        order_id = f"#{1160 + i}"
        orders[order_id] = _make_order(
            order_id=order_id,
            created_at=f"{days[i // 10]}T{8 + i % 10:02d}:{(i * 7) % 60:02d}:00+00:00",
            customer=f"{first_names[i % 10]} {last_names[i % 8]}",
            address={"address1": f"{street} {12 + i}", "city": city,
                     "zip": zip_code, "country_code": country},
            line_items=[{"title": title, "quantity": 1 + i % 2, "price": price}],
            shipping={"title": "EU Standard", "price": 0.00, "rate_id": "rate_eu_standard"},
            currency="EUR",
            fulfillment_status="fulfilled" if i < 30 else "unfulfilled",
        )

    orders["#1158"] = _make_order(
        "#1158", "2024-11-28T17:22:00+00:00", "Mathilde Krause",
        {"address1": "Schönhauser Allee 41", "city": "Berlin", "zip": "10435", "country_code": "DE"},
        [{"title": "Hand-painted serving platter", "quantity": 1, "price": 58.00}],
        {"title": "EU Standard", "price": 14.90, "rate_id": "rate_eu_standard"},
        "EUR",
    )
    orders["#1200"] = _make_order(
        "#1200", "2024-12-03T10:05:00+00:00", "Rui Carvalho",
        {"address1": "Rua do Almada 88", "city": "Porto", "zip": "4050-032", "country_code": "PT"},
        [{"title": "Sardine wall plate", "quantity": 2, "price": 24.50}],
        {"title": "CTT Domestic", "price": 4.90, "rate_id": "rate_pt_ctt"},
        "EUR", fulfillment_status="unfulfilled",
    )
    return orders


def _charge(charge_id: str, kind: str, description: str, amount: float,
            billed_on: str, subscription_id: Optional[str] = None) -> Dict[str, Any]:
    return {
        "id": charge_id,
        "type": kind,
        "description": description,
        "subscription_id": subscription_id,
        "amount": amount,
        "currency": "USD",
        "billed_on": billed_on,
        "billing_period": billed_on[:7],
    }


FIXTURES: Dict[str, Dict[str, Any]] = {
    "azulejo-ceramica-lisboa.myshopify.com": {
        "shop": {"name": "Azulejo Cerâmica Lisboa", "domain": "azulejo-ceramica-lisboa.myshopify.com",
                 "owner": "Maria Santos", "country": "PT", "currency": "EUR",
                 "plan": "Basic", "timezone": "Europe/Lisbon"},
        "orders": _lisbon_orders(),
        "delivery_profile": {
            "id": "dp_azulejo_general",
            "name": "General profile",
            "origin": "Rua de São Bento 212, 1200-821 Lisboa, PT",
            "zones": [
                {"id": "zone_pt", "name": "Portugal", "countries": ["PT"], "rates": [
                    {"id": "rate_pt_ctt", "name": "CTT Domestic", "price": 4.90,
                     "currency": "EUR", "updated_at": "2024-03-11T09:14:00+00:00"}]},
                {"id": "zone_eu", "name": "European Union",
                 "countries": ["ES", "FR", "DE", "NL", "IT", "BE", "IE", "AT"], "rates": [
                    {"id": "rate_eu_standard", "name": "EU Standard", "price": 0.00,
                     "currency": "EUR", "updated_at": "2024-11-28T23:41:00+00:00"},
                    {"id": "rate_eu_express", "name": "EU Express", "price": 24.90,
                     "currency": "EUR", "updated_at": "2024-03-11T09:14:00+00:00"}]},
                {"id": "zone_row", "name": "Rest of world", "countries": ["*"], "rates": [
                    {"id": "rate_row_tracked", "name": "International Tracked", "price": 29.90,
                     "currency": "EUR", "updated_at": "2024-03-11T09:14:00+00:00"}]},
            ],
        },
        "app_subscriptions": [
            {"id": "sub_lbl_3310", "app_name": "LabelDesk Shipping Labels", "plan": "Starter",
             "price": 9.99, "currency": "USD", "status": "active",
             "activated_on": "2024-02-02", "cancelled_on": None},
        ],
        "billing_charges": [
            _charge("chg_az_1101", "subscription", "Shopify Basic plan", 39.00, "2024-11-30"),
            _charge("chg_az_1102", "app_subscription", "LabelDesk Shipping Labels - Starter",
                    9.99, "2024-11-30", "sub_lbl_3310"),
            _charge("chg_az_1103", "transaction_fee", "Third-party payment fees, November", 6.42,
                    "2024-11-30"),
        ],
    },
    "northwind-coffee-roasters.myshopify.com": {
        "shop": {"name": "Northwind Coffee Roasters", "domain": "northwind-coffee-roasters.myshopify.com",
                 "owner": "Owen Brooks", "country": "US", "currency": "USD",
                 "plan": "Shopify", "timezone": "America/Chicago"},
        "orders": {
            "#4521": _make_order(
                "#4521", "2024-11-29T15:40:00+00:00", "Dana Whitfield",
                {"address1": "1820 Larimer St", "city": "Denver", "zip": "80202", "country_code": "US"},
                [{"title": "Single-origin Ethiopia, 1 lb", "quantity": 2, "price": 22.00},
                 {"title": "Ceramic pour-over dripper", "quantity": 1, "price": 34.00}],
                {"title": "USPS Ground Advantage", "price": 8.50, "rate_id": "rate_us_ground"},
                "USD",
            ),
            "#4533": _make_order(
                "#4533", "2024-12-01T19:12:00+00:00", "Kofi Mensah",
                {"address1": "77 Fulton St", "city": "Brooklyn", "zip": "11201", "country_code": "US"},
                [{"title": "Holiday blend, 12 oz", "quantity": 3, "price": 17.00}],
                {"title": "USPS Ground Advantage", "price": 8.50, "rate_id": "rate_us_ground"},
                "USD", fulfillment_status="unfulfilled",
            ),
        },
        "delivery_profile": {
            "id": "dp_northwind_general", "name": "General profile",
            "origin": "410 N Racine Ave, Chicago, IL 60642, US",
            "zones": [
                {"id": "zone_us", "name": "United States", "countries": ["US"], "rates": [
                    {"id": "rate_us_ground", "name": "USPS Ground Advantage", "price": 8.50,
                     "currency": "USD", "updated_at": "2024-06-20T14:00:00+00:00"}]},
            ],
        },
        "app_subscriptions": [
            {"id": "sub_rvw_2207", "app_name": "ReviewStream Product Reviews", "plan": "Growth",
             "price": 19.99, "currency": "USD", "status": "active",
             "activated_on": "2024-05-14", "cancelled_on": None},
        ],
        "billing_charges": [
            _charge("chg_nw_5501", "subscription", "Shopify plan", 105.00, "2024-11-30"),
            _charge("chg_nw_5502", "app_subscription", "ReviewStream Product Reviews - Growth",
                    19.99, "2024-11-30", "sub_rvw_2207"),
            _charge("chg_nw_5503", "app_subscription", "ReviewStream Product Reviews - Growth",
                    19.99, "2024-11-30", "sub_rvw_2207"),
        ],
    },
    "maple-and-thread.myshopify.com": {
        "shop": {"name": "Maple & Thread", "domain": "maple-and-thread.myshopify.com",
                 "owner": "Chloe Tremblay", "country": "CA", "currency": "USD",
                 "plan": "Basic", "timezone": "America/Toronto"},
        "orders": {
            "#2088": _make_order(
                "#2088", "2024-11-26T13:30:00+00:00", "Avery Clarke",
                {"address1": "245 Queen St W", "city": "Toronto", "zip": "M5V 1Z4", "country_code": "CA"},
                [{"title": "Merino wool scarf, charcoal", "quantity": 1, "price": 64.00}],
                {"title": "Canada Post Expedited", "price": 12.00, "rate_id": "rate_ca_expedited"},
                "USD",
            ),
            "#2093": _make_order(
                "#2093", "2024-11-29T21:05:00+00:00", "Noor Haddad",
                {"address1": "1450 Rue Peel", "city": "Montréal", "zip": "H3A 1S9", "country_code": "CA"},
                [{"title": "Knit beanie, oat", "quantity": 2, "price": 28.00}],
                {"title": "Canada Post Expedited", "price": 12.00, "rate_id": "rate_ca_expedited"},
                "USD", fulfillment_status="unfulfilled",
            ),
            "#2101": _make_order(
                "#2101", "2024-12-02T16:48:00+00:00", "Ethan Roy",
                {"address1": "890 Granville St", "city": "Vancouver", "zip": "V6Z 1K3", "country_code": "CA"},
                [{"title": "Linen throw blanket", "quantity": 1, "price": 120.00}],
                {"title": "Canada Post Expedited", "price": 12.00, "rate_id": "rate_ca_expedited"},
                "USD", fulfillment_status="unfulfilled",
            ),
        },
        "delivery_profile": {
            "id": "dp_maple_general", "name": "General profile",
            "origin": "18 Rue Saint-Paul O, Montréal, QC H2Y 1Y8, CA",
            "zones": [
                {"id": "zone_ca", "name": "Canada", "countries": ["CA"], "rates": [
                    {"id": "rate_ca_expedited", "name": "Canada Post Expedited", "price": 12.00,
                     "currency": "USD", "updated_at": "2024-09-03T12:00:00+00:00"}]},
            ],
        },
        "app_subscriptions": [],
        "billing_charges": [
            _charge("chg_mt_7701", "subscription", "Shopify Basic plan", 39.00, "2024-11-30"),
            _charge("chg_mt_7702", "transaction_fee", "Third-party payment fees, November", 3.18,
                    "2024-11-30"),
        ],
    },
    "harbour-lane-books.myshopify.com": {
        "shop": {"name": "Harbour Lane Books", "domain": "harbour-lane-books.myshopify.com",
                 "owner": "Fiona Hale", "country": "GB", "currency": "USD",
                 "plan": "Basic", "timezone": "Europe/London"},
        "orders": {
            "#7714": _make_order(
                "#7714", "2024-11-30T11:20:00+00:00", "Oliver Pratt",
                {"address1": "14 Gloucester Rd", "city": "Bristol", "zip": "BS7 8AE", "country_code": "GB"},
                [{"title": "Signed first edition, The Tide Keeper", "quantity": 1, "price": 45.00}],
                {"title": "Royal Mail Tracked 48", "price": 4.20, "rate_id": "rate_gb_tracked48"},
                "USD",
            ),
        },
        "delivery_profile": {
            "id": "dp_harbour_general", "name": "General profile",
            "origin": "3 Harbour Lane, Falmouth TR11 3QY, GB",
            "zones": [
                {"id": "zone_gb", "name": "United Kingdom", "countries": ["GB"], "rates": [
                    {"id": "rate_gb_tracked48", "name": "Royal Mail Tracked 48", "price": 4.20,
                     "currency": "USD", "updated_at": "2024-04-08T08:30:00+00:00"}]},
            ],
        },
        "app_subscriptions": [
            {"id": "sub_bnd_4410", "app_name": "BundleCraft Product Bundles", "plan": "Pro",
             "price": 29.00, "currency": "USD", "status": "cancelled",
             "activated_on": "2024-08-01", "cancelled_on": "2024-11-18"},
        ],
        "billing_charges": [
            _charge("chg_hl_9901", "subscription", "Shopify Basic plan", 39.00, "2024-11-30"),
            _charge("chg_hl_9902", "app_subscription", "BundleCraft Product Bundles - Pro",
                    29.00, "2024-11-30", "sub_bnd_4410"),
        ],
    },
}

_SEED: Dict[str, Dict[str, Any]] = copy.deepcopy(FIXTURES)


def reset_store() -> None:
    """Restore FIXTURES to its initial state and clear CALL_LOG."""
    FIXTURES.clear()
    FIXTURES.update(copy.deepcopy(_SEED))
    CALL_LOG.clear()


def _log_call(tool: str, **args: Any) -> None:
    CALL_LOG.append({"tool": tool, "args": copy.deepcopy(args), "timestamp": _now()})


def _require_shop(shop_domain: str) -> Dict[str, Any]:
    store = FIXTURES.get(shop_domain)
    if store is None:
        raise ToolError(f"Shop '{shop_domain}' not found. Use the full *.myshopify.com domain.")
    return store


def _require_order(shop_domain: str, order_id: str) -> Dict[str, Any]:
    order = _require_shop(shop_domain)["orders"].get(order_id)
    if order is None:
        raise ToolError(f"Order '{order_id}' not found on {shop_domain}. Order IDs include the '#', e.g. '#1187'.")
    return order


def _refundable(order: Dict[str, Any]) -> float:
    captured = sum(t["amount"] for t in order["transactions"]
                   if t["kind"] == "sale" and t["status"] == "success")
    refunded = sum(r["amount"] for r in order["refunds"])
    return round(captured - refunded, 2)


def _parse_day(value: str, field: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ToolError(f"{field} must be an ISO date like '2024-11-29', got '{value}'.") from exc


def get_shop(shop_domain: str) -> Dict[str, Any]:
    """Return the shop's name, owner, country, currency, plan and timezone."""
    _log_call("get_shop", shop_domain=shop_domain)
    return copy.deepcopy(_require_shop(shop_domain)["shop"])


def get_order(shop_domain: str, order_id: str) -> Dict[str, Any]:
    """Return one order with line items, shipping lines, address, totals, statuses, refunds and note."""
    _log_call("get_order", shop_domain=shop_domain, order_id=order_id)
    return copy.deepcopy(_require_order(shop_domain, order_id))


def list_orders(
    shop_domain: str,
    created_on_min: Optional[str] = None,
    created_on_max: Optional[str] = None,
    shipping_rate_title: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return order summaries, optionally filtered by inclusive creation dates and shipping rate title."""
    _log_call("list_orders", shop_domain=shop_domain, created_on_min=created_on_min,
              created_on_max=created_on_max, shipping_rate_title=shipping_rate_title)
    store = _require_shop(shop_domain)
    day_min = _parse_day(created_on_min, "created_on_min") if created_on_min else None
    day_max = _parse_day(created_on_max, "created_on_max") if created_on_max else None

    summaries = []
    for order in store["orders"].values():
        created = datetime.fromisoformat(order["created_at"]).date()
        shipping = order["shipping_lines"][0]
        if day_min and created < day_min:
            continue
        if day_max and created > day_max:
            continue
        if shipping_rate_title and shipping["title"] != shipping_rate_title:
            continue
        summaries.append({
            "order_id": order["order_id"],
            "created_at": order["created_at"],
            "customer_name": order["customer"]["name"],
            "destination_country": order["shipping_address"]["country_code"],
            "shipping_title": shipping["title"],
            "shipping_price": shipping["price"],
            "total_price": order["total_price"],
            "currency": order["currency"],
            "financial_status": order["financial_status"],
            "fulfillment_status": order["fulfillment_status"],
        })
    return sorted(summaries, key=lambda s: s["created_at"])


def list_order_transactions(shop_domain: str, order_id: str) -> List[Dict[str, Any]]:
    """Return the sale and refund transactions recorded against an order."""
    _log_call("list_order_transactions", shop_domain=shop_domain, order_id=order_id)
    return copy.deepcopy(_require_order(shop_domain, order_id)["transactions"])


def calculate_refund(shop_domain: str, order_id: str, amount: float) -> Dict[str, Any]:
    """Work out how a refund of `amount` would be applied to the order's captured payment.

    Returns the parent transaction, the refundable balance before and after,
    and the resulting financial status. The order is left as it is.
    """
    _log_call("calculate_refund", shop_domain=shop_domain, order_id=order_id, amount=amount)
    order = _require_order(shop_domain, order_id)
    available = _refundable(order)
    if amount <= 0:
        raise ToolError("Refund amount must be greater than zero.")
    if round(amount, 2) > available:
        raise ToolError(f"Refund {amount:.2f} exceeds refundable balance {available:.2f} {order['currency']}.")
    after = round(available - amount, 2)
    return {
        "order_id": order_id,
        "currency": order["currency"],
        "amount": round(amount, 2),
        "refundable_before": available,
        "refundable_after": after,
        "parent_transaction_id": order["transactions"][0]["id"],
        "resulting_financial_status": "refunded" if after == 0 else "partially_refunded",
    }


def create_refund(shop_domain: str, order_id: str, amount: float, reason: str,
                  notify_customer: bool = False) -> Dict[str, Any]:
    """Refund `amount` to the buyer's original payment method.

    Appends a refund and a refund transaction to the order and sets
    financial_status to partially_refunded or refunded. Returns the refund.
    """
    _log_call("create_refund", shop_domain=shop_domain, order_id=order_id, amount=amount,
              reason=reason, notify_customer=notify_customer)
    order = _require_order(shop_domain, order_id)
    available = _refundable(order)
    if amount <= 0:
        raise ToolError("Refund amount must be greater than zero.")
    if round(amount, 2) > available:
        raise ToolError(f"Refund {amount:.2f} exceeds refundable balance {available:.2f} {order['currency']}.")

    created_at = _now()
    refund = {
        "id": f"rfd_{uuid.uuid4().hex[:10]}",
        "created_at": created_at,
        "amount": round(amount, 2),
        "currency": order["currency"],
        "reason": reason,
        "notify_customer": notify_customer,
    }
    order["refunds"].append(refund)
    order["transactions"].append({
        "id": f"txn_{uuid.uuid4().hex[:10]}",
        "kind": "refund",
        "status": "success",
        "amount": refund["amount"],
        "currency": order["currency"],
        "gateway": "shopify_payments",
        "parent_id": order["transactions"][0]["id"],
        "processed_at": created_at,
    })
    order["financial_status"] = "refunded" if _refundable(order) == 0 else "partially_refunded"
    return copy.deepcopy(refund)


def get_delivery_profile(shop_domain: str) -> Dict[str, Any]:
    """Return the shop's delivery profile: origin, zones, countries and rate names and prices."""
    _log_call("get_delivery_profile", shop_domain=shop_domain)
    return copy.deepcopy(_require_shop(shop_domain)["delivery_profile"])


def update_shipping_rate(shop_domain: str, rate_id: str, price: float) -> Dict[str, Any]:
    """Set a delivery rate's price for future checkouts. Returns the rate with its previous price."""
    _log_call("update_shipping_rate", shop_domain=shop_domain, rate_id=rate_id, price=price)
    if price < 0:
        raise ToolError("Rate price cannot be negative.")
    for zone in _require_shop(shop_domain)["delivery_profile"]["zones"]:
        for rate in zone["rates"]:
            if rate["id"] == rate_id:
                previous = rate["price"]
                rate["price"] = round(price, 2)
                rate["updated_at"] = _now()
                return {**copy.deepcopy(rate), "zone": zone["name"], "previous_price": previous}
    raise ToolError(f"Rate '{rate_id}' not found in the delivery profile of {shop_domain}.")


def recalculate_order_shipping(shop_domain: str, order_id: str) -> Dict[str, Any]:
    """Reprice an order's shipping line at the shop's current delivery rate.

    Finds the rate the order was placed at, writes that rate's current price onto
    the order's shipping line, and updates total_price and total_outstanding
    (what the buyer would owe beyond the amount already captured). Returns the order.
    """
    _log_call("recalculate_order_shipping", shop_domain=shop_domain, order_id=order_id)
    store = _require_shop(shop_domain)
    order = _require_order(shop_domain, order_id)
    shipping = order["shipping_lines"][0]
    rate = next((r for zone in store["delivery_profile"]["zones"] for r in zone["rates"]
                 if r["id"] == shipping["rate_id"]), None)
    if rate is None:
        raise ToolError(f"Rate '{shipping['rate_id']}' for order {order_id} no longer exists.")

    shipping["price"] = rate["price"]
    order["total_price"] = round(order["subtotal_price"] + rate["price"], 2)
    captured = sum(t["amount"] for t in order["transactions"] if t["kind"] == "sale")
    order["total_outstanding"] = round(max(0.0, order["total_price"] - captured), 2)
    return copy.deepcopy(order)


def update_order_shipping_address(shop_domain: str, order_id: str,
                                  address: Dict[str, str]) -> Dict[str, Any]:
    """Replace fields of an unfulfilled order's shipping address. Returns the new address."""
    _log_call("update_order_shipping_address", shop_domain=shop_domain, order_id=order_id,
              address=address)
    order = _require_order(shop_domain, order_id)
    if order["cancelled_at"]:
        raise ToolError(f"Order {order_id} is cancelled.")
    if order["fulfillment_status"] != "unfulfilled":
        raise ToolError(f"Order {order_id} is already {order['fulfillment_status']}; the address cannot change.")
    allowed = {"name", "address1", "address2", "city", "zip", "province", "country_code"}
    unknown = set(address) - allowed
    if unknown:
        raise ToolError(f"Unknown address fields: {sorted(unknown)}. Allowed: {sorted(allowed)}.")
    order["shipping_address"].update(address)
    return copy.deepcopy(order["shipping_address"])


def cancel_order(shop_domain: str, order_id: str, reason: str) -> Dict[str, Any]:
    """Cancel an unfulfilled order and record the reason. The payment is not refunded by this call."""
    _log_call("cancel_order", shop_domain=shop_domain, order_id=order_id, reason=reason)
    order = _require_order(shop_domain, order_id)
    if order["cancelled_at"]:
        raise ToolError(f"Order {order_id} was already cancelled at {order['cancelled_at']}.")
    if order["fulfillment_status"] != "unfulfilled":
        raise ToolError(f"Order {order_id} is {order['fulfillment_status']} and cannot be cancelled.")
    order["cancelled_at"] = _now()
    order["cancel_reason"] = reason
    return copy.deepcopy(order)


def add_order_note(shop_domain: str, order_id: str, note: str) -> Dict[str, Any]:
    """Append a line to the order's staff note. Returns the order id and the full note."""
    _log_call("add_order_note", shop_domain=shop_domain, order_id=order_id, note=note)
    order = _require_order(shop_domain, order_id)
    if not note.strip():
        raise ToolError("Note text cannot be empty.")
    order["note"] = f"{order['note']}\n{note}".strip()
    return {"order_id": order_id, "note": order["note"]}


def get_app_subscriptions(shop_domain: str) -> List[Dict[str, Any]]:
    """Return the shop's app subscriptions with plan, price, status and activation/cancellation dates."""
    _log_call("get_app_subscriptions", shop_domain=shop_domain)
    return copy.deepcopy(_require_shop(shop_domain)["app_subscriptions"])


def list_billing_charges(shop_domain: str,
                         billing_period: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return the shop's Shopify bill lines and credits, optionally for one period such as '2024-11'."""
    _log_call("list_billing_charges", shop_domain=shop_domain, billing_period=billing_period)
    charges = _require_shop(shop_domain)["billing_charges"]
    if billing_period:
        charges = [c for c in charges if c["billing_period"] == billing_period]
    return copy.deepcopy(charges)


def cancel_app_subscription(shop_domain: str, subscription_id: str) -> Dict[str, Any]:
    """Cancel an active app subscription so it stops billing. Returns the subscription."""
    _log_call("cancel_app_subscription", shop_domain=shop_domain, subscription_id=subscription_id)
    for subscription in _require_shop(shop_domain)["app_subscriptions"]:
        if subscription["id"] == subscription_id:
            if subscription["status"] == "cancelled":
                raise ToolError(f"Subscription {subscription_id} was already cancelled on {subscription['cancelled_on']}.")
            subscription["status"] = "cancelled"
            subscription["cancelled_on"] = _now()[:10]
            return copy.deepcopy(subscription)
    raise ToolError(f"Subscription '{subscription_id}' not found on {shop_domain}.")


def issue_billing_credit(shop_domain: str, amount: float, description: str,
                         charge_id: Optional[str] = None) -> Dict[str, Any]:
    """Add a credit line to the shop's Shopify bill, optionally against one charge. Returns the credit."""
    _log_call("issue_billing_credit", shop_domain=shop_domain, amount=amount,
              description=description, charge_id=charge_id)
    charges = _require_shop(shop_domain)["billing_charges"]
    if amount <= 0:
        raise ToolError("Credit amount must be greater than zero.")
    if charge_id:
        target = next((c for c in charges if c["id"] == charge_id and c["type"] != "credit"), None)
        if target is None:
            raise ToolError(f"Charge '{charge_id}' not found on {shop_domain}.")
        already = sum(-c["amount"] for c in charges if c["type"] == "credit" and c.get("credits_charge_id") == charge_id)
        if round(amount + already, 2) > target["amount"]:
            raise ToolError(f"Credit {amount:.2f} plus prior credits {already:.2f} exceeds charge {target['amount']:.2f} USD.")

    today = _now()[:10]
    credit = {
        **_charge(f"crd_{uuid.uuid4().hex[:10]}", "credit", description, -round(amount, 2), today),
        "credits_charge_id": charge_id,
    }
    charges.append(credit)
    return copy.deepcopy(credit)