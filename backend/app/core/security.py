# /backend/app/core/security.py
import bcrypt

# --- THE SECURITY GUARD ---
# This file handles passwords. We never store passwords as plain text (like '12345').
# Instead, we 'Hash' them, which turns them into a long string of random characters.

def hash_password(password: str) -> str:
    """
    SCRAMBLING: 
    Turns a human password into a secure scramble. 
    Even if a hacker steals our database, they won't know your password!
    """
    # 1. Generate a 'Salt' (extra randomness)
    salt = bcrypt.gensalt()
    # 2. Hash the password with the salt
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    CHECKING: 
    Compares the password you just typed with the scrambled one in the database.
    If the scramble matches, we let you in!
    """
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
