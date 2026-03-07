import os
import psycopg2
from dotenv import load_dotenv

# 1. Load the variables from the .env file
load_dotenv()

def get_connection():
    """Establish and return a connection to the PostgreSQL database."""
    try:
        # 2. Pull credentials from environment variables
        connection = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS")
        )
        print("Successfully connected to the database!")
        return connection
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None
    
#. Breakdown: database/connections.py (The Logic)
# Import os and dotenv: These allow Python to interact with your computer's operating system and read the hidden .env file.

# load_dotenv(): This command scans your folder for the .env file and "unlocks" the data inside.

# os.getenv(): This pulls the specific "Value" (like your password) using the "Key" (like DB_PASS).

# psycopg2.connect(): This is the engine that uses those values to open a secure "tunnel" to the university server at 10.100.71.21.

# return connection: This sends that active "tunnel" back to whoever asked for it (in this case, main.py).