import json
import os
import csv
from datetime import date, datetime
from decimal import Decimal
import psycopg2.extras
from app.core.connection_factory import ConnectionFactory
import services.query_engine as query_engine

class EMSJsonEncoder(json.JSONEncoder):
    """
    The Master Packer:
    Handles types that standard JSON can't understand, like Decimals and Dates.
    """
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super(EMSJsonEncoder, self).default(obj)

def get_export_folder(tenant_id, prefix="Export"):
    """Creates a standardized, safe folder for exports in the root directory."""
    base_dir = "d:/DAIICT/exports"
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    folder_name = f"{tenant_id}_{prefix}_{timestamp}"
    full_path = os.path.join(base_dir, folder_name)
    
    if not os.path.exists(full_path):
        os.makedirs(full_path)
    return os.path.abspath(full_path)

def clean_data(obj):
    """Recursively converts Decimals and Dates to JSON-safe types."""
    if isinstance(obj, list):
        return [clean_data(item) for item in obj]
    if isinstance(obj, dict):
        return {k: clean_data(v) for k, v in obj.items()}
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return obj

def export_company_data_json():
    """
    THE SYSTEM SNAPSHOT:
    Gathers all records and packs them into a JSON file for machine portability.
    Stored inside a dedicated folder for better organization.
    """
    tenant_id = query_engine.CURRENT_TENANT_ID
    if not tenant_id:
        return False, "Error: No active session (Tenant ID missing)."

    try:
        # Create folder
        abs_folder_path = get_export_folder(tenant_id, "Snapshot")
        
        data_package = {
            "metadata": {
                "tenant_id": tenant_id,
                "export_date": datetime.now().isoformat(),
                "system": "EMS Multi-Tenant Professional"
            },
            "records": {}
        }

        tables = ["employee", "department", "project", "works_on", "dependent", "dept_locations", "audit_log"]

        with ConnectionFactory.get_tenant_connection(tenant_id) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                for table in tables:
                    cur.execute(f"SELECT * FROM {table};")
                    rows = cur.fetchall()
                    # We use dict(row) to convert DictRow to standard dict, then clean it
                    data_package["records"][table] = [clean_data(dict(row)) for row in rows]

        filename = f"system_snapshot_{date.today()}.json"
        filepath = os.path.join(abs_folder_path, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_package, f, indent=4, cls=EMSJsonEncoder)

        return True, filepath

    except Exception as e:
        return False, f"JSON Export failed: {str(e)}"

def export_company_data_csv():
    """
    THE HUMAN PORTABLE EXPORT:
    Generates an organized folder containing 7 CSV files for Excel/Spreadsheet use.
    """
    tenant_id = query_engine.CURRENT_TENANT_ID
    if not tenant_id:
        return False, "Error: No active session (Tenant ID missing)."

    try:
        # Create folder
        abs_folder_path = get_export_folder(tenant_id, "Excel_Bundle")

        tables = ["employee", "department", "project", "works_on", "dependent", "dept_locations", "audit_log"]

        with ConnectionFactory.get_tenant_connection(tenant_id) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                for table in tables:
                    cur.execute(f"SELECT * FROM {table};")
                    rows = cur.fetchall()
                    
                    if not rows: continue
                    
                    file_path = os.path.join(abs_folder_path, f"{table}.csv")
                    headers = rows[0].keys()
                    
                    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=headers)
                        writer.writeheader()
                        for row in rows:
                            # CSV needs flat values, clean_data handles this
                            writer.writerow(clean_data(dict(row)))

        return True, abs_folder_path

    except Exception as e:
        return False, f"CSV Export failed: {str(e)}"
