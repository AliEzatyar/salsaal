import zlib
import jwt
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from dependencies import get_db
from models import User
from sqlalchemy.orm import Session
from requests import get
from os import environ as env
from utils import redis

ANON_THROTTLE_PER_HOUR=36000
USER_THROTTLE_PER_HOUR=50
PUBLIC_KEY = None
ALGORITHM = "RS256"
security = HTTPBearer(auto_error=False)

# sending request to get public key for jwt authentication
resp = get(env.get("DJANGO_SERVER_URL") + "/jwtks/").text
PUBLIC_KEY = resp


def decode_token(token):
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])
        token_iat = payload["iat"]
        if token_iat is None:
            return None
        return payload
    except Exception as e:
        print("error decoding user token in fastAPI:", e)
        return None


def get_throttle_cache_key(typ, ip=None,user_id=None):
    if typ == "anon":
        return f"anon:{ip}:trtl"
    else:
        return f"user:{user_id}:trtl"


async def throttle_request(http_request=None,user_id=None):
    """throttle requests to prevent abuse"""
    raw= None
    key = None
    throttle_amount = USER_THROTTLE_PER_HOUR
    if http_request:
        real_ip_addr = http_request.client.host
        key = get_throttle_cache_key("anon", ip=real_ip_addr)
        raw = await redis.get(key)
        throttle_amount = ANON_THROTTLE_PER_HOUR
        
    elif user_id:
        key = get_throttle_cache_key("user",user_id=user_id)
        raw = await redis.get(key)
        

    if raw:
        val = int(raw) 
        if val >= throttle_amount:
            return False
        await redis.incrby(key)
        return True
    # first request, set key with expiry
    await redis.incrby(key)
    await redis.expire(key, 3600)
    return True

async def get_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        token = credentials.credentials
        payload = decode_token(token)
        if not payload:
            return None
        user_id = payload.get("user_id")
        if not user_id:
            return None
        token_iat = payload["iat"]
        user = db.scalars(select(User).where(User.id == user_id)).first()
        if user.token_valid_after > datetime.fromtimestamp(token_iat, timezone.utc):
            return None
        # Fetch user from DB if needed (SQLAlchemy or ORM)
        return user
    except Exception as e:
        return None
