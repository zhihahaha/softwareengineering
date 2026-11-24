"""密码哈希工具，避免明文存储用户密码。"""
import hashlib
import hmac
import secrets

_ITERATIONS = 240_000


def hash_password(password: str) -> str:
    """返回 PBKDF2-SHA256格式的密码哈希字符串。"""
    if len(password) < 6:
        raise ValueError("密码至少需要6个字符")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """验证密码，格式错误时安全返回False。"""
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False
