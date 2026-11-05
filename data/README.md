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

## Import the original cases

Preserve the source's messages and expected labels. If its columns have different
names, map those columns to the three fields above and document the mapping. Do
not infer Maria's expected route from this model's prediction. If the source uses
more than two routes, record the agreed mapping to `billing`/`orders` before
evaluating it; do not silently discard cases or relabel them.

Record the source URL or supplied filename, revision/date, license or permission
to publish, any anonymization, and Maria's exact case ID here when available.

Before configuring credentials, check the imported file locally:

```bash
merchant-triage validate data/shopify_merchant_tickets.json
merchant-triage validate data/shopify_merchant_tickets.json --ticket-id ORIGINAL_MARIA_ID
```

## Public-source search

A web, GitHub and Hugging Face search did not establish the requested original
dataset or Maria's case. These candidates were inspected but are not imported:

- [Customer-Support-AI-Employee evaluations](https://github.com/Ismail-2001/Customer-Support-AI-Employee/tree/e125e7c7bf5f2b8e039966a7ed22065ecb459ca0/evals):
  Shopify support examples with a different category taxonomy; no Maria case
  was present in `golden_dataset.json` at this revision.
- [Bitext customer support dataset](https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset):
  general support intents; not verified as the requested Shopify test set.

Neither candidate supplies evidence for Maria's expected route in this project.
