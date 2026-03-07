# backend/app/core/email_service.py
# ═══════════════════════════════════════════════════════════════════════════════
# THE EMAIL POSTMASTER
# All outgoing emails from EMS go through this single file.
# Uses Gmail SMTP + an App Password (NOT your real Gmail password).
#
# Setup required in backend/.env:
#   EMS_GMAIL_SENDER=your_gmail@gmail.com
#   EMS_GMAIL_APP_PASSWORD=your16charapppassword
#
# Get an App Password at: https://myaccount.google.com/apppasswords
# (Requires 2-Factor Authentication to be turned on on your Google account.)
# ═══════════════════════════════════════════════════════════════════════════════

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.mime.base      import MIMEBase
from email                import encoders


def _get_smtp_credentials():
    """
    THE CREDENTIAL READER:
    Reads EMS_GMAIL_SENDER and EMS_GMAIL_APP_PASSWORD from the .env file.
    Both are loaded by python-dotenv at startup. If either is missing,
    this raises a ValueError with an exact instruction to fix it.
    This function is private (starts with _) — only called from within
    this file. No other file should call it.
    """
    sender = os.getenv("EMS_GMAIL_SENDER", "").strip()
    app_pw = os.getenv("EMS_GMAIL_APP_PASSWORD", "").strip()

    if not sender:
        raise ValueError(
            "EMS_GMAIL_SENDER is missing from your .env file.\n"
            "Add this line to backend/.env:\n"
            "EMS_GMAIL_SENDER=your_gmail@gmail.com"
        )
    if not app_pw:
        raise ValueError(
            "EMS_GMAIL_APP_PASSWORD is missing from your .env file.\n"
            "Add this line to backend/.env:\n"
            "EMS_GMAIL_APP_PASSWORD=your16charapppassword\n"
            "Get one at: https://myaccount.google.com/apppasswords"
        )
    return sender, app_pw


def send_export_email(recipient_email: str,
                      company_name:    str,
                      file_path:       str,
                      export_type:     str = "Export"):
    """
    THE EXPORT DELIVERY:
    Emails a single exported file as an attachment to the company's
    registered email address after an export is generated.

    Parameters:
        recipient_email — the stored contact_email from public.tenants
        company_name    — used in the subject line and email body
        file_path       — full absolute path to the file to attach
        export_type     — label: "Excel Workbook", "JSON Snapshot", etc.

    Returns (True, success_message) or (False, error_message).
    Never raises an exception — always returns a tuple.
    """
    # Guard: empty recipient
    if not recipient_email or not recipient_email.strip():
        return False, "No recipient email address provided."

    # Guard: file must exist before we try to attach it
    if not os.path.exists(file_path):
        return False, f"Export file not found at path: {file_path}"

    # Guard: file must be a file (not a directory — CSV export produces a folder)
    if not os.path.isfile(file_path):
        return False, (
            "The path is a folder, not a file. "
            "Only Excel (.xlsx) and JSON exports can be emailed. "
            "CSV export produces a folder and cannot be emailed as a single file."
        )

    try:
        sender_email, app_password = _get_smtp_credentials()
    except ValueError as cred_error:
        return False, str(cred_error)

    try:
        # ── Build the email ──────────────────────────────────────────────────
        msg            = MIMEMultipart()
        msg['From']    = sender_email
        msg['To']      = recipient_email
        msg['Subject'] = f"EMS {export_type} — {company_name}"

        body = (
            f"Hello {company_name},\n\n"
            f"Your {export_type} export has been generated and is attached.\n\n"
            f"File: {os.path.basename(file_path)}\n\n"
            f"This is an automated message from your "
            f"Employee Management System.\n"
        )
        msg.attach(MIMEText(body, 'plain'))

        # ── Attach the file ──────────────────────────────────────────────────
        with open(file_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename="{os.path.basename(file_path)}"'
        )
        msg.attach(part)

        # ── Connect to Gmail and send ────────────────────────────────────────
        # Port 587 is the standard for SMTP with TLS (Transport Layer Security).
        # TLS encrypts the connection so the password and email are not sent
        # as plain text over the internet.
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.ehlo()          # Identify ourselves to the Gmail server
            smtp.starttls()      # Upgrade the connection to encrypted TLS
            smtp.login(sender_email, app_password)
            smtp.sendmail(sender_email, recipient_email, msg.as_string())

        return True, f"Email sent successfully to {recipient_email}."

    except smtplib.SMTPAuthenticationError:
        return False, (
            "Gmail rejected the login credentials.\n"
            "Check EMS_GMAIL_APP_PASSWORD in backend/.env.\n"
            "The App Password must be exactly 16 characters with no spaces.\n"
            "Create one at: https://myaccount.google.com/apppasswords"
        )
    except smtplib.SMTPRecipientsRefused:
        return False, (
            f"Gmail refused to send to: {recipient_email}\n"
            "Check the email address is correctly formatted."
        )
    except smtplib.SMTPConnectError:
        return False, (
            "Could not connect to Gmail. Check your internet connection."
        )
    except smtplib.SMTPException as e:
        return False, f"SMTP error while sending: {str(e)}"
    except OSError as e:
        return False, f"File read error while attaching: {str(e)}"
    except Exception as e:
        return False, f"Unexpected email error: {str(e)}"


def send_verification_email(recipient_email: str,
                             company_name:    str,
                             code:            str):
    """
    THE VERIFICATION SENDER:
    Sends a 6-digit verification code to the company email during signup.
    The user must type this code back into the CLI to confirm they own
    the email address before it is saved to the database.

    Returns (True, success_message) or (False, error_message).
    """
    if not recipient_email or not recipient_email.strip():
        return False, "No recipient email address provided."

    try:
        sender_email, app_password = _get_smtp_credentials()
    except ValueError as cred_error:
        return False, str(cred_error)

    try:
        msg            = MIMEMultipart()
        msg['From']    = sender_email
        msg['To']      = recipient_email
        msg['Subject'] = f"EMS Email Verification Code — {company_name}"

        body = (
            f"Hello {company_name},\n\n"
            f"Your EMS email verification code is:\n\n"
            f"        {code}\n\n"
            f"Type this 6-digit code in the terminal to complete registration.\n"
            f"This code expires in 10 minutes.\n\n"
            f"If you did not request this, ignore this email.\n"
        )
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(sender_email, app_password)
            smtp.sendmail(sender_email, recipient_email, msg.as_string())

        return True, f"Verification code sent to {recipient_email}."

    except smtplib.SMTPAuthenticationError:
        return False, (
            "Gmail rejected the App Password. "
            "Check EMS_GMAIL_APP_PASSWORD in backend/.env."
        )
    except Exception as e:
        return False, f"Verification email error: {str(e)}"
