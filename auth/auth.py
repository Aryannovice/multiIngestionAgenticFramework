import logging 
from datetime import datetime, timedelta, timezone
from typing import Annotated
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash 
from database.models import User
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

def authenticate_user(username: str, password: str):
    row = User.get_by_username(username)
    if not row:
        verify_password(password, DUMMY_HASH)
        return None
    
    user_id, username, email, hashed_password, is_active, role = row
    
    if not verify_password(password, hashed_password):
        return None
    
    if not is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    
    # user_role = User.get_by_id(str(user_id)) 
    # print("GET_BY_ID RESULT:", user_role)
    # role = user_role[4] if user_role else "user"

    return {"user_id": str(user_id), "username": username, "role": role}

def create_access_token(user_id: str, username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes
    )
    payload = {"sub": user_id, "username": username, "role": role, "exp": expire}
    print("TOKEN PAYLOAD:", payload)
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)]
) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        username = payload.get("username")
        role = payload.get("role", "user")  # add this
        if not user_id or not username:
            raise credentials_exception
        
        tracker.set_tag("auth_user", username)
        return TokenData(user_id=user_id, username=username, role=role)  # add role
    except InvalidTokenError:
        tracker.set_tag("auth_status", "failed")
        raise credentials_exception
    
    
