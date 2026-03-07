# /backend/app/core/connection_factory.py
import os
import psycopg2
from psycopg2 import sql
from contextlib import contextmanager
from dotenv import load_dotenv

# --- THE KEY TO THE CASTLE: LOADING THE .env FILE ---
# This part scans your folder for the hidden '.env' file where your Supabase password lives.
# We make sure it finds the file even if you run the code from different folders.
env_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env')
if not os.path.exists(env_path):
    env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')

load_dotenv(dotenv_path=env_path)

class ConnectionFactory:
    """
    HOW THIS WORKS: 
    Think of this class as a 'Switchboard Operator'. 
    Whenever the code needs to talk to the database, it asks this class for a 'tunnel' (connection).
    """
    
    @staticmethod
    def _get_base_connection():
        """
        THE RAW TUNNEL:
        This opens a basic connection to Supabase using the credentials in your .env.
        It's like dialing the main building's phone number.
        """
        return psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS")
        )

    @classmethod
    @contextmanager
    def get_tenant_connection(cls, tenant_id: str):
        """
        THE PRIVATE OFFICE TUNNEL:
        This is the most important part! It doesn't just connect to the database; 
        it immediately enters a specific 'Schema' (like a private room for one company).
        
        If you are 'Company_A', this makes sure you ONLY see 'Company_A' data.
        """
        conn = cls._get_base_connection()
        try:
            with conn.cursor() as cursor:
                # This 'SET search_path' command tells Postgres: 
                # "From now on, only look inside this company's private folder!"
                query = sql.SQL("SET search_path TO {schema}, public").format(
                    schema=sql.Identifier(tenant_id)
                )
                cursor.execute(query)
            yield conn
        finally:
            # We always 'hang up' the phone when we're done to save resources.
            conn.close()

    @classmethod
    @contextmanager
    def get_admin_connection(cls):
        """
        THE MASTER TUNNEL (ADMIN ONLY):
        This connects you to the 'Public' schema where the main list of all companies lives.
        We use this when someone signs up for the first time.
        """
        conn = cls._get_base_connection()
        try:
            yield conn
        finally:
            conn.close()
