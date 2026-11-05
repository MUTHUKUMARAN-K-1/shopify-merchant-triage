# Test set provenance

The user supplied **Shopify Merchant Ticket Test Set (24 labelled tickets).csv**
alongside **Meeting-Notes.md** for this public-repository task on 5 November
2026. The original CSV is preserved byte-for-byte at
`source/shopify_merchant_tickets.csv`. No upstream public source or license was
supplied; no third-party dataset license is asserted here.

Source SHA-256:
`9aa9f5f90263bad16092a961ddf9bd86a8f8de7127c3eaaf85ec0d37c07fe294`

## Reproducible evaluation input

Run `python scripts/import_tickets.py` from the repository root to recreate
`shopify_merchant_tickets.json`. The conversion preserves all 24 records, in
source order, with this mapping:

| JSON field | CSV source |
| --- | --- |
| `id` | `ticket_id`, unchanged |
| `message` | `subject` + two newlines + `message_body`, unchanged |
| `expected_route` | `expected_route`, unchanged |

The JSON contains 12 `billing` and 12 `orders` labels. Merchant names, domains,
dates, amounts and order IDs remain in the source CSV. Expected tool calls,
fixes, escalation flags and mixed-issue flags also remain there for subsequent
milestones. They are never included in model input for this triage evaluation.
The current node returns only route and reason and does not execute fixes or
implement escalation. The source has four escalation cases and one mixed-issue
case; their route labels still apply at this milestone.

## Maria's acceptance case

- Merchant: Maria Sousa, Barro Azul Cerâmica.
- Exact ID: `SUP-48213`.
- Expected route: `orders`.
- Issue: checkout rates for domestic Portugal and Europe are swapped.
- Reference routing justification: the request concerns shipping rate
  configuration and affected customer orders.

The justification above is a human reference, not a model response or a live
test result. Source `expected_fix` belongs to a future orders specialist:
restore the shipping-zone rates and list affected orders. This triage node
does not perform those actions.

```bash
merchant-triage validate data/shopify_merchant_tickets.json
merchant-triage validate data/shopify_merchant_tickets.json --ticket-id SUP-48213
merchant-triage evaluate data/shopify_merchant_tickets.json \
  --ticket-id SUP-48213 --output reports/maria-live.json
```

## Supplemental examples

`example_tickets.json` contains eight original synthetic examples created before
the supplied set was available. They are separate from the 24 supplied tickets.
The earlier web search did not establish the original dataset; the uploaded CSV
is now the authoritative source for this project. No public alternative was
substituted and no original expected label was inferred or changed.
