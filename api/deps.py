from collections.abc import Generator
import ftplib
from typing import Annotated, Optional

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


def conexion_ftp(
    host: str = 'ftpserver.fichafamiliarchambo.site', 
    user: str = 'admin', 
    passwd: str = 'Y9uHCY8eZ880n', 
    timeout: int = 30

) -> Optional[ftplib.FTP]:
    """
    Establece una conexión segura con un servidor FTP.
    
    Args:
        host (str): Dirección del servidor FTP
        user (str): Nombre de usuario para la autenticación
        passwd (str): Contraseña de acceso
        timeout (int): Tiempo máximo de espera para la conexión
    
    Returns:
        ftplib.FTP: Objeto de conexión FTP o None si falla
    """
    try:
        
        # Crear instancia de FTP con manejo de timeout
        ftp = ftplib.FTP(timeout=timeout)
        
        # Deshabilitar modo pasivo si es necesario
        ftp.set_pasv(False)
        
        # Conectar al servidor con información detallada de logging
        ftp.connect(host=host)
        
        # Autenticar con credenciales
        ftp.login(user=user, passwd=passwd)
        
        # Confirmar conexión exitosa        
        return ftp

    except ftplib.all_errors as e:
        # Manejo comprehensivo de errores de FTP
        return None

def cerrar_conexion_ftp(ftp: Optional[ftplib.FTP]) -> None:
    """
    Cierra de manera segura una conexión FTP.
    
    Args:
        ftp (ftplib.FTP): Objeto de conexión FTP
    """
    if ftp is not None:
        try:
            ftp.quit()
        except ftplib.all_errors as e:
            ftp.close()

   


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