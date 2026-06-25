import logging 

from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash 
from models.schema import TokenData
from config.settings import get_settings
from observability.tracker import tracker

logger = logging.getLogger(__name__)

settings = get_settings()

password_hash = PasswordHash.recommended()
DUMMY_HASH = password_hash.hash("dummypassword")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


def verify_password(plain: str, hashed: str) -> bool:
    return password_hash.verify(plain, hashed)

def authenticate_user(username: str, password: str) -> bool:
    if username != settings.app_username:
        verify_password(password, DUMMY_HASH)
        tracker.set_tag("auth_status", "failed")
        tracker.set_tag("auth_user", username)
        return False  ##we run verify even if its on wrong username as well
    
    ##when desgining a multi user setup, we can replace this with db lookup + hashed password compare
    if password != settings.app_password:
        tracker.set_tag("auth_status", "failed")
        tracker.set_tag("auth_user", username)
        logger.warning("Authentication failed for user: %s", username)
        return False
    
    return True

def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes
        )
    payload = {"sub": username, "exp": expire}
    token = jwt.encode(
        payload, settings.jwt_secret, algorithm="HS256"
        )
    return token

async def get_current_user(
        token: Annotated[str, Depends(oauth2_scheme)]
) -> TokenData:
    logger.info("AUTH | TOKEN RECEIVED | TOKEN=%s", token[:20])
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token , settings.jwt_secret, algorithms=["HS256"]

        )
        username =payload.get("sub")
        if not username:
            raise credentials_exception
        
        tracker.set_tag("auth_status", "success")
        return TokenData(username=username)
    except InvalidTokenError:
        tracker.set_tag("auth_status", "failed")
        raise credentials_exception
    
    ##fir if we do get a multi user setup then
    # async def get_current_active_user(
#     current_user: Annotated[TokenData, Depends(get_current_user)],
# ) -> TokenData:
#     # replace with DB lookup: user = Session.get_by_username(current_user.username)
#     # if not user or not user.is_active:
#     #     raise HTTPException(status_code=400, detail="Inactive user")
#     return current_user
