import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import time
import random
from config.database import get_connection
# ... rest of workload_generator.py

FAST_QUERIES = [
    ("SELECT * FROM customers WHERE id = %s", lambda: (random.randint(1, 10000),)),
    ("SELECT * FROM products WHERE id = %s", lambda: (random.randint(1, 10000),)),
    ("SELECT id, name FROM categories WHERE id = %s", lambda: (random.randint(1, 500),)),
]

SLOW_QUERIES = [
    # 1. Full table scan with non-SARGable function
    (
        "SELECT * FROM orders WHERE YEAR(created_at) = 2025 AND order_status = 'PENDING'",
        lambda: ()
    ),
    # 2. Leading wildcard text search on unindexed column
    (
        "SELECT * FROM products WHERE description LIKE '%quality%'",
        lambda: ()
    ),
    # 3. Unindexed 3-way join with sort
    (
        """
        SELECT c.full_name, o.total_amount, oi.quantity, p.title
        FROM customers c
        JOIN orders o ON c.id = o.customer_id
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        WHERE o.order_status = 'COMPLETED'
        ORDER BY o.total_amount DESC
        LIMIT 50
        """,
        lambda: ()
    ),
    # 4. Deep pagination offset with filesort
    (
        "SELECT * FROM customers ORDER BY country, created_at LIMIT 50 OFFSET 8000",
        lambda: ()
    ),
    # 5. Missing index equality aggregation
    (
        "SELECT customer_id, COUNT(*), AVG(total_amount) FROM orders GROUP BY customer_id HAVING COUNT(*) > 2",
        lambda: ()
    )
]

def run_workload(iterations=200):
    conn = get_connection(include_db=True)
    cursor = conn.cursor()
    print(f"Starting workload generator ({iterations} iterations)...")

    for i in range(1, iterations + 1):
        if random.random() < 0.8:
            sql, param_fn = random.choice(FAST_QUERIES)
        else:
            sql, param_fn = random.choice(SLOW_QUERIES)

        params = param_fn()
        try:
            start_t = time.perf_counter()
            cursor.execute(sql, params)
            cursor.fetchall()
            elapsed_ms = (time.perf_counter() - start_t) * 1000
            if i % 25 == 0:
                print(f"[{i}/{iterations}] Executed query in {elapsed_ms:.2f}ms")
        except Exception as e:
            print(f"Error on query: {e}")

        time.sleep(0.05)

    cursor.close()
    conn.close()
    print("Workload iteration cycle complete.")

if __name__ == "__main__":
    run_workload(iterations=300)