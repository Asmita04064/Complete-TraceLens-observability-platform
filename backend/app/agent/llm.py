"""Provider boundary for real, instrumented LLM calls."""

import os
import time
from typing import Any

from app.instrumentation.context import get_current_event_id, set_current_event_id
from app.instrumentation.tracer import Tracer


class GeminiProvider:
    """Thin Gemini adapter. The adapter boundary is the instrumentation boundary."""

    def __init__(self, db):
        self.db = db
        self.mock_mode = os.getenv("MOCK_LLM", "false").lower() == "true"
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key and not self.mock_mode:
            raise RuntimeError("GEMINI_API_KEY environment variable not set")

    def generate(self, prompt: str, stage: str) -> str:
        started = time.perf_counter()
        status = "success"
        error_message = None
        output = None
        try:
            if self.mock_mode:
                time.sleep(0.001)
                output = {
                    "llm_1_request_analysis": "The request needs shipping policy and order details.",
                    "llm_2_action_planning": "Look up the order and confirm delivery status.",
                    "llm_3_final_response": "Your order is in transit. Please check the estimated delivery date and tracking number.",
                }.get(stage, "The request was processed.")
                return output
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            response = genai.GenerativeModel(self.model_name).generate_content(prompt, stream=False)
            output = getattr(response, "text", "") or ""
            if not output and getattr(response, "candidates", None):
                output = str(response.candidates[0].content)
            return output
        except Exception as exc:
            status = "failed"
            error_message = str(exc)
            raise
        finally:
            event_db = self.db
            event_id = Tracer(event_db).create_event(
                event_type="llm_call",
                component=self.model_name,
                start_time=started,
                end_time=time.perf_counter(),
                input_data={"stage": stage, "prompt": prompt[:2000]},
                output_data={"response": (output or "")[:2000], "usage": self._usage(response) if 'response' in locals() else None} if output is not None else None,
                status=status,
                error_message=error_message,
                metadata={"provider": "mock" if self.mock_mode else "gemini", "stage": stage, "mode": "mock" if self.mock_mode else "real"},
            )
            set_current_event_id(event_id)

    @staticmethod
    def _usage(response):
        metadata = getattr(response, "usage_metadata", None)
        if metadata is None:
            return None
        return {
            "prompt_tokens": getattr(metadata, "prompt_token_count", None),
            "completion_tokens": getattr(metadata, "candidates_token_count", None),
            "total_tokens": getattr(metadata, "total_token_count", None),
        }
