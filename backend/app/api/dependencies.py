from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from app.core.config import settings
from app.schemas.user import TokenData, UserResponse
from app.db.database import get_database
from bson import ObjectId

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login"
)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserResponse:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        token_data = TokenData(**payload)
        if token_data.email is None:
            # We are using sub (which maps to email or id)
            email: str = payload.get("sub")
            if email is None:
                raise credentials_exception
            token_data = TokenData(email=email)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    db = get_database()
    user = await db.users.find_one({"email": token_data.email})
    
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
        
    return UserResponse(
        id=str(user["_id"]),
        email=user["email"],
        username=user["username"],
        created_at=user["created_at"]
    )
