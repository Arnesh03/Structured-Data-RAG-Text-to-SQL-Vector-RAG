"""
Database setup: generates 1,000 fake e-commerce orders and loads them into SQLite.

Run standalone:  python database.py
"""
import csv
import random
import sqlite3
from datetime import datetime, timedelta

from faker import Faker

from config import CSV_PATH, DB_PATH, NUM_ORDERS

fake = Faker()
Faker.seed(42)
random.seed(42)

# ── Product Catalog ──────────────────────────────────────────────────
PRODUCTS = {
    "Electronics": [
        ("Wireless Earbuds", 29.99, 79.99),
        ("Bluetooth Speaker", 39.99, 149.99),
        ("Laptop Stand", 24.99, 59.99),
        ("USB-C Hub", 19.99, 49.99),
        ("Mechanical Keyboard", 49.99, 129.99),
        ("Gaming Mouse", 29.99, 89.99),
        ("Webcam HD", 39.99, 99.99),
        ("Portable Charger", 14.99, 49.99),
    ],
    "Clothing": [
        ("Cotton T-Shirt", 9.99, 29.99),
        ("Denim Jeans", 29.99, 69.99),
        ("Running Shoes", 49.99, 129.99),
        ("Winter Jacket", 59.99, 149.99),
        ("Baseball Cap", 9.99, 24.99),
        ("Hoodie", 24.99, 59.99),
    ],
    "Home & Kitchen": [
        ("Coffee Maker", 29.99, 89.99),
        ("Air Fryer", 49.99, 129.99),
        ("Blender", 24.99, 69.99),
        ("Cutting Board Set", 14.99, 39.99),
        ("Water Bottle", 9.99, 29.99),
        ("Desk Lamp", 19.99, 49.99),
    ],
    "Books": [
        ("Python Programming", 19.99, 49.99),
        ("Data Science Handbook", 24.99, 54.99),
        ("AI & Machine Learning", 29.99, 59.99),
        ("Business Strategy", 14.99, 34.99),
        ("Self-Help Guide", 9.99, 24.99),
    ],
}

STATUSES = ["Delivered", "Shipped", "Processing", "Cancelled", "Returned"]
STATUS_WEIGHTS = [0.55, 0.15, 0.10, 0.10, 0.10]
PAYMENT_METHODS = ["Credit Card", "Debit Card", "PayPal", "UPI", "Cash on Delivery"]
US_STATES = [
    "California", "Texas", "New York", "Florida", "Illinois",
    "Pennsylvania", "Ohio", "Georgia", "North Carolina", "Michigan",
    "New Jersey", "Virginia", "Washington", "Arizona", "Massachusetts",
]


def generate_orders(n: int = NUM_ORDERS) -> list[dict]:
    """Generate n fake e-commerce orders."""
    orders = []
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 12, 31)

    for i in range(1, n + 1):
        category = random.choice(list(PRODUCTS.keys()))
        product_name, min_price, max_price = random.choice(PRODUCTS[category])
        unit_price = round(random.uniform(min_price, max_price), 2)
        quantity = random.randint(1, 5)
        total_amount = round(unit_price * quantity, 2)
        order_date = start_date + timedelta(
            days=random.randint(0, (end_date - start_date).days)
        )
        state = random.choice(US_STATES)

        orders.append({
            "order_id": f"ORD-{i:05d}",
            "customer_name": fake.name(),
            "email": fake.email(),
            "product": product_name,
            "category": category,
            "quantity": quantity,
            "unit_price": unit_price,
            "total_amount": total_amount,
            "order_date": order_date.strftime("%Y-%m-%d"),
            "status": random.choices(STATUSES, STATUS_WEIGHTS)[0],
            "payment_method": random.choice(PAYMENT_METHODS),
            "shipping_city": fake.city(),
            "shipping_state": state,
        })

    return orders


def save_csv(orders: list[dict]) -> None:
    """Save orders to CSV."""
    if not orders:
        return
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=orders[0].keys())
        writer.writeheader()
        writer.writerows(orders)
    print(f"✅ Saved {len(orders)} orders to {CSV_PATH}")


def load_into_sqlite(orders: list[dict]) -> None:
    """Create SQLite database and insert orders."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS orders")
    cursor.execute("""
        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            customer_name TEXT,
            email TEXT,
            product TEXT,
            category TEXT,
            quantity INTEGER,
            unit_price REAL,
            total_amount REAL,
            order_date TEXT,
            status TEXT,
            payment_method TEXT,
            shipping_city TEXT,
            shipping_state TEXT
        )
    """)

    cursor.executemany("""
        INSERT INTO orders VALUES (
            :order_id, :customer_name, :email, :product, :category,
            :quantity, :unit_price, :total_amount, :order_date,
            :status, :payment_method, :shipping_city, :shipping_state
        )
    """, orders)

    conn.commit()

    # Verify
    count = cursor.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    print(f"✅ Loaded {count} orders into SQLite at {DB_PATH}")

    conn.close()


def setup_database() -> None:
    """Generate data, save CSV, and load into SQLite."""
    orders = generate_orders()
    save_csv(orders)
    load_into_sqlite(orders)


if __name__ == "__main__":
    setup_database()
