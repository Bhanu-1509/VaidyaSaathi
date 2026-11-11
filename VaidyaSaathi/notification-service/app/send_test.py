"""Send a test email to check the SMTP settings.

Docker:  docker compose exec notification-service python -m app.send_test you@example.com
"""
import sys

from app.main import SMTP_HOST, SMTP_PORT, SMTP_USER, deliver

if len(sys.argv) != 2:
    sys.exit("Usage: python -m app.send_test you@example.com")
print(f"Mode: {'SMTP ' + SMTP_HOST + ':' + str(SMTP_PORT) + ' as ' + SMTP_USER if SMTP_HOST else 'console (SMTP_HOST is empty)'}")
try:
    result = deliver(sys.argv[1], "VaidyaSaathi test email", "If you can read this, email sending works.")
except Exception as exc:  # show the real reason
    sys.exit(f"FAILED: {exc!r}")
print("Sent. Check the inbox (and spam folder)." if result == "sent" else "Printed to the log only, because SMTP_HOST is empty.")
