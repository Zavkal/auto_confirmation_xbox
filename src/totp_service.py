import pyotp


def generate_totp(secret: str) -> str:
    cleaned = secret.replace(" ", "").replace("-", "").upper()
    return pyotp.TOTP(cleaned).now()
