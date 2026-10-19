import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import re

def reconstruct_executable_query(digest_text: str) -> str:
    """
    Transforms a normalized DIGEST_TEXT back into an executable SQL string
    by substituting parameter placeholders with representative values.
    """
    if not digest_text:
        return ""

    sql = digest_text.strip()

    # 1. Replace IN (...) parameter lists
    sql = re.sub(r'IN\s*\(\s*\?\s*,\s*\.\.\.\s*\)', 'IN (1, 2, 3)', sql, flags=re.IGNORECASE)
    sql = re.sub(r'IN\s*\(\s*\?\s*\)', 'IN (1)', sql, flags=re.IGNORECASE)

    # 2. Replace LIKE ? placeholders
    sql = re.sub(r'LIKE\s+\?', "LIKE '%test%'", sql, flags=re.IGNORECASE)

    # 3. Replace YEAR(...) = ? or DATE(...) = ?
    sql = re.sub(r'(YEAR\s*\([^)]+\)\s*=\s*)\?', r'\g<1>2025', sql, flags=re.IGNORECASE)

    # 4. Handle LIMIT ? OFFSET ? or LIMIT ?, ?
    sql = re.sub(r'LIMIT\s+\?\s+OFFSET\s+\?', 'LIMIT 50 OFFSET 100', sql, flags=re.IGNORECASE)
    sql = re.sub(r'LIMIT\s+\?,\s*\?', 'LIMIT 100, 50', sql, flags=re.IGNORECASE)
    sql = re.sub(r'LIMIT\s+\?', 'LIMIT 50', sql, flags=re.IGNORECASE)

    # 5. Replace equality/comparison ? with safe generic defaults
    # Numeric / string comparisons: col = ? -> col = 1 or col = 'SAMPLE'
    # We test with '1' which works cleanly for IDs, numbers, and MySQL loose type coercion
    sql = re.sub(r'=\s*\?', "= '1'", sql)
    sql = re.sub(r'>=\s*\?', ">= '1'", sql)
    sql = re.sub(r'<=\s*\?', "<= '1'", sql)
    sql = re.sub(r'>\s*\?', "> '1'", sql)
    sql = re.sub(r'<\s*\?', "< '1'", sql)

    # 6. Any remaining isolated '?' replaced with '1'
    sql = re.sub(r'\?', "'1'", sql)

    return sql

if __name__ == "__main__":
    sample = "SELECT * FROM `orders` WHERE YEAR ( `created_at` ) = ? AND `order_status` = ?"
    print("Original:   ", sample)
    print("Reconstructed:", reconstruct_executable_query(sample))