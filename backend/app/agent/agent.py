"""AI Agent using Google Gemini with tool calling."""

import json
import os
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.agent.tools import OrderService
from app.instrumentation.context import (
    get_current_trace_id,
    get_current_event_id,
    set_current_event_id,
)
from app.instrumentation.tracer import Tracer


class AIAgent:
    """
    AI Agent that uses Google Gemini for reasoning and calls tools.

    The agent automatically creates trace events for:
    - LLM calls to Gemini
    - Tool calls to order service
    - Database queries
    """

    def __init__(self, db: Session):
        self.db = db
        self.tracer = Tracer(db)
        self.order_service = OrderService(db)

        # Get API key from environment
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY environment variable not set. "
                "Please set your Google Gemini API key."
            )

    def run(self, user_message: str) -> str:
        """
        Run the agent with a user message.

        This will:
        1. Send the message to Gemini with available tools
        2. Gemini decides which tool to call (if any)
        3. Execute the tool
        4. Send result back to Gemini
        5. Return final response

        All operations are automatically traced.

        Args:
            user_message: The user's request

        Returns:
            Final response from the agent
        """
        trace_id = get_current_trace_id()
        if not trace_id:
            raise RuntimeError("No active trace. Call start_trace() first.")

        try:
            # Import Google generative AI
            try:
                import google.generativeai as genai
            except ImportError:
                raise RuntimeError(
                    "google-generativeai not installed. "
                    "Install with: pip install google-generativeai"
                )

            # Configure Gemini
            genai.configure(api_key=self.api_key)

            # Define tools for the model
            tools = [
                {
                    "name": "get_order_status",
                    "description": "Get the current status of an order and its tracking information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {
                                "type": "string",
                                "description": "The order ID (e.g., ORD-1001)",
                            }
                        },
                        "required": ["order_id"],
                    },
                },
                {
                    "name": "get_customer_details",
                    "description": "Get customer information by customer ID",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {
                                "type": "string",
                                "description": "The customer ID",
                            }
                        },
                        "required": ["customer_id"],
                    },
                },
                {
                    "name": "list_customer_orders",
                    "description": "List all orders for a customer",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {
                                "type": "string",
                                "description": "The customer ID",
                            }
                        },
                        "required": ["customer_id"],
                    },
                },
            ]

            # Create tool configuration
            from google.generativeai.types import Tool
            tool_config = Tool(
                function_declarations=tools
            )

            # Create model with tool use
            model = genai.GenerativeModel(
                model_name="gemini-2.0-flash",
                tools=tool_config,
            )

            # First LLM call - user message
            parent_event_id = get_current_event_id()
            response = self._trace_llm_call(
                model,
                user_message,
                parent_event_id,
            )

            # Agentic loop - handle tool calls
            max_iterations = 5
            iteration = 0

            while iteration < max_iterations:
                iteration += 1

                # Check if model wants to call a tool
                if not response.candidates or not response.candidates[0].content.parts:
                    break

                tool_calls = [
                    part
                    for part in response.candidates[0].content.parts
                    if hasattr(part, "function_call")
                ]

                if not tool_calls:
                    # No tool calls, we're done
                    break

                # Execute tool calls
                tool_results = []
                for tool_call in tool_calls:
                    result = self._execute_tool(tool_call.function_call)
                    tool_results.append(
                        {
                            "type": "function_result",
                            "function_name": tool_call.function_call.name,
                            "id": tool_call.function_call.name,
                            "result": result,
                        }
                    )

                # Second LLM call - with tool results
                parent_event_id = get_current_event_id()
                response = self._trace_llm_call(
                    model,
                    user_message,
                    parent_event_id,
                    tool_results=tool_results,
                )

            # Extract final text response
            final_response = ""
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "text"):
                        final_response = part.text
                        break

            if not final_response:
                final_response = "I was unable to process your request. Please try again."

            return final_response

        except Exception as e:
            raise RuntimeError(f"Agent execution failed: {str(e)}") from e

    def _trace_llm_call(
        self,
        model: Any,
        user_message: str,
        parent_event_id: Optional[int] = None,
        tool_results: Optional[list] = None,
    ) -> Any:
        """
        Make a Gemini LLM call with automatic tracing.

        Args:
            model: The Gemini model instance
            user_message: The user message
            parent_event_id: Parent event ID from context
            tool_results: Optional tool results from previous calls

        Returns:
            The model's response
        """
        import time

        trace_id = get_current_trace_id()

        # Prepare input data for tracing
        input_data = {"user_message": user_message[:500]}
        if tool_results:
            input_data["tool_results_count"] = len(tool_results)

        start_time = time.perf_counter()
        status = "success"
        error_message = None
        output_data = None

        try:
            # Build conversation history
            messages = [{"role": "user", "content": user_message}]
            if tool_results:
                messages.append(
                    {
                        "role": "model",
                        "content": "",  # This will be populated from previous response
                    }
                )
                messages.extend(tool_results)

            # Call Gemini
            response = model.generate_content(
                messages if tool_results else user_message,
                stream=False,
            )

            # Capture output
            output_text = ""
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "text"):
                        output_text = part.text
                        break

            output_data = {
                "response_text": output_text[:500] if output_text else "",
                "finish_reason": str(response.candidates[0].finish_reason) if response.candidates else "unknown",
            }

            return response

        except Exception as e:
            status = "failed"
            error_message = str(e)
            raise

        finally:
            end_time = time.perf_counter()

            # Create trace event
            from app.database import SessionLocal

            db = SessionLocal()
            try:
                tracer = Tracer(db)

                # Restore parent event context if needed
                if parent_event_id:
                    set_current_event_id(parent_event_id)

                event_db_id = tracer.create_event(
                    event_type="llm_call",
                    component="gemini-2.0-flash",
                    start_time=start_time,
                    end_time=end_time,
                    input_data=input_data,
                    output_data=output_data,
                    status=status,
                    error_message=error_message,
                )

                # Update current event for nested operations
                set_current_event_id(event_db_id)

            except Exception as e:
                print(f"Error creating LLM trace event: {e}")
            finally:
                db.close()

    def _execute_tool(self, function_call: Any) -> dict[str, Any]:
        """
        Execute a tool call from Gemini.

        Args:
            function_call: The function call object from Gemini

        Returns:
            Tool execution result
        """
        tool_name = function_call.name
        args = dict(function_call.args)

        # Save parent event context
        parent_event_id = get_current_event_id()

        try:
            if tool_name == "get_order_status":
                result = self.order_service.get_order_status(args["order_id"])
            elif tool_name == "get_customer_details":
                result = self.order_service.get_customer_details(args["customer_id"])
            elif tool_name == "list_customer_orders":
                result = self.order_service.list_customer_orders(args["customer_id"])
            else:
                raise ValueError(f"Unknown tool: {tool_name}")

            return {"success": True, "data": result}

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            # Restore parent event context for next LLM call
            if parent_event_id:
                set_current_event_id(parent_event_id)
