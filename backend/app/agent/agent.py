"""Customer-support workload observed by TraceLens."""

import re

from sqlalchemy.orm import Session

from app.agent.knowledge_base import KnowledgeBase
from app.agent.llm import GeminiProvider
from app.agent.order_api import OrderManagementClient
from app.agent.tools import OrderService
from app.instrumentation.context import get_current_trace_id
from app.instrumentation.tracer import Tracer


class AIAgent:
    """Run the customer-support workflow; TraceLens remains the product under test."""

    def __init__(self, db: Session):
        self.db = db
        self.llm = GeminiProvider(db)
        self.knowledge_base = KnowledgeBase()
        self.order_service = OrderService(db)
        self.order_api = OrderManagementClient(db)

    def run(self, user_message: str) -> str:
        if not get_current_trace_id():
            raise RuntimeError("No active trace. Call start_trace() first.")

        analysis = self.llm.generate(
            f"Analyze this customer request and list the information required to answer it:\n{user_message}",
            "llm_1_request_analysis",
        )
        knowledge = self.knowledge_base.search(f"shipping delivery policy {user_message}")
        decision = self.llm.generate(
            "Determine the order ID to look up and the next actions using the request analysis and policy context.\n"
            f"Request analysis: {analysis}\nKnowledge base: {knowledge}",
            "llm_2_action_planning",
        )
        order_id = self._extract_order_id(user_message) or self._extract_order_id(decision)
        if not order_id:
            raise ValueError("No order ID was found in the request")

        order = self.order_service.get_order_status(order_id)
        api_order = self.order_api.get_order(order_id)
        return self.llm.generate(
            "Answer the customer using the request, policy, database order, and order-management API results. "
            "Be concise and include status, estimated delivery, and tracking when available.\n"
            f"Request: {user_message}\nPolicy: {knowledge}\nDatabase: {order}\nOrder API: {api_order}",
            "llm_3_final_response",
        )

    @staticmethod
    def _extract_order_id(text: str) -> str | None:
        match = re.search(r"\bORD[- ]?[A-Z0-9-]*\d[A-Z0-9-]*\b", text.upper())
        return match.group(0).replace(" ", "-") if match else None
