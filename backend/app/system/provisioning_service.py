# /backend/app/system/provisioning_service.py
# ==================================================================================================
# PROVISIONING SERVICE — Updated to include methods called by both cli_main.py and main.py
#
# ADDED vs original:
#   - provision_new_company now accepts optional email parameter
#   - change_company_password()        ← called by cli_main.py option 3
#   - update_company_email()           ← called by cli_main.py option 4
#   - get_company_email_by_tenant_id() ← called by cli_main.py export flow
#
# NOTE: The public.tenants table needs an email column.
#       Run this SQL once in Supabase SQL editor:
#       ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS email VARCHAR(255);
# ==================================================================================================

import os
import psycopg2
from psycopg2 import sql
from app.core.connection_factory import ConnectionFactory
from app.core.security import hash_password, verify_password


def generate_tenant_slug(company_name: str) -> str:
    """
    Makes a 'Safe' folder name for the database.
    Example: 'My Company!' becomes 'comp_my_company'
    """
    clean_name = "".join(e for e in company_name if e.isalnum() or e.isspace()).lower()
    return f"comp_{clean_name.replace(' ', '_')}"


class ProvisioningService:
    """
    THE BUILDER & ACCOUNT MANAGER:
    Handles all company lifecycle operations — creation, password changes,
    email updates, and deletion.
    """

    @staticmethod
    def provision_new_company(company_name: str, admin_password: str, email: str = None):
        """
        THE AUTO-CREATOR:
        1. Makes a safe schema name for the company.
        2. Hashes the password.
        3. Creates a private Schema in the database.
        4. Runs the template SQL to build all 6 tables + audit triggers.

        Now accepts an optional email address.
        """
        try:
            tenant_id  = generate_tenant_slug(company_name)
            hashed_pwd = hash_password(admin_password)

            # STEP A: Register the company in the Master Registry (public.tenants)
            with ConnectionFactory.get_admin_connection() as conn:
                with conn.cursor() as cursor:
                    # Check if the name is already taken
                    cursor.execute(
                        "SELECT 1 FROM public.tenants WHERE company_name = %s",
                        (company_name,)
                    )
                    if cursor.fetchone():
                        return False, f"Sorry, the company name '{company_name}' is already taken."

                    # Save the company details — include email if provided
                    register_query = """
                    INSERT INTO public.tenants (company_name, tenant_id, hashed_password, email)
                    VALUES (%s, %s, %s, %s);
                    """
                    cursor.execute(register_query, (company_name, tenant_id, hashed_pwd, email))

                    # Create the actual private schema
                    cursor.execute(
                        sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(tenant_id))
                    )
                conn.commit()

            # STEP B: Put furniture in the new room (Creating all 6 tables + triggers)
            with ConnectionFactory.get_tenant_connection(tenant_id) as conn:
                with conn.cursor() as cursor:
                    # Find the tenant template SQL file
                    template_path = os.path.join(
                        os.path.dirname(__file__), '..', '..', 'app', 'database', 'tenant_template.sql'
                    )
                    if not os.path.exists(template_path):
                        template_path = os.path.join(
                            os.path.dirname(__file__), '..', 'database', 'tenant_template.sql'
                        )

                    with open(template_path, 'r') as f:
                        template_sql = f.read()

                    cursor.execute(template_sql)
                conn.commit()

            return True, tenant_id

        except Exception as e:
            return False, str(e)

    @staticmethod
    def change_company_password(company_name: str, current_password: str,
                                 new_password: str, confirm_password: str):
        """
        Changes the company's login password.
        Requires the current password for security verification.
        Also called by cli_main.py option 3.
        """
        if new_password != confirm_password:
            return False, "New passwords do not match."

        if len(new_password) < 6:
            return False, "New password must be at least 6 characters."

        try:
            with ConnectionFactory.get_admin_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT tenant_id, hashed_password FROM public.tenants WHERE company_name = %s",
                        (company_name,)
                    )
                    row = cursor.fetchone()

                if not row:
                    return False, f"Company '{company_name}' not found."

                tenant_id, hashed_pwd = row

                if not verify_password(current_password, hashed_pwd):
                    return False, "Current password is incorrect."

                new_hash = hash_password(new_password)

                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE public.tenants SET hashed_password = %s WHERE company_name = %s",
                        (new_hash, company_name)
                    )
                conn.commit()

            return True, "Password updated successfully."

        except Exception as e:
            return False, str(e)

    @staticmethod
    def update_company_email(company_name: str, password: str, new_email: str):
        """
        Adds or updates the company's registered email address.
        Requires password for verification.
        Also called by cli_main.py option 4.
        """
        if not new_email or "@" not in new_email:
            return False, "Please provide a valid email address."

        try:
            with ConnectionFactory.get_admin_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT tenant_id, hashed_password FROM public.tenants WHERE company_name = %s",
                        (company_name,)
                    )
                    row = cursor.fetchone()

                if not row:
                    return False, f"Company '{company_name}' not found."

                _, hashed_pwd = row

                if not verify_password(password, hashed_pwd):
                    return False, "Password is incorrect."

                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE public.tenants SET email = %s WHERE company_name = %s",
                        (new_email.strip(), company_name)
                    )
                conn.commit()

            return True, f"Email updated to {new_email.strip()}."

        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_company_email_by_tenant_id(tenant_id: str):
        """
        Returns (company_name, email) for the given tenant_id.
        Used by cli_main.py export flow before sending the email.
        Returns (False, error_message) if no email is registered.
        """
        try:
            with ConnectionFactory.get_admin_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT company_name, email FROM public.tenants WHERE tenant_id = %s",
                        (tenant_id,)
                    )
                    row = cursor.fetchone()

            if not row:
                return False, "Company not found."

            company_name, email = row
            if not email:
                return False, "No email address registered for this company."

            return True, (company_name, email)

        except Exception as e:
            return False, str(e)

    @staticmethod
    def delete_company_space(company_name: str, password: str):
        """
        THE WRECKING BALL:
        Permanently deletes every piece of data for a company.
        A password is MANDATORY.
        """
        try:
            with ConnectionFactory.get_admin_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT tenant_id, hashed_password FROM public.tenants WHERE company_name = %s",
                        (company_name,)
                    )
                    row = cursor.fetchone()

                if not row:
                    return False, "We couldn't find a company with that name."

                tenant_id, hashed_pwd = row
                if not verify_password(password, hashed_pwd):
                    return False, "The password was incorrect. We won't delete anything."

                with conn.cursor() as cursor:
                    cursor.execute(
                        sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(tenant_id))
                    )
                    cursor.execute(
                        "DELETE FROM public.tenants WHERE company_name = %s",
                        (company_name,)
                    )
                conn.commit()

            return True, f"Success! '{company_name}' and all its data have been permanently deleted."

        except Exception as e:
            return False, str(e)

    @staticmethod
    def force_delete_test_company(company_name: str):
        """
        [MAINTENANCE ONLY]:
        Force-deletes test companies only. Blocked for real company names.
        """
        test_prefixes = ["AlphaCorp_", "BetaCorp_", "CloudTestCorp_", "TEST_"]
        is_test       = any(company_name.startswith(p) for p in test_prefixes)

        if not is_test:
            return False, "SECURITY ALERT: Force-delete is forbidden for real companies."

        try:
            with ConnectionFactory.get_admin_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT tenant_id FROM public.tenants WHERE company_name = %s",
                        (company_name,)
                    )
                    row = cursor.fetchone()
                    if not row:
                        return False, "Test company not found."

                    tenant_id = row[0]
                    cursor.execute(
                        sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(tenant_id))
                    )
                    cursor.execute(
                        "DELETE FROM public.tenants WHERE company_name = %s",
                        (company_name,)
                    )
                conn.commit()

            return True, f"Admin Purge: '{company_name}' removed successfully."

        except Exception as e:
            return False, str(e)