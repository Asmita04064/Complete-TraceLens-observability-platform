"""Small local knowledge-base abstraction used by the observed agent."""

from typing import Any

from app.instrumentation.decorators import traced_function


class KnowledgeBase:
    """Retrieve shipping policy context from a local document collection."""

    documents = [
        {
            "id": "shipping-policy",
            "text": "In-transit orders show an estimated delivery date and tracking number."
        },
        {
            "id": "delivery-policy",
            "text": "Customers can use the order status and carrier tracking number to follow delivery."
        },
    ]

    @traced_function(event_type="knowledge_base_search", component="local_knowledge_base")
    def search(self, query: str) -> dict[str, Any]:
        terms = {word.lower().strip("?.,!") for word in query.split() if len(word) > 2}
        matches = [document for document in self.documents if any(term in document["text"].lower() for term in terms)]
        return {"query": query, "result_count": len(matches), "documents": matches}
