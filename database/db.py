import sys
import atexit
from psycopg_pool import ConnectionPool
from config.settings import get_settings

# Load settings and database URL
settings = get_settings()
db_url = settings.db_url



class Database:
    def __init__(self, db_url: str, min_size: int = 1, max_size: int = 7, timeout: int = 10):
        try:
            self.pool = ConnectionPool(
                conninfo=db_url,
                min_size=min_size,
                max_size=max_size,
                timeout=timeout,
            )
        except Exception as e:
            print(f"Error initializing database connection pool: {e}")
            sys.exit(1)

    def execute(self, query: str, params: tuple = None, fetch: str = None, commit: bool = False):
        try:
            # psycopg_pool idiom: use context manager
            with self.pool.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)

                    result = None
                    if fetch == "one":
                        result = cursor.fetchone()
                    elif fetch == "all":
                        result = cursor.fetchall()

                    if commit:
                        conn.commit()
                    else:
                        # If not committing, rollback ensures no dangling transaction
                        conn.rollback()

                    return result
        except Exception as e:
            print(f"Error executing query: {e}")
            return None

    def close_pool(self):
        try:
            self.pool.close()
        except Exception as e:
            print(f"Error closing connection pool: {e}")


# Create global database object
db_obj = Database(db_url)

# Ensure pool closes cleanly on exit
atexit.register(db_obj.close_pool)
