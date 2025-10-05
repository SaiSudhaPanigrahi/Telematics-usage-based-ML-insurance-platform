
from datetime import datetime, timedelta
import jwt
from fastapi import Header, HTTPException
from src.utils.config import SECRET_KEY, JWT_EXPIRES_MIN, API_KEY

def create_token(user_id: int):
    payload = {"sub": str(user_id), "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRES_MIN)}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def require_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")
    return True
