import base64, hashlib, hmac, secrets

def hash_password(password: str):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600000)
    return 'pbkdf2_sha256$600000$' + base64.b64encode(salt).decode() + '$' + base64.b64encode(digest).decode()

def verify_password(password: str, stored: str):
    try:
        algo, iterations, salt, expected = stored.split('$')
        if algo != 'pbkdf2_sha256': return False
        result = hashlib.pbkdf2_hmac('sha256', password.encode(), base64.b64decode(salt), int(iterations))
        return hmac.compare_digest(result, base64.b64decode(expected))
    except (ValueError, TypeError):
        return False
