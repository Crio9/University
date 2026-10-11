from passlib.context import CryptContext
import os
from datetime import datetime,timedelta,timezone
import jwt
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

SECRET_KEY = os.environ["JWT_SECRET_KEY"]
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


def get_pass_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(
    password: str,
    password_hash: str
) -> bool:
    return pwd_context.verify(password, password_hash)

def create_access_token(email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=30)

    payload = {
        "sub": email,
        "exp": expire
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return token


def decode_access_token(token: str) -> str | None: # What token does send back by default, do not forget!!!
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "exp"]}
        )
        email = payload.get("sub")

        if not isinstance(email, str) or not email:
            return None

        return email

    except jwt.InvalidTokenError:
        return None

