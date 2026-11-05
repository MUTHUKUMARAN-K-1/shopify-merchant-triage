"""Host-only, opt-in supplemental stores; never replace supplied fixture keys."""

import copy
import json
from contextlib import contextmanager

from . import mock_admin


def load_supplemental_fixtures(path):
    stores = json.loads(path.read_text(encoding="utf-8"))
    validate_supplemental_fixtures(stores)
    return stores


def validate_supplemental_fixtures(stores):
    if not isinstance(stores, dict) or not stores:
        raise ValueError("Supplemental fixtures must be a nonempty shop mapping")
    for domain, store in stores.items():
        if domain in mock_admin._SEED:
            raise ValueError("Supplemental fixtures cannot replace supplied shops")
        if (not isinstance(domain, str) or not domain.endswith(".myshopify.com")
                or not isinstance(store, dict)
                or set(store) != {"shop", "orders", "delivery_profile", "app_subscriptions", "billing_charges"}
                or not isinstance(store["shop"], dict) or store["shop"].get("domain") != domain
                or not isinstance(store["orders"], dict)
                or not isinstance(store["delivery_profile"], dict)
                or not isinstance(store["app_subscriptions"], list)
                or not isinstance(store["billing_charges"], list)):
            raise ValueError("Invalid supplemental shop structure or domain")


@contextmanager
def isolated_supplemental_store(stores=None):
    if stores is not None:
        validate_supplemental_fixtures(stores)
    mock_admin.reset_store()
    try:
        if stores is not None:
            mock_admin.FIXTURES.update(copy.deepcopy(stores))
        yield
    finally:
        mock_admin.reset_store()
