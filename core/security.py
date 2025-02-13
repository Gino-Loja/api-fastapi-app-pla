

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext
import pytz
from core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


ALGORITHM = "HS256"


def create_access_token(subject: str | Any, expires_delta: timedelta) -> str:
    expire = datetime.now(pytz.timezone('America/Guayaquil')) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# async def create_db_and_tables():
#     print("Creando tablas")
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)


# async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
#     async with async_session_maker() as session:
#         yield session


# async def get_user_db(session: SessionDep ):
#     yield SQLAlchemyUserDatabase(session, User)
    
    
# async def get_access_token_db(
#     session: SessionDep,
# ):  
#     yield SQLAlchemyAccessTokenDatabase(session, AccessToken)
