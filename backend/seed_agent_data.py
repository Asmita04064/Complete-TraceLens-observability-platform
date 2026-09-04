"""Seed agent data (orders and customers) for real agent execution."""

from datetime import datetime, timedelta, timezone

from app.database import Base, SessionLocal, engine
from app.models.agent import Order, Customer


def seed_agent_data():
    """Seed realistic order and customer data for agent operations."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Check if data already exists
        existing_customers = db.query(Customer).count()
        if existing_customers > 0:
            print("Agent data already exists. Skipping seed.")
            return

        # Create customers
        customers = [
            Customer(
                customer_id="CUST-001",
                name="Alice Johnson",
                email="alice@example.com",
                phone="+1-555-0101",
                address="123 Main St, Springfield, IL 62701",
                created_at=datetime.now(timezone.utc) - timedelta(days=180),
            ),
            Customer(
                customer_id="CUST-002",
                name="Bob Smith",
                email="bob@example.com",
                phone="+1-555-0102",
                address="456 Oak Ave, Portland, OR 97201",
                created_at=datetime.now(timezone.utc) - timedelta(days=120),
            ),
            Customer(
                customer_id="CUST-003",
                name="Carol Williams",
                email="carol@example.com",
                phone="+1-555-0103",
                address="789 Pine Rd, Austin, TX 78701",
                created_at=datetime.now(timezone.utc) - timedelta(days=60),
            ),
        ]

        for customer in customers:
            db.add(customer)

        db.flush()

        # Create orders
        now = datetime.now(timezone.utc)

        orders = [
            Order(
                order_id="ORD-1001",
                customer_id="CUST-001",
                order_date=now - timedelta(days=5),
                status="in_transit",
                total_amount=149.99,
                items_description="Wireless Headphones, Phone Case",
                estimated_delivery=now + timedelta(days=2),
                tracking_number="TRK-2024-001-ABC",
                shipping_address="123 Main St, Springfield, IL 62701",
                created_at=now - timedelta(days=5),
            ),
            Order(
                order_id="ORD-1002",
                customer_id="CUST-001",
                order_date=now - timedelta(days=15),
                status="delivered",
                total_amount=89.99,
                items_description="USB Cable 3-pack",
                estimated_delivery=now - timedelta(days=13),
                tracking_number="TRK-2024-002-DEF",
                shipping_address="123 Main St, Springfield, IL 62701",
                created_at=now - timedelta(days=15),
            ),
            Order(
                order_id="ORD-1003",
                customer_id="CUST-002",
                order_date=now - timedelta(days=2),
                status="processing",
                total_amount=299.99,
                items_description="Laptop Stand, External SSD",
                estimated_delivery=now + timedelta(days=5),
                tracking_number="TRK-2024-003-GHI",
                shipping_address="456 Oak Ave, Portland, OR 97201",
                created_at=now - timedelta(days=2),
            ),
            Order(
                order_id="ORD-1004",
                customer_id="CUST-003",
                order_date=now - timedelta(days=30),
                status="delivered",
                total_amount=45.50,
                items_description="Screen Protector",
                estimated_delivery=now - timedelta(days=28),
                tracking_number="TRK-2024-004-JKL",
                shipping_address="789 Pine Rd, Austin, TX 78701",
                created_at=now - timedelta(days=30),
            ),
            Order(
                order_id="ORD-1005",
                customer_id="CUST-002",
                order_date=now - timedelta(days=8),
                status="shipped",
                total_amount=199.99,
                items_description="Mechanical Keyboard, Mouse Pad",
                estimated_delivery=now + timedelta(days=3),
                tracking_number="TRK-2024-005-MNO",
                shipping_address="456 Oak Ave, Portland, OR 97201",
                created_at=now - timedelta(days=8),
            ),
        ]

        for order in orders:
            db.add(order)

        db.commit()

        print(f"Agent data seed complete: {len(customers)} customers, {len(orders)} orders created.")

    finally:
        db.close()


if __name__ == "__main__":
    seed_agent_data()
