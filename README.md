# Shopify Merchant Triage

A small LangGraph entry node that reads a merchant's message and returns one
route (`billing` or `orders`) plus a short reason. Advisors currently sort these
tickets manually; this node is the common entry point before specialist agents.

## First-step scope and acceptance

1. Put the runnable node and the supplied Shopify merchant tickets test set in
   a public GitHub repository.
2. Call a free model through OpenRouter. Read the API key from the environment,
   outside the repository.
3. Run Maria's original ticket and compare the predicted route with the test
   set's expected route. Preserve the result and return an immutable commit link.

**Current status:** the supplied 24-ticket test set is imported, with 12 billing
and 12 orders labels. Maria Sousa is `SUP-48213`, expected `orders`: her Portugal
and Europe checkout shipping rates are swapped. The node and offline checks are
available. The first live run authenticated successfully but exposed inconsistent
routes across the free router's selected models: Maria failed standalone and
passed within the full set; the full set scored 22/24 with one wrong route and
one invalid response. The default is now pinned to a single free model with
clearer checkout-rate and partial-refund rules, pending a fresh live check.
See `reports/verification.json` and the preserved baseline in `reports/runs/`.

## Run locally

Python 3.11+ is required. From this directory:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

On Windows PowerShell, activate with `.\.venv\Scripts\Activate.ps1` instead.
Set `OPENROUTER_API_KEY` using your shell or secret manager. The program only
reads environment variables; `.env.example` is documentation and contains no key.
For example, a session-only Bash prompt avoids including the key in history:

```bash
read -rsp 'OpenRouter key: ' OPENROUTER_API_KEY
export OPENROUTER_API_KEY
export OPENROUTER_MODEL=nvidia/nemotron-3.5-super-vl:free
```

Or in PowerShell:

```powershell
$triageSecret = Read-Host 'OpenRouter key' -AsSecureString
$env:OPENROUTER_API_KEY = [System.Net.NetworkCredential]::new('', $triageSecret).Password
$env:OPENROUTER_MODEL = 'nvidia/nemotron-3.5-super-vl:free'
```

```bash
merchant-triage route 'My Shopify plan was charged twice this month.'
merchant-triage validate data/shopify_merchant_tickets.json
merchant-triage evaluate data/shopify_merchant_tickets.json --output reports/tickets-live.json
python -m pytest -q
```

The default is `nvidia/nemotron-3.5-super-vl:free`, pinned to avoid switching
models between cases. Reports record both requested and resolved models.
You may override it with another explicit `:free` model or `openrouter/free`;
the latter dynamically selects models and produced inconsistent baseline
results. Paid model IDs are rejected.
Free endpoint limits and structured-output availability can prevent a request;
these failures remain errors and do not produce a guessed route.

## Routing policy

| Route | Issue owner |
| --- | --- |
| `billing` | Merchant's Shopify plan, subscription, platform/app invoice, fees, billing card, payout, chargeback/dispute, payment-account hold or shipping-label invoice charge |
| `orders` | Checkout shipping rates/zones/profiles, customer purchase, fulfilment, delivery, tracking, cancellation, return, refund or order payment problem |

A customer-order refund goes to `orders`; a disputed Shopify subscription
charge goes to `billing`. For mixed messages, use the explicit primary request,
then the first actionable issue. A vague message goes to `orders` with an
explicit reason requesting advisor review. The supplied labels establish the
shipping-rate, shipping-label billing and chargeback boundaries above. Mixed
and vague-message tie-breaking remain project policy assumptions. This is a
development evaluation set used to clarify the policy, not an unseen benchmark.

## Graph and specialist integration

The first milestone compiles `START → triage → END`. To attach specialist agents:

```python
from merchant_triage import build_graph
from merchant_triage.openrouter import OpenRouterClassifier

def billing_agent(state):
    # Replace with your specialist agent; route and reason are already validated.
    return {"specialist_result": "Billing specialist received the ticket"}

def orders_agent(state):
    return {"specialist_result": "Orders specialist received the ticket"}

graph = build_graph(
    OpenRouterClassifier.from_env(),
    billing_specialist=billing_agent,
    orders_specialist=orders_agent,
)
result = graph.invoke({"message": "Customer order 1042 has not arrived."})
```

Both specialists sit behind triage and only the selected specialist runs. The
key and HTTP client stay outside graph state. The model receives the merchant
message as untrusted user content and must return a strict JSON schema. A
Pydantic check rejects unknown routes, blank reasons, extra fields, malformed
JSON and incomplete responses. Network/transient HTTP errors get at most three
attempts; authentication failures stop immediately. Prompt-injection resistance
is instructed but is not proven by the offline mock tests.

## Verify Maria against the original label

The original CSV is in `data/source/`; its reproducible evaluation mapping is
documented in `data/README.md`. Select Maria by her exact record ID:

```bash
merchant-triage validate data/shopify_merchant_tickets.json --ticket-id SUP-48213
merchant-triage evaluate data/shopify_merchant_tickets.json \
  --ticket-id SUP-48213 --output reports/maria-live.json
```

`validate` works without an API key or network access. It checks the JSON schema,
unique IDs and optional case selection, then prints the selected count, label
counts and dataset checksum without printing messages. This checks dataset
structure; it does not establish that the supplied labels are correct.

The evaluator sends only the message to the graph. It compares the output with
the expected label afterward and reports expected route, actual route, reason,
model IDs, timestamp and dataset SHA-256. A missing case errors before the model
is called. Exit codes are `0` for all routes matching, `1` for mismatches/API
errors in evaluation, and `2` for configuration/input errors. Reports contain
routing explanations and case IDs; review them before committing.

## Verification limits

Offline tests verify orchestration, HTTP request construction, strict validation,
retry limits, error handling, label isolation and evaluation exit codes. Mocked
responses do **not** establish classification accuracy or a successful live
OpenRouter call. A route match also does not independently grade reason quality.
Maria's original inputs and label are available, and the repository Actions
secret is configured. Her initial standalone prediction was wrong, while the
separate full-set prediction matched; neither is hidden by rerunning. The
meeting notes describe eventual autonomous
specialists, simulated admin tools and human handoffs. Those later milestones
are outside this first route-and-reason node. The notes mention Anthropic;
this implementation uses OpenRouter as explicitly requested for this step.

## Remaining handoff

1. Configure `OPENROUTER_API_KEY` outside the repository using the session-only
   instructions above, then run the Maria evaluation and the complete set.
2. Inspect mismatches and reasons, record the live model and results, and push
   reviewed reports at a new immutable commit.

Alternatively, add an Actions repository secret named `OPENROUTER_API_KEY`, then
run **Live ticket evaluation** from the repository's Actions tab. This manually
triggered workflow checks Maria and all 24 cases and saves the JSON reports as
the `live-triage-reports` artifact. It fails for mismatched routes or API errors;
offline push/PR checks never use a key. Reports are ignored by Git until reviewed
and deliberately added.

The repository is ready for these steps. Offline tests and synthetic examples
do not replace the pending original-ticket acceptance check.

## Primary references

- [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [OpenRouter Free Models Router](https://openrouter.ai/docs/guides/routing/routers/free-router)
- [OpenRouter structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs)
