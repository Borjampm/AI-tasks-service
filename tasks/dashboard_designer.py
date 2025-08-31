import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

# Replace with your Supabase credentials
conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

cur = conn.cursor()

SQL_get_tables_with_schema = """
SELECT 
    t.table_name,
    c.column_name,
    c.data_type
FROM information_schema.tables t
JOIN information_schema.columns c 
    ON t.table_name = c.table_name 
    AND t.table_schema = c.table_schema
WHERE t.table_schema = 'public' 
    AND t.table_type = 'BASE TABLE'
ORDER BY t.table_name, c.ordinal_position;
"""

def transform_to_tables_schema(rows):
    tables_schema = {}
    for row in rows:
        if row[0] not in tables_schema:
            tables_schema[row[0]] = {}
        tables_schema[row[0]][row[1]] = row[2]
    return tables_schema

# Run raw SQL
cur.execute(SQL_get_tables_with_schema)
rows = cur.fetchall()

tables_schema = transform_to_tables_schema(rows)
print(tables_schema)


cur.close()
conn.close()
