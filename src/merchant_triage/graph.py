from typing import Callable, NotRequired, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph

from .models import Decision, Route, RouteDecision
from .openrouter import Classification, TriageError


class TriageState(TypedDict):
    message: str
    shop_domain: NotRequired[str]
    merchant_name: NotRequired[str]
    decision: NotRequired[RouteDecision]
    route: NotRequired[Route]
    reason: NotRequired[str]
    requested_model: NotRequired[str]
    resolved_model: NotRequired[str]
    specialist_result: NotRequired[dict | str]


class Classifier(Protocol):
    def classify(self, message: str) -> Classification: ...


Specialist = Callable[[TriageState], dict]


def build_graph(
    classifier: Classifier,
    *,
    billing_specialist: Specialist | None = None,
    orders_specialist: Specialist | None = None,
):
    """Compile the triage-only graph or place both specialists behind triage."""
    if (billing_specialist is None) != (orders_specialist is None):
        raise ValueError("Provide both specialists, or neither for triage-only mode.")

    def triage(state: TriageState) -> dict:
        message = state.get("message")
        if not isinstance(message, str) or not message.strip() or len(message) > 20000:
            raise TriageError("Merchant message must contain 1–20000 characters.")
        result = classifier.classify(message)
        decision = Decision.model_validate(result.decision.model_dump())
        return {
            **decision.model_dump(),
            "decision": decision,
            "requested_model": result.requested_model,
            "resolved_model": result.resolved_model,
        }

    builder = StateGraph(TriageState)
    builder.add_node("triage", triage)
    builder.add_edge(START, "triage")
    if billing_specialist is None:
        builder.add_edge("triage", END)
    else:
        builder.add_node("billing_specialist", billing_specialist)
        builder.add_node("orders_specialist", orders_specialist)
        builder.add_conditional_edges(
            "triage", lambda state: state["decision"].route,
            {"billing": "billing_specialist", "orders": "orders_specialist"},
        )
        builder.add_edge("billing_specialist", END)
        builder.add_edge("orders_specialist", END)
    return builder.compile()
