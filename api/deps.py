from collections.abc import Generator
from typing import Annotated

# import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
# from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

# from app.core import security
from core.config import settings
from core.db import engine
import smtplib 
from email.message import EmailMessage 
#from app.models import TokenPayload, User

# reusable_oauth2 = OAuth2PasswordBearer(
#     tokenUrl=f"{settings.API_V1_STR}/login/access-token"
# )


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
#TokenDep = Annotated[str, Depends(reusable_oauth2)]

def sender_email(to: str, subject: str, text: str) -> True:

    try:
        sender_email_address = "ginoarkaniano@gmail.com" 
        email_smtp = "smtp.gmail.com" 
        email_password = "xsmx ekzb esfm pizr" 

        # Create an email message object 
        message = EmailMessage() 

        # Configure email headers 
        message['Subject'] = subject 
        message['From'] = sender_email_address 
        message['To'] = to 

        # Set email body text 
        message.set_content(text) 

        # Set smtp server and port 
        server = smtplib.SMTP(email_smtp, '587') 

        # Identify this client to the SMTP server 
        server.ehlo() 

        # Secure the SMTP connection 
        server.starttls() 

        # Login to email account 
        server.login(sender_email_address, email_password) 

        # Send email 
        server.send_message(message) 

        # Close connection to server 
        server.quit()
        return True
    except e:
        return False


   


# def get_current_user(session: SessionDep, token: TokenDep) -> User:
#     try:
#         payload = jwt.decode(
#             token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
#         )
#         token_data = TokenPayload(**payload)
#     except (InvalidTokenError, ValidationError):
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Could not validate credentials",
#         )
#     user = session.get(User, token_data.sub)
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#     if not user.is_active:
#         raise HTTPException(status_code=400, detail="Inactive user")
#     return user


# CurrentUser = Annotated[User, Depends(get_current_user)]


# def get_current_active_superuser(current_user: CurrentUser) -> User:
#     if not current_user.is_superuser:
#         raise HTTPException(
#             status_code=403, detail="The user doesn't have enough privileges"
#         )
#     return current_user