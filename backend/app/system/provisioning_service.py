# /backend/app/system/provisioning_service.py
import os
import re
import psycopg2
from psycopg2 import sql
from app.core.connection_factory import ConnectionFactory
from app.core.security import hash_password

def generate_tenant_slug(company_name: str) -> str:
    """
    Makes a 'Safe' folder name for the database.
    Example: 'My Company!' becomes 'comp_my_company'
    """
    clean_name = "".join(e for e in company_name if e.isalnum() or e.isspace()).lower()
    return f"comp_{clean_name.replace(' ', '_')}"

def is_valid_email(email: str) -> bool:
    """
    THE EMAIL FORMAT VALIDATOR:
    Checks whether a string looks like a real email address.
    Does NOT send a test email — just checks the pattern.
    Valid examples:   user@gmail.com   admin@company.co.uk   t.30@daiict.ac.in
    Invalid examples: notanemail   @gmail.com   user@   user@.com   user @x.com

    The regex pattern means:
      ^                          = start of string
      [a-zA-Z0-9._%+\-]+        = one or more allowed characters before the @
      @                          = the @ symbol (required)
      [a-zA-Z0-9.\-]+           = one or more allowed characters for the domain name
      \.                         = a dot (required)
      [a-zA-Z]{2,}              = at least 2 letters for the extension (.com, .in, etc.)
      $                          = end of string
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))

class ProvisioningService:
    """
    THE BUILDER:
    This service is responsible for creating a brand new workspace for a company.
    It's like building an apartment and putting the furniture inside.
    """

    @staticmethod
    def provision_new_company(company_name: str,
                               admin_password: str,
                               contact_email: str = None):
        """
        THE AUTO-CREATOR:
        Creates a brand new isolated company workspace.

        New vs original:
        - Accepts an optional contact_email parameter (default None for
          backward compatibility — all existing test scripts still work).
        - If contact_email is provided: validates format, checks uniqueness,
          stores it in the contact_email column of public.tenants.
        - If contact_email is None or blank: stores NULL (no email registered).

        All existing steps (slug, hash, schema creation, template) unchanged.
        Returns (True, tenant_id) on success, (False, error_message) on failure.
        """
        try:
            tenant_id  = generate_tenant_slug(company_name)
            hashed_pwd = hash_password(admin_password)

            # ── Validate and clean the email if provided ─────────────────────
            clean_email = None
            if contact_email and contact_email.strip():
                clean_email = contact_email.strip().lower()
                if not is_valid_email(clean_email):
                    return False, (
                        f"'{clean_email}' is not a valid email address.\n"
                        "Required format: something@something.com\n"
                        "Examples: admin@mycompany.com, hr@corp.co.uk"
                    )

            # ── Register in the master registry ──────────────────────────────
            with ConnectionFactory.get_admin_connection() as conn:
                with conn.cursor() as cursor:

                    # Guard 1: company name must be unique
                    cursor.execute(
                        "SELECT 1 FROM public.tenants "
                        "WHERE company_name = %s",
                        (company_name,)
                    )
                    if cursor.fetchone():
                        return False, (
                            f"Sorry, the company name '{company_name}' "
                            f"is already taken."
                        )

                    # Guard 2: email must be unique (only check if provided)
                    if clean_email:
                        cursor.execute(
                            "SELECT company_name FROM public.tenants "
                            "WHERE contact_email = %s",
                            (clean_email,)
                        )
                        existing = cursor.fetchone()
                        if existing:
                            return False, (
                                f"The email '{clean_email}' is already "
                                f"registered to company: '{existing[0]}'.\n"
                                "Each company must use a unique email address."
                            )

                    # Insert with or without email
                    if clean_email:
                        cursor.execute(
                            """
                            INSERT INTO public.tenants
                                (company_name, tenant_id,
                                 hashed_password, contact_email)
                            VALUES (%s, %s, %s, %s);
                            """,
                            (company_name, tenant_id, hashed_pwd, clean_email)
                        )
                    else:
                        cursor.execute(
                            """
                            INSERT INTO public.tenants
                                (company_name, tenant_id, hashed_password)
                            VALUES (%s, %s, %s);
                            """,
                            (company_name, tenant_id, hashed_pwd)
                        )

                    # Create the private schema
                    cursor.execute(
                        sql.SQL("CREATE SCHEMA {}").format(
                            sql.Identifier(tenant_id))
                    )
                conn.commit()

            # ── Build tables in the new schema ───────────────────────────────
            with ConnectionFactory.get_tenant_connection(tenant_id) as conn:
                with conn.cursor() as cursor:
                    template_path = os.path.join(
                        os.path.dirname(__file__),
                        '..', '..', 'app', 'database', 'tenant_template.sql'
                    )
                    if not os.path.exists(template_path):
                        template_path = os.path.join(
                            os.path.dirname(__file__),
                            '..', 'database', 'tenant_template.sql'
                        )
                    with open(template_path, 'r') as f:
                        template_sql = f.read()
                    cursor.execute(template_sql)
                conn.commit()

            return True, tenant_id

        except Exception as e:
            return False, str(e)

    @staticmethod
    def delete_company_space(company_name: str, password: str):
        """
        THE WRECKING BALL:
        This permanently deletes every single piece of data for a company.
        A password is MANDATORY for all real companies.
        """
        from app.core.security import verify_password
        try:
            with ConnectionFactory.get_admin_connection() as conn:
                with conn.cursor() as cursor:
                    # 1. Check if the company exists and the password matches
                    cursor.execute("SELECT tenant_id, hashed_password FROM public.tenants WHERE company_name = %s", (company_name,))
                    row = cursor.fetchone()
                    if not row:
                        return False, "We couldn't find a company with that name."
                    
                    tenant_id, hashed_pwd = row
                    if not verify_password(password, hashed_pwd):
                        return False, "The password was incorrect. We won't delete anything."

                    # 2. DELETE EVERYTHING (CASCADE means it deletes tables too!)
                    cursor.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(tenant_id)))

                    # 3. Remove them from our 'Master Registry'
                    cursor.execute("DELETE FROM public.tenants WHERE company_name = %s", (company_name,))
                
                conn.commit()
            return True, f"Success! '{company_name}' and all its data have been permanently deleted."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def force_delete_test_company(company_name: str):
        """
        [MAINTENANCE ONLY]:
        Allows force-deleting 'Test' companies only.
        This function WILL FAIL if you try to use it on a real company name.
        """
        # SECURITY WALL: Only allow names with specific test prefixes
        test_prefixes = ["AlphaCorp_", "BetaCorp_", "CloudTestCorp_", "TEST_"]
        is_test = any(company_name.startswith(p) for p in test_prefixes)
        
        if not is_test:
            return False, "SECURITY ALERT: Force-delete is forbidden for real companies. Use the CLI with a password."

        try:
            with ConnectionFactory.get_admin_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT tenant_id FROM public.tenants WHERE company_name = %s", (company_name,))
                    row = cursor.fetchone()
                    if not row: return False, "Test company not found."
                    
                    tenant_id = row[0]
                    cursor.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(tenant_id)))
                    cursor.execute("DELETE FROM public.tenants WHERE company_name = %s", (company_name,))
                conn.commit()
            return True, f"Admin Purge: '{company_name}' removed successfully."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_company_email(company_name: str):
        """
        THE EMAIL LOOKUP:
        Retrieves the registered contact email for a company.
        Used by the CLI export menu to find where to send the file.
        Returns (True, email_string) if found and set.
        Returns (False, error_message) if company not found or email is NULL.
        """
        try:
            with ConnectionFactory.get_admin_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT contact_email FROM public.tenants "
                        "WHERE company_name = %s",
                        (company_name,)
                    )
                    row = cursor.fetchone()
                    if not row:
                        return False, f"Company '{company_name}' not found."
                    if not row[0]:
                        return False, (
                            "This company has no email address on file.\n"
                            "Register one via 'Update Company Email' "
                            "on the landing page."
                        )
                    return True, row[0]
        except Exception as e:
            return False, f"Email lookup failed: {str(e)}"

    @staticmethod
    def get_company_email_by_tenant_id(tenant_id: str):
        """
        THE SESSION-BASED EMAIL LOOKUP:
        Same as get_company_email but looks up by tenant_id (the session variable)
        instead of company_name. Used inside the export menu where we have
        the tenant_id from the active session.
        Returns (True, (company_name, email)) or (False, error_message).
        """
        try:
            with ConnectionFactory.get_admin_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT company_name, contact_email "
                        "FROM public.tenants WHERE tenant_id = %s",
                        (tenant_id,)
                    )
                    row = cursor.fetchone()
                    if not row:
                        return False, "Session company not found."
                    if not row[1]:
                        return False, (
                            "No email address registered for this company."
                        )
                    return True, (row[0], row[1])
        except Exception as e:
            return False, f"Email lookup failed: {str(e)}"

    @staticmethod
    def update_company_email(company_name:    str,
                              current_password: str,
                              new_email:        str):
        """
        THE EMAIL UPDATER:
        Allows a company to add or change their registered contact email.
        Requires the current password for security.
        Validates: non-empty → correct format → not taken by another company.
        Returns (True, success_message) or (False, error_message).
        """
        from app.core.security import verify_password

        # ── Guard: email cannot be empty ─────────────────────────────────────
        if not new_email or not new_email.strip():
            return False, "Email address cannot be empty."

        clean_email = new_email.strip().lower()

        # ── Guard: email must be valid format ────────────────────────────────
        if not is_valid_email(clean_email):
            return False, (
                f"'{clean_email}' is not a valid email address.\n"
                "Format: something@something.com"
            )

        try:
            with ConnectionFactory.get_admin_connection() as conn:
                with conn.cursor() as cursor:

                    # Guard: company must exist + password must be correct
                    cursor.execute(
                        "SELECT tenant_id, hashed_password "
                        "FROM public.tenants WHERE company_name = %s",
                        (company_name,)
                    )
                    row = cursor.fetchone()
                    if not row:
                        return False, f"Company '{company_name}' not found."

                    _, stored_hash = row
                    if not verify_password(current_password, stored_hash):
                        return False, (
                            "Password is incorrect. No changes made."
                        )

                    # Guard: email must not be taken by a DIFFERENT company
                    cursor.execute(
                        "SELECT company_name FROM public.tenants "
                        "WHERE contact_email = %s",
                        (clean_email,)
                    )
                    conflict = cursor.fetchone()
                    if conflict and conflict[0] != company_name:
                        return False, (
                            f"Email '{clean_email}' is already registered "
                            f"to: '{conflict[0]}'."
                        )

                    # Update
                    cursor.execute(
                        "UPDATE public.tenants "
                        "SET contact_email = %s "
                        "WHERE company_name = %s",
                        (clean_email, company_name)
                    )
                conn.commit()

            return True, (
                f"Email updated to '{clean_email}' for '{company_name}'."
            )

        except Exception as e:
            return False, f"Email update failed: {str(e)}"

    @staticmethod
    def change_company_password(company_name: str, current_password: str,
                                new_password: str, confirm_new_password: str):
        """
        THE CREDENTIAL VAULT UPDATER:
        Allows a logged-in company to rotate their access password.
        Enforces three security gates before any change is committed:
          Gate 1 — new_password and confirm_new_password must match.
          Gate 2 — new_password must not be blank.
          Gate 3 — current_password must verify against the stored bcrypt hash.
        On success, hashes the new password and overwrites the registry record.
        Returns (True, success_message) or (False, error_message).
        """
        from app.core.security import verify_password

        # ── Gate 1: Confirmation match ──────────────────────────────────────
        if new_password != confirm_new_password:
            return False, "New passwords do not match. No changes were made."

        # ── Gate 1.5: Cannot reuse current password ─────────────────────────
        if new_password == current_password:
            return False, "New password cannot be the same as the current password."

        # ── Gate 2: Non-empty new password ──────────────────────────────────
        if not new_password or not new_password.strip():
            return False, "New password cannot be empty. No changes were made."

        try:
            with ConnectionFactory.get_admin_connection() as conn:
                with conn.cursor() as cursor:

                    # ── Gate 3a: Company must exist ──────────────────────────
                    cursor.execute(
                        "SELECT tenant_id, hashed_password FROM public.tenants "
                        "WHERE company_name = %s",
                        (company_name,)
                    )
                    row = cursor.fetchone()
                    if not row:
                        return False, f"Company '{company_name}' not found."

                    tenant_id, stored_hash = row

                    # ── Gate 3b: Current password must be correct ────────────
                    if not verify_password(current_password, stored_hash):
                        return False, ("Current password is incorrect. "
                                       "No changes were made.")

                    # ── All gates passed: hash and persist ───────────────────
                    # We need to import hash_password directly here as it was imported at module level
                    from app.core.security import hash_password 

                    new_hashed = hash_password(new_password)
                    cursor.execute(
                        "UPDATE public.tenants SET hashed_password = %s "
                        "WHERE company_name = %s",
                        (new_hashed, company_name)
                    )
                conn.commit()

            return True, f"Password for '{company_name}' updated successfully."

        except Exception as e:
            return False, f"Password change failed: {str(e)}"

