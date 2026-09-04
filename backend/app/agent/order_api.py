"""Client for the local order-management HTTP service."""

import os
import time
import json
from urllib.request import Request, urlopen
from typing import Any

from app.instrumentation.context import set_current_event_id
from app.instrumentation.tracer import Tracer


class OrderManagementClient:
    def __init__(self, db):
        self.db = db
        self.base_url = os.getenv("ORDER_MANAGEMENT_API_URL", "http://127.0.0.1:8000")

    def get_order(self, order_id: str) -> dict[str, Any]:
        started = time.perf_counter()
        status = "success"
        error_message = None
        output = None
        try:
            request = Request(f"{self.base_url}/mock/order-management/orders/{order_id}", method="GET")
            with urlopen(request, timeout=10) as response:
                output = json.loads(response.read().decode("utf-8"))
            return output
        except Exception as exc:
            status = "failed"
            error_message = str(exc)
            raise
        finally:
            event_id = Tracer(self.db).create_event(
                event_type="external_api_call",
                component="order_management_api",
                start_time=started,
                end_time=time.perf_counter(),
                input_data={"order_id": order_id, "method": "GET"},
                output_data=output,
                status=status,
                error_message=error_message,
            )
            set_current_event_id(event_id)
