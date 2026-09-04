"""Real tools for the AI agent."""

import time
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.models.agent import Order, Customer
from app.instrumentation.decorators import traced_function


class OrderService:
    """Service for order-related operations."""

    def __init__(self, db: Session):
        self.db = db

    @traced_function(event_type="database_query", component="postgresql")
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get order status from database.

        Args:
            order_id: The order ID to look up

        Returns:
            Order details or error information
        """
        order = (
            self.db.query(Order)
            .filter(Order.order_id == order_id)
            .first()
        )

        if not order:
            raise ValueError(f"Order {order_id} not found")

        return {
            "order_id": order.order_id,
            "customer_id": order.customer_id,
            "status": order.status,
            "total_amount": order.total_amount,
            "order_date": order.order_date.isoformat(),
            "estimated_delivery": order.estimated_delivery.isoformat() if order.estimated_delivery else None,
            "tracking_number": order.tracking_number,
            "items": order.items_description,
        }

    @traced_function(event_type="database_query", component="postgresql")
    def get_customer_details(self, customer_id: str) -> Dict[str, Any]:
        """
        Get customer details from database.

        Args:
            customer_id: The customer ID to look up

        Returns:
            Customer details
        """
        customer = (
            self.db.query(Customer)
            .filter(Customer.customer_id == customer_id)
            .first()
        )

        if not customer:
            raise ValueError(f"Customer {customer_id} not found")

        return {
            "customer_id": customer.customer_id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "address": customer.address,
        }

    @traced_function(event_type="database_query", component="postgresql")
    def list_customer_orders(self, customer_id: str) -> list[Dict[str, Any]]:
        """
        List all orders for a customer.

        Args:
            customer_id: The customer ID

        Returns:
            List of orders
        """
        orders = (
            self.db.query(Order)
            .filter(Order.customer_id == customer_id)
            .order_by(Order.order_date.desc())
            .all()
        )

        return [
            {
                "order_id": order.order_id,
                "status": order.status,
                "total_amount": order.total_amount,
                "order_date": order.order_date.isoformat(),
                "estimated_delivery": order.estimated_delivery.isoformat() if order.estimated_delivery else None,
            }
            for order in orders
        ]
