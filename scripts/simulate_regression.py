import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import time
import random
from config.database import get_connection

def simulate_regressed_workload(iterations=30):
    """
    Simulates a regressed query by running a Cartesian-like lookup
    that slows down customer fetching.
    """
    conn = get_connection(include_db=True)
    cursor = conn.cursor()
    print("Simulating performance regression on customers lookup...")

    regressed_query = """
    SELECT c1.id, c1.full_name, c2.country 
    FROM customers c1 
    JOIN customers c2 ON c1.country = c2.country 
    WHERE c1.id = %s
    LIMIT 200;
    """

    for i in range(1, iterations + 1):
        cust_id = random.randint(1, 1000)
        start_t = time.perf_counter()
        cursor.execute(regressed_query, (cust_id,))
        cursor.fetchall()
        elapsed_ms = (time.perf_counter() - start_t) * 1000

        if i % 5 == 0:
            print(f"[{i}/{iterations}] Regressed query took: {elapsed_ms:.2f}ms")
        time.sleep(0.2)

    cursor.close()
    conn.close()
    print("Regression simulation workload finished.")

if __name__ == "__main__":
    simulate_regressed_workload()