import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic_ai import Agent
from google.genai import Client
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
import os
from dotenv import load_dotenv
import logfire

logfire.configure()  
logfire.instrument_pydantic_ai()

load_dotenv()
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
USER_ID = os.getenv('USER_ID')

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
# cur.execute(SQL_get_tables_with_schema)
# rows = cur.fetchall()

# tables_schema = transform_to_tables_schema(rows)
# print(tables_schema)

# ------------ MODEL ----------------------

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
model_options = ['gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemma-3-27b-it']

client = Client(
    api_key=GOOGLE_API_KEY,
)
provider = GoogleProvider(client=client)
model = GoogleModel(model_options[0], provider=provider)

INSTRUCTIONS = """
You are an expert in HTML, CSS, and JavaScript. You will build small front visualizations based on requests from the user.
The user will include its request in the <user> tag. Design data, such as viewport size, will be included in the <design> tag if provided.
You must retrieve the data from the userbase to create the visualizations.
You will output code inside <output> tags.
"""

# INSTRUCTIONS = """
# You are an expert in database management. You will help the user with his requests
# """

designer = Agent(
    model,
    instructions=INSTRUCTIONS
)

@designer.instructions
def get_user_id() -> str:
    return f"The user id is: {USER_ID}"

@designer.tool_plain
def get_database_schema() -> dict:
    """Returns the Schema of the database"""
    cur.execute(SQL_get_tables_with_schema)
    rows = cur.fetchall()
    tables_schema = transform_to_tables_schema(rows)
    return tables_schema

@designer.tool_plain
def run_sql_query(query: str) -> dict:
    """Runs a SQL query and returns the result. If there is an error it returns the error message so you can try again"""
    try:    
        cur.execute(query)
        rows = cur.fetchall()
        return rows
    except Exception as e:
        return str(e)


result = designer.run_sync(
    "Make a pie chart of the activities I have done between 25/08/2025 - 01/09/2025"
)

with open("outputs/dashboard_designer.html", "w") as f:
    f.write(result.output)

print(result.output)

cur.close()
conn.close()


