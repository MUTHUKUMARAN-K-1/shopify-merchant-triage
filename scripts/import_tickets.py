"""Rebuild the evaluation JSON from the supplied CSV without changing labels."""

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/source/shopify_merchant_tickets.csv"
OUTPUT = ROOT / "data/shopify_merchant_tickets.json"


def convert(source=SOURCE):
    with source.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return [
        {"id": row["ticket_id"],
         "message": row["subject"] + "\n\n" + row["message_body"],
         "expected_route": row["expected_route"]}
        for row in rows
    ]


if __name__ == "__main__":
    records = convert()
    OUTPUT.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"tickets": len(records), "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest()}))
