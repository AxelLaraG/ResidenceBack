import jwt
from datetime import datetime,timedelta
from fastapi import HTTPException, Request

SECRET_KEY = "6c|exxBM5Ci;e'9/C}R:3IU£HdO-\Mh2p8b_wW^\r:]8GxDA9?"

def create_jwt_token(data:dict, expires_delta:timedelta = timedelta(hours=2)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")

def verify_jwt_from_cookie(request: Request):
    token = request.cookies.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Token faltante")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")
