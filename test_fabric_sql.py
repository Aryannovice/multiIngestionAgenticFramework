import pyodbc

server = "emmzwhxktbte7hmtroidfloccm-jydrooom3uoednoqafjz2k7b3e.datawarehouse.fabric.microsoft.com"
database = "multiIngestionLakehouse"

conn_str = f"""
DRIVER={{ODBC Driver 18 for SQL Server}};
SERVER={server};
DATABASE={database};
Authentication=ActiveDirectoryInteractive;
Encrypt=yes;
TrustServerCertificate=no;
"""

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

cursor.execute("SELECT TOP 5 * FROM startup_funding")

for row in cursor.fetchall():
    print(row)
