import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "qpa_workload"),
    "autocommit": True
}

def get_connection(include_db=True):
    config = DB_CONFIG.copy()
    if not include_db:
        config.pop("database", None)
    return mysql.connector.connect(**config)