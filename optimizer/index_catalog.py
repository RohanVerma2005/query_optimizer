import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from typing import Dict, List
from config.database import get_connection

class IndexCatalog:
    def __init__(self, schema_name="qpa_workload"):
        self.schema_name = schema_name

    def get_existing_indexes(self, table_name: str) -> Dict[str, List[str]]:
        """
        Returns a mapping: index_name -> [col1, col2, ...] in key sequence order.
        """
        conn = get_connection(include_db=False)
        cursor = conn.cursor(dictionary=True)
        query = """
        SELECT INDEX_NAME, COLUMN_NAME, SEQ_IN_INDEX
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        ORDER BY INDEX_NAME, SEQ_IN_INDEX;
        """
        cursor.execute(query, (self.schema_name, table_name))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        indexes: Dict[str, List[str]] = {}
        for r in rows:
            idx = r['INDEX_NAME']
            col = r['COLUMN_NAME'].lower()
            if idx not in indexes:
                indexes[idx] = []
            indexes[idx].append(col)
        return indexes

    def is_covered_by_existing_index(self, table_name: str, candidate_cols: List[str]) -> bool:
        """
        Checks if candidate_cols is already covered by a left-prefix of an existing index.
        """
        existing = self.get_existing_indexes(table_name)
        for idx_name, cols in existing.items():
            # If the candidate columns match the leading prefix of an existing index
            if cols[:len(candidate_cols)] == candidate_cols:
                return True
        return False

    def get_unused_indexes(self) -> List[dict]:
        """
        Fetches indexes that have never been used for lookups using MySQL's sys schema.
        """
        conn = get_connection(include_db=False)
        cursor = conn.cursor(dictionary=True)
        query = """
        SELECT object_schema, object_name AS table_name, index_name
        FROM sys.schema_unused_indexes
        WHERE object_schema = %s AND index_name != 'PRIMARY';
        """
        try:
            cursor.execute(query, (self.schema_name,))
            return cursor.fetchall()
        except Exception:
            return []
        finally:
            cursor.close()
            conn.close()