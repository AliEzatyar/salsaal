import jwt
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from database import SessionLocal as db
from dependencies import get_db
from models import User
from sqlalchemy.orm import Session

PUBLIC_KEY = None
ALGORITHM = "RS256"
security = HTTPBearer()

# Load the same public key Django uses
with open("public.pem", "r") as f:
    PUBLIC_KEY = f.read()
    print(PUBLIC_KEY)


def decode_token(token):
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])
        token_iat = payload["iat"]
        if token_iat is None:
            return None
        return payload
    except Exception as e:
        print("error:", e)
        return None


async def get_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    token_iat = payload["iat"]
    user = db.scalars(select(User).where(User.id == user_id)).first()
    if user.token_valid_after > datetime.fromtimestamp(token_iat, timezone.utc):
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Fetch user from DB if needed (SQLAlchemy or ORM)
    return user
