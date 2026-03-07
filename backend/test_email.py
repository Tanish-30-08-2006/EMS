import sys
import os
import tempfile

# This tells Python to treat the current folder as the root, solving the 'app' module error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.core.email_service import send_export_email

# 1. Create a fake text file to attach
f = tempfile.NamedTemporaryFile(suffix='.txt', delete=False)
f.write(b'This is a test export file.')
f.close()

# 2. Attempt to send the email (REPLACE WITH YOUR PERSONAL EMAIL)
target_email = "your_email@example.com" 
print(f"Testing sending an email to: {target_email}...")

ok, msg = send_export_email(target_email, 'Test Company', f.name, 'Test')

# 3. Print the result
if ok:
    print("\n✅ SUCCESS!")
    print(msg)
else:
    print("\n❌ FAILED!")
    print(msg)

# 4. Clean up the fake file
os.unlink(f.name)
