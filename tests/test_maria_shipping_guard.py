"""Dispatcher boundary tests: real mock writes only inside isolated test stores."""

import copy
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from merchant_triage import mock_admin
from merchant_triage.admin_tools import (
    MARIA_SHIPPING_WRITE_LIMIT, MARIA_SHIPPING_TARGETS, MARIA_SHOP_DOMAIN,
    ToolSession, WriteLimitError, bind_tools,
)
from merchant_triage.supplemental_fixtures import isolated_supplemental_store, load_supplemental_fixtures


@pytest.fixture
def maria_session():
    seed = load_supplemental_fixtures(Path("data/supplemental_fixtures/maria-barro-azul.json"))
    # An observed, existing third rate proves rejection is policy enforcement,
    # rather than a not-found or unobserved-ID check.
    seed[MARIA_SHOP_DOMAIN]["delivery_profile"]["zones"][0]["rates"].append({
        "id": "rate_ba_express", "name": "Express", "price": 30.0,
        "currency": "EUR", "updated_at": "2024-11-01T00:00:00+00:00"})
    with isolated_supplemental_store(seed):
        tools = bind_tools("orders")
        spies = {t.name: Mock(wraps=t.function) for t in tools if t.effect == "write"}
        session = ToolSession(tuple(replace(t, function=spies[t.name]) if t.name in spies else t for t in tools), MARIA_SHOP_DOMAIN)
        session.execute("get_shop", {"shop_domain": MARIA_SHOP_DOMAIN})
        session.execute("get_delivery_profile", {"shop_domain": MARIA_SHOP_DOMAIN})
        yield session, spies


def write_rate(session, rate, price):
    return session.execute("update_shipping_rate", {"shop_domain": MARIA_SHOP_DOMAIN, "rate_id": rate, "price": price})


def assert_rejected_without_dispatch(session, spies, name, args, kind):
    before, log = copy.deepcopy(mock_admin.FIXTURES), copy.deepcopy(mock_admin.CALL_LOG)
    counts = {k: s.call_count for k, s in spies.items()}
    with pytest.raises(WriteLimitError):
        session.execute(name, {"shop_domain": MARIA_SHOP_DOMAIN, **args})
    assert {k: s.call_count for k, s in spies.items()} == counts
    assert mock_admin.CALL_LOG == log
    assert mock_admin.FIXTURES == before
    assert session.audit[-1]["status"] == "blocked"
    assert session.audit[-1]["executed"] is False
    assert session.audit[-1]["limit_kind"] == kind


def test_maria_third_write_blocked_before_mock_function(maria_session):
    session, spies = maria_session
    assert MARIA_SHIPPING_WRITE_LIMIT == 2
    original = copy.deepcopy(mock_admin.FIXTURES)
    for rate, target in MARIA_SHIPPING_TARGETS.items():
        write_rate(session, rate, target)
    assert spies["update_shipping_rate"].call_count == 2
    assert session.maria_write_attempts == 2
    profile = mock_admin.FIXTURES[MARIA_SHOP_DOMAIN]["delivery_profile"]
    rates = {r["id"]: r["price"] for z in profile["zones"] for r in z["rates"]}
    assert rates["rate_ba_pt_standard"] == 4.5 and rates["rate_ba_eu_standard"] == 14.9
    assert profile["pre_incident_snapshot"] == original[MARIA_SHOP_DOMAIN]["delivery_profile"]["pre_incident_snapshot"]
    for domain in original:
        if domain != MARIA_SHOP_DOMAIN:
            assert mock_admin.FIXTURES[domain] == original[domain]
    # Even an allowed target and a fresh read cannot reset the write budget.
    session.execute("get_delivery_profile", {"shop_domain": MARIA_SHOP_DOMAIN})
    assert_rejected_without_dispatch(session, spies, "update_shipping_rate",
        {"rate_id": "rate_ba_pt_standard", "price": 4.5}, "maria_write_budget")
    assert sum(c["tool"] == "update_shipping_rate" for c in mock_admin.CALL_LOG) == 2


@pytest.mark.parametrize("name,args,kind", [
    ("update_shipping_rate", {"rate_id": "rate_ba_express", "price": 14.9}, "maria_rate_allowlist"),
    ("update_shipping_rate", {"rate_id": "rate_ba_eu_standard", "price": 1.0}, "maria_target_price"),
    ("cancel_order", {"order_id": "#1234", "reason": "unrequested cancellation"}, "maria_rate_allowlist"),
])
def test_maria_out_of_scope_write_never_runs(maria_session, name, args, kind):
    session, spies = maria_session
    assert "rate_ba_express" in session.seen_rates
    assert_rejected_without_dispatch(session, spies, name, args, kind)
    for spy in spies.values():
        spy.assert_not_called()


def test_maria_duplicate_rate_blocked_before_second_write(maria_session):
    session, spies = maria_session
    write_rate(session, "rate_ba_pt_standard", 4.5)
    assert_rejected_without_dispatch(session, spies, "update_shipping_rate",
        {"rate_id": "rate_ba_pt_standard", "price": 4.5}, "maria_duplicate_rate")
    assert spies["update_shipping_rate"].call_count == 1


def test_maria_changed_profile_blocks_before_first_write(maria_session):
    session, spies = maria_session
    mock_admin.FIXTURES[MARIA_SHOP_DOMAIN]["delivery_profile"]["zones"][0]["rates"][0]["price"] = 12.0
    assert_rejected_without_dispatch(session, spies, "update_shipping_rate",
        {"rate_id": "rate_ba_pt_standard", "price": 4.5}, "maria_configuration")


def test_maria_configuration_change_between_writes_blocks_second(maria_session):
    session, spies = maria_session
    write_rate(session, "rate_ba_pt_standard", 4.5)
    mock_admin.FIXTURES[MARIA_SHOP_DOMAIN]["delivery_profile"]["zones"][1]["countries"].append("US")
    assert_rejected_without_dispatch(session, spies, "update_shipping_rate",
        {"rate_id": "rate_ba_eu_standard", "price": 14.9}, "maria_configuration")
    assert spies["update_shipping_rate"].call_count == 1


def test_maria_failed_write_consumes_attempt_and_prevents_retry(maria_session):
    session, spies = maria_session
    spies["update_shipping_rate"].side_effect = mock_admin.ToolError("simulated write failure")
    with pytest.raises(mock_admin.ToolError):
        write_rate(session, "rate_ba_pt_standard", 4.5)
    assert session.maria_write_attempts == 1
    assert_rejected_without_dispatch(session, spies, "update_shipping_rate",
        {"rate_id": "rate_ba_eu_standard", "price": 14.9}, "maria_stopped")
    assert spies["update_shipping_rate"].call_count == 1
