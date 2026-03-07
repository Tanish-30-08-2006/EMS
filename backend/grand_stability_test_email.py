# =============================================================================
# backend/grand_stability_test_email.py
# =============================================================================
# Tests every edge case for the email feature:
#   - New columns exist in Supabase
#   - Email format validator (valid and invalid inputs)
#   - Signup with email
#   - Signup without email (backward compat)
#   - Signup with blank/whitespace email (treated as None)
#   - Duplicate company name rejected
#   - Duplicate email rejected
#   - Invalid email format at signup rejected
#   - get_company_email (exists / missing / no email)
#   - get_company_email_by_tenant_id
#   - update_company_email (all security and format guards)
#   - email_service module import and error-path functions
# Does NOT send real emails. SMTP is not called.
# =============================================================================

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.system.provisioning_service import ProvisioningService, is_valid_email
from app.core.connection_factory import ConnectionFactory
from services.query_engine import set_current_tenant

# ── Test counters ─────────────────────────────────────────────────────────────
passed = 0
failed = 0

# ── Test company names (all start with TEST_ so force_delete works) ───────────
COMPANY_A = "TEST_EmailFeature_A"   # will have email
COMPANY_B = "TEST_EmailFeature_B"   # will have NO email
COMPANY_C = "TEST_EmailFeature_C"   # starts without email, gets one added later

PASSWORD  = "EmailTest@Pass1"
EMAIL_A   = "test_company_alpha_ems@mailinator.com"
EMAIL_B   = "test_company_beta_ems@mailinator.com"
EMAIL_C   = "test_company_gamma_ems@mailinator.com"

def ok(msg):
    global passed; passed += 1
    print(f"  \033[92m[PASS]\033[0m {msg}")

def fail(msg):
    global failed; failed += 1
    print(f"  \033[91m[FAIL]\033[0m {msg}")

def info(msg):
    print(f"  \033[90m[INFO]\033[0m {msg}")

def section(title):
    print(f"\n\033[1;36m{'═'*68}\033[0m")
    print(f"\033[1;33m  {title}\033[0m")
    print(f"\033[1;36m{'═'*68}\033[0m")

def db_get_email(company_name):
    """Directly query Supabase for a company's stored email."""
    with ConnectionFactory.get_admin_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT contact_email FROM public.tenants "
                "WHERE company_name = %s",
                (company_name,)
            )
            row = cur.fetchone()
            return row[0] if row else None

def db_get_tenant_id(company_name):
    """Directly query Supabase for a company's tenant_id."""
    with ConnectionFactory.get_admin_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tenant_id FROM public.tenants "
                "WHERE company_name = %s",
                (company_name,)
            )
            row = cur.fetchone()
            return row[0] if row else None

def db_column_exists(column_name):
    """Check if a column exists in public.tenants."""
    with ConnectionFactory.get_admin_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name   = 'tenants'
                  AND column_name  = %s
            """, (column_name,))
            return cur.fetchone() is not None

# =============================================================================
# SETUP
# =============================================================================
section("SETUP — Clean up any leftover test companies")

for tc in [COMPANY_A, COMPANY_B, COMPANY_C]:
    try:
        ProvisioningService.force_delete_test_company(tc)
        info(f"Cleaned up: {tc}")
    except Exception:
        pass

# Clean up any accidental companies from error-path tests
for extra in ["TEST_BadEmailFmt_EMS", "TEST_DupEmail_EMS"]:
    try:
        ProvisioningService.force_delete_test_company(extra)
    except Exception:
        pass

time.sleep(0.3)

# =============================================================================
# SECTION 1 — Supabase schema verification
# =============================================================================
section("SECTION 1 — Verify new Supabase columns exist")

ok("contact_email column exists in public.tenants") if db_column_exists(
    "contact_email") else fail(
    "contact_email MISSING. Did you run Step A3 in Supabase?")

ok("google_sub column exists in public.tenants") if db_column_exists(
    "google_sub") else fail(
    "google_sub MISSING. Did you run Step A4 in Supabase?")

ok("email_verified column exists in public.tenants") if db_column_exists(
    "email_verified") else fail(
    "email_verified MISSING. Did you run Step A5 in Supabase?")

# =============================================================================
# SECTION 2 — Email format validator
# =============================================================================
section("SECTION 2 — is_valid_email() validation")

# Valid email addresses — all must return True
valid_cases = [
    "user@gmail.com",
    "admin@mycompany.co.uk",
    "tanish.30@daiict.ac.in",
    "test+label@subdomain.company.com",
    "user123@domain.org",
    "A@b.com",
    "very.long.email.address@really.long.domain.name.com",
]
for e in valid_cases:
    ok(f"Valid accepted:    {e}") if is_valid_email(e) else fail(
        f"Should be valid but rejected: {e}")

# Invalid email addresses — all must return False
invalid_cases = [
    "",
    "   ",
    "notanemail",
    "@gmail.com",
    "user@",
    "user@.com",
    "user @gmail.com",
    "user@gmail",
    "user@@gmail.com",
    "@",
    "plaintext",
]
for e in invalid_cases:
    ok(f"Invalid rejected:  '{e}'") if not is_valid_email(e) else fail(
        f"Should be invalid but accepted: '{e}'")

# =============================================================================
# SECTION 3 — Signup WITH email
# =============================================================================
section("SECTION 3 — Provision company WITH email")

s, r = ProvisioningService.provision_new_company(COMPANY_A, PASSWORD, EMAIL_A)
ok(f"Provision {COMPANY_A} with email. Tenant: {r}") if s else fail(
    f"Provision with email failed: {r}")

if s:
    stored = db_get_email(COMPANY_A)
    ok(f"Email stored in DB = {stored}") if stored == EMAIL_A else fail(
        f"Email not stored. Expected '{EMAIL_A}', got '{stored}'")

# =============================================================================
# SECTION 4 — Signup WITHOUT email (backward compatibility)
# =============================================================================
section("SECTION 4 — Provision company WITHOUT email (backward compat)")

s, r = ProvisioningService.provision_new_company(COMPANY_B, PASSWORD)
ok(f"Provision {COMPANY_B} without email succeeded") if s else fail(
    f"Provision without email failed: {r}")

if s:
    stored = db_get_email(COMPANY_B)
    ok("contact_email is NULL when no email provided") if stored is None else fail(
        f"Expected None, got '{stored}'")

# =============================================================================
# SECTION 5 — Signup with blank/whitespace email (treated as None)
# =============================================================================
section("SECTION 5 — Signup with whitespace-only email = treated as None")

s, r = ProvisioningService.provision_new_company(COMPANY_C, PASSWORD, "   ")
ok(f"Provision {COMPANY_C} with '   ' treated as no-email") if s else fail(
    f"Provision failed: {r}")

if s:
    stored = db_get_email(COMPANY_C)
    ok("Whitespace email stored as NULL") if stored is None else fail(
        f"Expected None, got '{stored}'")

# =============================================================================
# SECTION 6 — Duplicate company name
# =============================================================================
section("SECTION 6 — Duplicate company name rejected")

s, r = ProvisioningService.provision_new_company(
    COMPANY_A, PASSWORD, "other@email.com")
ok("Duplicate company name rejected") if not s else fail(
    f"Should reject duplicate name. Got: {r}")
info(f"Rejection message: {r}")
# Clean up just in case it was accidentally created
try:
    ProvisioningService.force_delete_test_company(COMPANY_A + "_duplicate")
except Exception:
    pass

# =============================================================================
# SECTION 7 — Duplicate email rejected
# =============================================================================
section("SECTION 7 — Duplicate email address rejected")

# EMAIL_A is already registered to COMPANY_A
s, r = ProvisioningService.provision_new_company(
    "TEST_DupEmail_EMS", PASSWORD, EMAIL_A)
ok("Duplicate email address rejected") if not s else fail(
    f"Should reject duplicate email. Got tenant: {r}")
info(f"Rejection message: {r}")
try:
    ProvisioningService.force_delete_test_company("TEST_DupEmail_EMS")
except Exception:
    pass

# =============================================================================
# SECTION 8 — Invalid email format at signup
# =============================================================================
section("SECTION 8 — Invalid email format rejected at signup")

bad_emails = [
    "notanemail",
    "@nogood.com",
    "missingdomain@",
    "has space@email.com",
    "double@@at.com",
]
for bad in bad_emails:
    s, r = ProvisioningService.provision_new_company(
        "TEST_BadEmailFmt_EMS", PASSWORD, bad)
    ok(f"Bad email '{bad}' rejected at signup") if not s else fail(
        f"Should reject '{bad}'. Got: {r}")
    try:
        ProvisioningService.force_delete_test_company("TEST_BadEmailFmt_EMS")
    except Exception:
        pass

# =============================================================================
# SECTION 9 — get_company_email
# =============================================================================
section("SECTION 9 — get_company_email()")

# Company WITH email
s, result = ProvisioningService.get_company_email(COMPANY_A)
ok(f"get_company_email({COMPANY_A}) = {result}") if (
    s and result == EMAIL_A) else fail(
    f"Expected '{EMAIL_A}', got: {result}")

# Company WITHOUT email
s, result = ProvisioningService.get_company_email(COMPANY_B)
ok("get_company_email returns False for no-email company") if not s else fail(
    f"Should return False. Got: {result}")
info(f"No-email message: {result}")

# Non-existent company
s, result = ProvisioningService.get_company_email("GHOST_COMPANY_XYZ")
ok("get_company_email returns False for non-existent company") if not s else fail(
    f"Should return False. Got: {result}")

# =============================================================================
# SECTION 10 — get_company_email_by_tenant_id
# =============================================================================
section("SECTION 10 — get_company_email_by_tenant_id()")

tid_a = db_get_tenant_id(COMPANY_A)
s, result = ProvisioningService.get_company_email_by_tenant_id(tid_a)
ok(f"Lookup by tenant_id: got ({result})") if s else fail(
    f"Failed tenant_id lookup: {result}")
if s:
    co_name, co_email = result
    ok(f"company_name = {co_name}") if co_name == COMPANY_A else fail(
        f"Expected {COMPANY_A}, got {co_name}")
    ok(f"contact_email = {co_email}") if co_email == EMAIL_A else fail(
        f"Expected {EMAIL_A}, got {co_email}")

# Tenant with no email
tid_b = db_get_tenant_id(COMPANY_B)
s, result = ProvisioningService.get_company_email_by_tenant_id(tid_b)
ok("No-email tenant returns False from tenant_id lookup") if not s else fail(
    f"Should be False. Got: {result}")

# Non-existent tenant_id
s, result = ProvisioningService.get_company_email_by_tenant_id("comp_ghost_xyz")
ok("Ghost tenant_id returns False") if not s else fail(
    f"Should be False. Got: {result}")

# =============================================================================
# SECTION 11 — update_company_email
# =============================================================================
section("SECTION 11 — update_company_email() (all guards)")

# 11-a: Wrong password must fail
s, m = ProvisioningService.update_company_email(
    COMPANY_B, "WRONGPASS", EMAIL_B)
ok("Wrong password rejected on email update") if not s else fail(
    f"Should reject wrong pass. Got: {m}")

# 11-b: Invalid email format must fail
s, m = ProvisioningService.update_company_email(
    COMPANY_B, PASSWORD, "notvalid")
ok("Invalid format rejected on update") if not s else fail(
    f"Should reject bad format. Got: {m}")

# 11-c: Empty email must fail
s, m = ProvisioningService.update_company_email(
    COMPANY_B, PASSWORD, "  ")
ok("Blank email rejected on update") if not s else fail(
    f"Should reject blank. Got: {m}")

# 11-d: Email already taken by COMPANY_A must fail
s, m = ProvisioningService.update_company_email(
    COMPANY_B, PASSWORD, EMAIL_A)
ok("Email taken by other company rejected") if not s else fail(
    f"Should reject taken email. Got: {m}")
info(f"Conflict message: {m}")

# 11-e: Valid new email must succeed
s, m = ProvisioningService.update_company_email(
    COMPANY_B, PASSWORD, EMAIL_B)
ok(f"Valid email update succeeded") if s else fail(
    f"Valid update failed: {m}")
if s:
    stored = db_get_email(COMPANY_B)
    ok(f"DB confirmed: {stored}") if stored == EMAIL_B else fail(
        f"DB has '{stored}', expected '{EMAIL_B}'")

# 11-f: Re-setting same email on same company must succeed (idempotent)
s, m = ProvisioningService.update_company_email(
    COMPANY_B, PASSWORD, EMAIL_B)
ok("Setting same email again on same company succeeds") if s else fail(
    f"Idempotent update failed: {m}")

# 11-g: Non-existent company must fail
s, m = ProvisioningService.update_company_email(
    "GHOST_COMPANY_XYZ", PASSWORD, "new@email.com")
ok("Ghost company rejected on email update") if not s else fail(
    f"Should be False. Got: {m}")

# 11-h: Add email to COMPANY_C (currently NULL)
s, m = ProvisioningService.update_company_email(
    COMPANY_C, PASSWORD, EMAIL_C)
ok(f"Email added to previously email-less company") if s else fail(
    f"Failed: {m}")
if s:
    stored = db_get_email(COMPANY_C)
    ok(f"DB confirmed: {stored}") if stored == EMAIL_C else fail(
        f"Expected '{EMAIL_C}', got '{stored}'")

# 11-i: Verify all three companies now have distinct emails
emails_set = set()
for cn in [COMPANY_A, COMPANY_B, COMPANY_C]:
    e = db_get_email(cn)
    if e:
        emails_set.add(e)
ok("All three companies have 3 distinct emails") if len(
    emails_set) == 3 else fail(
    f"Expected 3 unique emails, got {len(emails_set)}: {emails_set}")

# =============================================================================
# SECTION 12 — email_service module
# =============================================================================
section("SECTION 12 — email_service module and error paths")

try:
    from app.core.email_service import (
        send_export_email,
        send_verification_email,
    )
    ok("email_service.py imported successfully")
    ok("send_export_email is callable") if callable(
        send_export_email) else fail("send_export_email not callable")
    ok("send_verification_email is callable") if callable(
        send_verification_email) else fail("send_verification_email not callable")
except ImportError as ie:
    fail(f"Cannot import email_service: {ie}")

# 12-a: Non-existent file path must return False clearly
s, m = send_export_email(
    "test@mailinator.com", "TestCo",
    "/nonexistent/path/export.xlsx", "Excel Workbook")
ok("Returns False for non-existent file") if not s else fail(
    f"Should fail for missing file. Got: {m}")
ok("Error message mentions file/path") if any(
    word in m.lower() for word in ["file", "path", "found"]) else fail(
    f"Unclear error: {m}")

# 12-b: Empty recipient must return False
s, m = send_export_email("", "TestCo", "/any/path.xlsx", "Excel")
ok("Returns False for empty recipient") if not s else fail(
    f"Should fail empty recipient. Got: {m}")

# 12-c: Folder path (CSV export result) must return False
import tempfile, os as _os
with tempfile.TemporaryDirectory() as tmpdir:
    s, m = send_export_email(
        "test@mailinator.com", "TestCo", tmpdir, "CSV Bundle")
    ok("Returns False when path is a folder (CSV case)") if not s else fail(
        f"Should fail for folder path. Got: {m}")
    ok("Error message explains folder limitation") if any(
        word in m.lower() for word in [
            "folder", "directory", "file", "csv"]) else fail(
        f"Unclear error: {m}")

# 12-d: Missing .env credentials returns clear error (no SMTP attempted)
# Temporarily clear the env var to simulate missing config
original_sender = os.environ.pop("EMS_GMAIL_SENDER", None)
original_pw     = os.environ.pop("EMS_GMAIL_APP_PASSWORD", None)

import tempfile
with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
    tmp_path = tmp.name
    tmp.write(b"fake xlsx content")

s, m = send_export_email("test@mailinator.com", "TestCo", tmp_path, "Excel")
ok("Returns False when .env credentials missing") if not s else fail(
    f"Should fail with missing creds. Got: {m}")
ok("Error message mentions .env or EMS_GMAIL") if any(
    word in m.lower() for word in [
        ".env", "ems_gmail", "missing", "app_password",
        "apppassword", "sender"]) else fail(
    f"Unclear error: {m}")

_os.unlink(tmp_path)

# Restore env vars if they were set
if original_sender:
    os.environ["EMS_GMAIL_SENDER"] = original_sender
if original_pw:
    os.environ["EMS_GMAIL_APP_PASSWORD"] = original_pw

# =============================================================================
# SECTION 13 — Session flow integration
# =============================================================================
section("SECTION 13 — Session flow integration")

# 13-a: After provisioning, session lookup works correctly
set_current_tenant(db_get_tenant_id(COMPANY_A))
import services.query_engine as _qe
ok(f"CURRENT_TENANT_ID set correctly: {_qe.CURRENT_TENANT_ID}") if (
    _qe.CURRENT_TENANT_ID is not None) else fail("CURRENT_TENANT_ID is None")

# 13-b: Email lookup by tenant_id works from session
tid = _qe.CURRENT_TENANT_ID
s, result = ProvisioningService.get_company_email_by_tenant_id(tid)
ok(f"Email accessible from active session tenant_id") if s else fail(
    f"Session-based email lookup failed: {result}")

# =============================================================================
# TEARDOWN
# =============================================================================
section("TEARDOWN — Removing all test companies")

for tc in [COMPANY_A, COMPANY_B, COMPANY_C]:
    s, m = ProvisioningService.force_delete_test_company(tc)
    ok(f"Deleted {tc}") if s else fail(f"Could not delete {tc}: {m}")

# =============================================================================
# FINAL REPORT
# =============================================================================
total = passed + failed
print(f"\n\033[1;36m{'═'*68}\033[0m")
print(f"\033[1;33m  EMAIL FEATURE — GRAND STABILITY TEST\033[0m")
print(f"\033[1;36m{'═'*68}\033[0m")
print(f"  Total Tests  : {total}")
print(f"  \033[92mPassed       : {passed}\033[0m")
print(f"  \033[91mFailed       : {failed}\033[0m")
print(f"\033[1;36m{'═'*68}\033[0m")

if failed == 0:
    print(f"\n  \033[1;92m ALL {passed} TESTS PASSED. EMAIL FEATURE STABLE.\033[0m\n")
else:
    print(f"\n  \033[1;91m {failed} TEST(S) FAILED. SEE OUTPUT ABOVE.\033[0m\n")
    sys.exit(1)
