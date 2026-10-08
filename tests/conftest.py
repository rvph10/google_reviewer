import os

from cryptography.fernet import Fernet

os.environ.update({
    "SECRET_KEY": "test-secret",
    "ENCRYPTION_KEY": Fernet.generate_key().decode(),
    "ADMIN_PASSWORD": "test",
    "GBP_MODE": "fake",
    "RESEND_API_KEY": "",
    "SCHEDULER_ENABLED": "false",
})
