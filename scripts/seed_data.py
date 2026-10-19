import sys
from pathlib import Path

# Ensure project root is in sys.path regardless of how script is executed
sys.path.append(str(Path(__file__).resolve().parent.parent))

import random
from datetime import datetime, timedelta
from faker import Faker
from config.database import get_connection

fake = Faker()
Faker.seed(42)
random.seed(42)

TOTAL_ROWS = 10000
BATCH_SIZE = 2000

def seed_categories(cursor):
    print("Seeding categories (500 rows)...")
    cursor.execute("TRUNCATE TABLE categories")
    cats = [(fake.unique.word().capitalize() + f" {i}", fake.sentence()[:250]) for i in range(500)]
    cursor.executemany("INSERT INTO categories (name, description) VALUES (%s, %s)", cats)

def seed_customers(cursor):
    print("Seeding customers (10,000 rows)...")
    cursor.execute("TRUNCATE TABLE customers")
    base_date = datetime.now() - timedelta(days=730)
    for _ in range(0, TOTAL_ROWS, BATCH_SIZE):
        batch = []
        for _ in range(BATCH_SIZE):
            created_at = base_date + timedelta(seconds=random.randint(0, 730 * 86400))
            batch.append((
                fake.name()[:100],
                fake.email()[:150],
                fake.phone_number()[:50],
                fake.country()[:100],  # truncated to prevent column overflow
                created_at.strftime('%Y-%m-%d %H:%M:%S')
            ))
        cursor.executemany(
            "INSERT INTO customers (full_name, email, phone, country, created_at) VALUES (%s, %s, %s, %s, %s)",
            batch
        )

def seed_products(cursor):
    print("Seeding products (10,000 rows)...")
    cursor.execute("TRUNCATE TABLE products")
    base_date = datetime.now() - timedelta(days=730)
    for start in range(0, TOTAL_ROWS, BATCH_SIZE):
        batch = []
        for i in range(BATCH_SIZE):
            created_at = base_date + timedelta(seconds=random.randint(0, 730 * 86400))
            batch.append((
                random.randint(1, 500),
                fake.catch_phrase()[:150],
                f"SKU-{start + i}-{random.randint(100, 999)}",
                round(random.uniform(5.0, 500.0), 2),
                random.randint(0, 1000),
                fake.paragraph(nb_sentences=3),
                created_at.strftime('%Y-%m-%d %H:%M:%S')
            ))
        cursor.executemany(
            "INSERT INTO products (category_id, title, sku, price, stock, description, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            batch
        )

def seed_orders(cursor):
    print("Seeding orders (10,000 rows)...")
    cursor.execute("TRUNCATE TABLE orders")
    statuses = ['PENDING', 'PROCESSING', 'COMPLETED', 'CANCELLED', 'REFUNDED']
    base_date = datetime.now() - timedelta(days=365)
    for _ in range(0, TOTAL_ROWS, BATCH_SIZE):
        batch = []
        for _ in range(BATCH_SIZE):
            created_at = base_date + timedelta(seconds=random.randint(0, 365 * 86400))
            batch.append((
                random.randint(1, TOTAL_ROWS),
                random.choice(statuses),
                round(random.uniform(10.0, 2000.0), 2),
                fake.address().replace('\n', ', ')[:250],
                created_at.strftime('%Y-%m-%d %H:%M:%S')
            ))
        cursor.executemany(
            "INSERT INTO orders (customer_id, order_status, total_amount, shipping_address, created_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            batch
        )

def seed_order_items(cursor):
    print("Seeding order_items (10,000 rows)...")
    cursor.execute("TRUNCATE TABLE order_items")
    for _ in range(0, TOTAL_ROWS, BATCH_SIZE):
        batch = []
        for _ in range(BATCH_SIZE):
            batch.append((
                random.randint(1, TOTAL_ROWS),
                random.randint(1, TOTAL_ROWS),
                random.randint(1, 5),
                round(random.uniform(5.0, 300.0), 2)
            ))
        cursor.executemany(
            "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
            batch
        )

def seed_reviews(cursor):
    print("Seeding reviews (10,000 rows)...")
    cursor.execute("TRUNCATE TABLE reviews")
    base_date = datetime.now() - timedelta(days=365)
    for _ in range(0, TOTAL_ROWS, BATCH_SIZE):
        batch = []
        for _ in range(BATCH_SIZE):
            created_at = base_date + timedelta(seconds=random.randint(0, 365 * 86400))
            batch.append((
                random.randint(1, TOTAL_ROWS),
                random.randint(1, TOTAL_ROWS),
                random.randint(1, 5),
                fake.sentence(nb_words=12),
                created_at.strftime('%Y-%m-%d %H:%M:%S')
            ))
        cursor.executemany(
            "INSERT INTO reviews (product_id, customer_id, rating, review_text, created_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            batch
        )

if __name__ == "__main__":
    conn = get_connection(include_db=True)
    cursor = conn.cursor()
    try:
        seed_categories(cursor)
        seed_customers(cursor)
        seed_products(cursor)
        seed_orders(cursor)
        seed_order_items(cursor)
        seed_reviews(cursor)
        print("Data seeding completed successfully!")
    finally:
        cursor.close()
        conn.close()