import sys
import psycopg
from psycopg_pool import ConnectionPool
import atexit
from config.settings import db_url


class Database:
    def __init__(self, db_url: str, min_size: int = 1, max_size: int = 7, timeout: int = 10):
        def _check_connection(conn):

            try:

                conn.execute("SELECT 1")
                return True
            except psycopg.OperationalError:
                return False
        try:
            self.pool = ConnectionPool(
                conninfo=db_url,
                min_size=min_size,
                max_size=max_size,
                timeout=timeout,
                check = _check_connection,
                kwargs={"autocommit": True},
            )
        except Exception as e:
            print(f"Error initializing database connection pool: {e}")
            sys.exit(1)

    def get_conn(self):
        try:
            return self.pool.getconn()
        except Exception as e:
            print(f"Error getting connection from pool: {e}")
            return None

    def release_conn(self, conn):
        if conn:
            try:
                self.pool.putconn(conn)
            except Exception as e:
                print(f"Error releasing connection back to pool: {e}")

    def close_pool(self):
        try:
            self.pool.close()
        except Exception as e:
            print(f"Error closing connection pool: {e}")

    def execute(self, query: str, params: tuple = None, fetch: str = None, commit: bool = False):
        conn = None
        try:
            conn = self.get_conn()
            with conn.cursor() as cursor:
                cursor.execute(query, params)

                result = None
                if fetch == "one":
                    result = cursor.fetchone()
                elif fetch == "all":
                    result = cursor.fetchall()

                if commit:
                    conn.commit()

                return result

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error executing query: {e}")
            return None

        finally:
            self.release_conn(conn)


db_obj = Database(db_url)
atexit.register(db_obj.close_pool)