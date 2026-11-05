# Test set provenance

`example_tickets.json` contains eight original synthetic examples created for
this project. They are NOT an official Shopify dataset or the user's supplied
merchant tickets test set. None is presented as Maria's original ticket.

The requested test set, Maria's original message and her expected route have
not been supplied or found. Add the actual publishable, anonymized test set as
`data/shopify_merchant_tickets.json`, preserving its original expected labels.
Document its source and redistribution permission here before publishing it.

Accepted format is a nonempty JSON array. Each record has exactly three fields:

```json
{"id": "original-case-id", "message": "Original merchant message", "expected_route": "billing"}
```

`expected_route` must be `billing` or `orders`. IDs must be unique. The evaluator
passes only `message` to the graph and keeps the expected label separate.
