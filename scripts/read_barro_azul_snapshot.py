"""Host-only read evidence: no model calls and no write tools bound."""

import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path

from merchant_triage import mock_admin
from merchant_triage.admin_tools import ToolSession, bind_tools, digest
from merchant_triage.supplemental_fixtures import isolated_supplemental_store, load_supplemental_fixtures


def main():
    path = Path(__file__).resolve().parents[1] / "data/supplemental_fixtures/maria-barro-azul.json"
    seed = load_supplemental_fixtures(path)
    domain = "barro-azul-ceramica.myshopify.com"
    supplied = copy.deepcopy(mock_admin.FIXTURES)
    read_tools = tuple(t for t in bind_tools("orders") if t.name in {"get_shop", "get_delivery_profile"})
    with isolated_supplemental_store(seed):
        before = copy.deepcopy(mock_admin.FIXTURES)
        session = ToolSession(read_tools, domain)
        shop = session.execute("get_shop", {"shop_domain": domain})
        profile = session.execute("get_delivery_profile", {"shop_domain": domain})
        snapshot = profile["pre_incident_snapshot"]
        assert datetime.fromisoformat(snapshot["captured_at"]) < datetime.fromisoformat("2024-11-30T00:00:00+00:00")
        assert snapshot["profile_id"] == profile["id"]
        current = {z["id"]: z for z in profile["zones"]}
        previous = {z["id"]: z for z in snapshot["zones"]}
        assert previous["zone_ba_pt"]["countries"] == ["PT"]
        assert previous["zone_ba_pt"]["rates"][0]["price"] == 4.5
        assert current["zone_ba_pt"]["rates"][0]["price"] == previous["zone_ba_eu"]["rates"][0]["price"]
        assert current["zone_ba_eu"]["rates"][0]["price"] == previous["zone_ba_pt"]["rates"][0]["price"]
        assert mock_admin.FIXTURES == before
        assert all(c["effect"] == "read" and c["status"] == "completed" and c["checked_against_store"] and c["call_log_matches"] for c in session.audit)
        report = {
            "mode": "host_read_only_no_model", "seed_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bound_tools": [t.name for t in read_tools], "calls": session.audit,
            "shop": shop, "delivery_profile": profile,
            "store_unchanged": True, "before_sha256": digest(before), "after_sha256": digest(mock_admin.FIXTURES),
            "write_calls": 0,
        }
    assert mock_admin.FIXTURES == supplied
    report["supplied_store_restored"] = True
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
