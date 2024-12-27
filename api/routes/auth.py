


from typing import Annotated, Union
from contextlib import asynccontextmanager
from fastapi import APIRouter, Depends, FastAPI
from dotenv import dotenv_values
import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from sqlmodel import select
from model import Profesores
from api.deps import SessionDep


router = APIRouter()


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class User(BaseModel):
    nombre: str
    email: str | None = None
    rol: str | None = None
    id: int | None = None


class UserInDB(User):
    hashed_password: str

SECRET_KEY = "15b7036b06be44e41fb66df54d966670ff46000ff0196728efeff0d3512e6d38"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

#print("1111111111")



def verify_password(plain_password, hashed_password):

    #print(plain_password, hashed_password)
    #return pwd_context.verify(plain_password, hashed_password)
    return plain_password == hashed_password


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user(session: SessionDep, email: str): #aqui
    statement = select(Profesores).where(Profesores.email == email)
    result = session.exec(statement).first()
    
    #user = User(nombre=result.nombre, email=result.email, rol=result.rol)

    if not result:
        #print("Usuario no encontrado")
        return None  # Devuelve None si el usuario no existe
    return UserInDB(
        nombre=result.nombre,
        email=result.email,
        rol=result.rol,
        id=result.id,
        hashed_password=result.password
    )


def authenticate_user(session: SessionDep, username: str, password: str):
    user = get_user(session, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(session: SessionDep,token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(username=email)
    except InvalidTokenError:
        raise credentials_exception
    user = get_user(session, email=token_data.username)
    #print(token_data.username)
    if user is None:
        raise credentials_exception
    

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    
    return current_user


@router.post("/token")
async def login_for_access_token(
    session: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],

) -> Token:
    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")


@router.get("/users/me/", response_model=User)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    return current_user
