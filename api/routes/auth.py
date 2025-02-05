from datetime import datetime, timedelta, timezone
from email.message import Message
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from pydantic import BaseModel
import pytz
from sqlmodel import select
from pytz import timezone as tz
import jwt

from model import AccessToken, Profesores
from api.deps import SessionDep
from utils import generate_password_reset_token, send_email, generate_reset_password_email, verify_password_reset_token
from core.config import settings

# Constants
SECURITY_CONFIG = {
    "ACCESS_TOKEN_EXPIRE_MINUTES": 60,
    "SECRET_KEY":settings.SECRET_KEY,
    "ALGORITHM": settings.ALGORITHM
    
}

LOCAL_TIMEZONE = tz("America/Guayaquil")
class PasswordRecoveryResponse(BaseModel):
    message: str
    email: str
    success: bool

# Models
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: str | None = None

class UserInDB(BaseModel):
    id: Optional[int] = None
    nombre: str
    email: str
    rol: Optional[str] = None
    hashed_password: str
    estado: Optional[bool] = None
    is_verified: Optional[bool] = None
    
class EmailRequest(BaseModel):
    email: str
    
class NewPassword(BaseModel):
    token: str
    new_password: str 
# Security setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")
router = APIRouter()

# Authentication utilities

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def get_user(session: SessionDep, email: str) -> Optional[UserInDB]:
    """Fetch user from database by email."""
    result = session.exec(
        select(Profesores).where(Profesores.email == email)
    ).first()
    
    if not result:
        return None
        
    return UserInDB(
        id=result.id,
        nombre=result.nombre,
        email=result.email,
        rol=result.rol,
        estado=result.estado,
        is_verified=result.is_verified,
        hashed_password=result.password
    )

def verify_password(plain_password: str, hashed_password: str) -> bool:

    return pwd_context.verify(plain_password, hashed_password)

def authenticate_user(session: SessionDep, username: str, password: str) -> Optional[UserInDB]:
    """Authenticate user credentials."""
    user = session.exec(select(Profesores).where(Profesores.email == username)).first()
    
    if not user or not verify_password(password, user.password):
        return None

    user.is_verified = True
    user.estado = True
    session.add(user)
    session.commit()

    return user

def create_token_payload(data: dict, expires_delta: Optional[timedelta] = None) -> dict:
    """Create JWT payload with expiration."""
    to_encode = data.copy()
    expire = datetime.now(pytz.timezone('America/Guayaquil')) + (
        expires_delta if expires_delta else timedelta(minutes=15)
    )
    to_encode.update({"exp": expire})
    return to_encode, expire

def save_token_to_db(
    session: SessionDep,
    profesor_id: int,
    token: str,
    created_at: datetime
) -> str:
    """Save or update access token in database."""
    now = datetime.now(LOCAL_TIMEZONE)
    existing_token = session.query(AccessToken).filter(
        AccessToken.profesor_id == profesor_id
    ).first()

    if existing_token and now < existing_token.created_at:
        return existing_token.token

    if existing_token:
        session.delete(existing_token)
        session.commit()

    new_token = AccessToken(
        profesor_id=profesor_id,
        token=token,
        created_at=created_at
    )
    session.add(new_token)
    session.commit()
    session.refresh(new_token)
    return new_token.token

def create_access_token(
    session: SessionDep,
    data: dict,
    expires_delta: Optional[timedelta] = None,
    id: Optional[int] = None
) -> str:
    """Create and save JWT access token."""
    payload, expire = create_token_payload(data, expires_delta)
    token = jwt.encode(
        payload,
        SECURITY_CONFIG["SECRET_KEY"],
        algorithm=SECURITY_CONFIG["ALGORITHM"]
    )
    return save_token_to_db(session, id, token, expire)

# Dependencies
async def get_current_user(
    session: SessionDep,
    token: Annotated[str, Depends(oauth2_scheme)]
) -> UserInDB:
    """Validate JWT token and return current user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            SECURITY_CONFIG["SECRET_KEY"],
            algorithms=[SECURITY_CONFIG["ALGORITHM"]]
        )
        email = payload.get("sub")
        if not email:
            raise credentials_exception
    except InvalidTokenError:
        try:
            # Handle expired tokens
            payload = jwt.decode(
                token,
                SECURITY_CONFIG["SECRET_KEY"],
                algorithms=[SECURITY_CONFIG["ALGORITHM"]],
                options={"verify_exp": False}
            )
            if email := payload.get("sub"):
                result = session.exec(
                    select(Profesores).where(Profesores.email == email)
                ).first()
                if result:
                    result.is_verified = False
                    result.estado = False
                    session.add(result)
                    session.commit()
        except Exception:
            pass
        raise credentials_exception

    if user := get_user(session, email):
        return user
    raise credentials_exception

async def get_current_active_user(
    current_user: Annotated[UserInDB, Depends(get_current_user)]
) -> UserInDB:
    """
    Verify if the current user is active and return the user.
    Raises HTTPException if user is not active or not verified.
    """
    if not current_user.estado or not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo o no verificado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user

# Routes
@router.post("/token")
async def login_for_access_token(
    session: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """Login endpoint to obtain access token."""
    if not (user := authenticate_user(session, form_data.username, form_data.password)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        session,
        data={"sub": user.email},
        expires_delta=timedelta(minutes=SECURITY_CONFIG["ACCESS_TOKEN_EXPIRE_MINUTES"]),
        id=user.id
    )
    
    return Token(access_token=access_token)

@router.get("/users/me/", response_model=UserInDB)
async def read_users_me(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)]
) -> UserInDB:
    """Get current user information."""
    return current_user




@router.post("/password-recovery/", response_class=HTMLResponse)
def recover_password(session: SessionDep, email: str = Form(...)):
    """
    Password Recovery
    """
    user = get_user(session=session, email=email)

    if not user:
        # Devolver un HTML indicando que el usuario no existe con estilos
        html_content = """
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Error</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background-color: #f2f2f2;
                }}
                .container {{
                    background: white;
                    padding: 30px;
                    border-radius: 5px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                    text-align: center;
                    max-width: 400px;
                    width: 100%;
                }}
                h2 {{
                    color: #d9534f;
                }}
                p {{
                    color: #555;
                    font-size: 1.1em;
                }}
                a {{
                    text-decoration: none;
                    color: #5bc0de;
                    font-size: 1em;
                    margin-top: 20px;
                    display: inline-block;
                }}
                a:hover {{
                    color: #31b0d5;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Correo no encontrado</h2>
                <p>El usuario con el correo <strong>{email}</strong> no existe en el sistema.</p>
                <a href="/email-recovery-form">Volver</a>
            </div>
        </body>
        </html>
        """.format(email=email)
        return HTMLResponse(content=html_content, status_code=404)

    # Generar el token y enviar el correo
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )
    send_email(
        email_to=user.email,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )

    # Devolver un HTML indicando que el correo fue enviado con estilos
    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Recuperación enviada</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background-color: #f2f2f2;
            }}
            .container {{
                background: white;
                padding: 30px;
                border-radius: 5px;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                text-align: center;
                max-width: 400px;
                width: 100%;
              }}
            h2 {{
                color: rgb(68, 213, 49);
              }}
            p {{
                color: #555;
                font-size: 1.1em;
              }}
            a {{
                text-decoration: none;
                color:rgb(68, 213, 49);
                font-size: 1em;
                margin-top: 20px;
                display: inline-block;
              }}
            a:hover {{
                color:rgb(68, 213, 49);
              }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Correo enviado</h2>
            <p>Hemos enviado un enlace de recuperación al correo <strong>{email}</strong>.</p>
            <a href="/email-recovery-form">Volver</a>
        </div>
    </body>
    </html>
    """.format(email=email)
    return HTMLResponse(content=html_content, status_code=200)
    

@router.get("/password-reset-form/{token}", response_class=HTMLResponse)
async def password_reset_form(token: str):
    try:
        email = verify_password_reset_token(token=token)
    except HTTPException as e:
        return HTMLResponse(
            content=f"<h1>Error</h1><p>{e.detail}</p>", status_code=e.status_code
        )
    
    html_content = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Restablecer Contraseña</title>
    <style>
        body {{
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 400px;
                margin: auto;
                background: white;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }}
            h2 {{
                text-align: center;
                color: #333;
            }}
            label {{
                display: block;
                margin: 10px 0 5px;
            }}
            input[type="password"] {{
                width: 100%;
                padding: 10px;
                margin: 5px 0 20px;
                border: 1px solid #ccc;
                border-radius: 5px;
            }}
            button {{
                width: 100%;
                padding: 10px;
                background-color: #5cb85c;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
            }}
            button:hover {{
                background-color: #4cae4c;
            }}
            .error {{
                color: red;
                font-size: 0.9em;
            }}
    </style>
    <script>
        function validateForm() {{
            const newPassword = document.getElementById('new_password').value;
            const confirmPassword = document.getElementById('confirm_password').value;
            const errorMessage = document.getElementById('error_message');

            // Validar longitud mínima de 8 caracteres
            if (newPassword.length < 8) {{
                errorMessage.textContent = 'La contraseña debe tener al menos 8 caracteres.';
                return false;
            }}

            // Validar que contenga al menos una letra minúscula
            if (!/[a-z]/.test(newPassword)){{
                errorMessage.textContent = 'La contraseña debe contener al menos una letra minúscula.';
                return false;
            }}

            // Validar que contenga al menos una letra mayúscula
            if (!/[A-Z]/.test(newPassword)) {{
                errorMessage.textContent = 'La contraseña debe contener al menos una letra mayúscula.';
                return false;
            }}

            // Validar que contenga al menos un número
            if (!/[0-9]/.test(newPassword)) {{
                errorMessage.textContent = 'La contraseña debe contener al menos un número.';
                return false;
            }}

            // Validar que las contraseñas coincidan
            if (newPassword !== confirmPassword) {{
                errorMessage.textContent = 'Las contraseñas no coinciden.';
                return false;
            }}

            // Si todo está bien, limpiar el mensaje de error y permitir el envío del formulario
            errorMessage.textContent = '';
            return true;
        }}
    </script>
</head>
<body>
    <div class="container">
        <h2>Restablecer tu contraseña</h2>
        <form action="/auth/reset-password" method="post" onsubmit="return validateForm()">
            <input type="hidden" name="token" value="{token}" />
            <label for="new_password">Nueva Contraseña:</label>
            <input type="password" id="new_password" name="new_password" required />
            <label for="confirm_password">Confirmar Contraseña:</label>
            <input type="password" id="confirm_password" required />
            <div id="error_message" class="error"></div>
            <button type="submit">Restablecer Contraseña</button>
        </form>
    </div>
</body>
</html>
    """
    return HTMLResponse(content=html_content, status_code=200)


@router.get("/email-recovery-form", response_class=HTMLResponse)
async def email_recovery_form():
    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Recuperación de Contraseña</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 20px;
            }
            .container {
                max-width: 400px;
                margin: auto;
                background: white;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }
            h2 {
                text-align: center;
                color: #333;
            }
            label {
                display: block;
                margin: 10px 0 5px;
            }
            input[type="email"] {
                width: 100%;
                padding: 10px;
                margin: 5px 0 20px;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
            button {
                width: 100%;
                padding: 10px;
                background-color: #5cb85c;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
            }
            button:hover {
                background-color: #4cae4c;
            }
            .error {
                color: red;
                font-size: 0.9em;
            }
        </style>
        <script>
    async function submitForm(event) {
        event.preventDefault();
        const emailInput = document.getElementById('email').value;
        const errorMessage = document.getElementById('error_message');
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        const submitButton = document.getElementById('submit_button');

        if (!emailPattern.test(emailInput)) {
            errorMessage.textContent = 'Por favor, introduce un correo electrónico válido.';
            return false;
        }
        errorMessage.textContent = '';
        submitButton.disabled = true;
        submitButton.textContent = 'Enviando solicitud. Por favor, espere.';

        
    }
</script>
    </head>
    <body>
        <div class="container">
    <h2>Recuperar Contraseña</h2>
        <form action="/auth/password-recovery" method="post">
            <label for="email">Correo Electrónico:</label>
            <input type="email" id="email" name="email" required />
            <button id="submit_button" type="submit">Enviar Correo de Recuperación</button>
        </form>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


@router.post("/reset-password/", response_class=HTMLResponse)
def reset_password(
    session: SessionDep,
    token: str = Form(...),
    new_password: str = Form(...)
):
    """
    Reset password
    """
    email = verify_password_reset_token(token=token)
    if not email:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Error</title>
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        background-color: #f4f4f4;
                        margin: 0;
                        padding: 0;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                    }
                    .container {
                        background: #fff;
                        padding: 20px;
                        border-radius: 8px;
                        box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                        text-align: center;
                    }
                    h1 {
                        color: #e74c3c;
                    }
                    p {
                        color: #555;
                        font-size: 1.1em;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Error</h1>
                    <p>Invalid token. Please try again.</p>
                </div>
            </body>
            </html>
            """,
            status_code=400,
        )
    
    user = session.exec(
        select(Profesores).where(Profesores.email == email)
    ).first()

    if not user:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Error</title>
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        background-color: #f4f4f4;
                        margin: 0;
                        padding: 0;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                    }
                    .container {
                        background: #fff;
                        padding: 20px;
                        border-radius: 8px;
                        box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                        text-align: center;
                    }
                    h1 {
                        color: #e74c3c;
                    }
                    p {
                        color: #555;
                        font-size: 1.1em;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Error</h1>
                    <p>The user with this email does not exist in the system.</p>
                </div>
            </body>
            </html>
            """,
            status_code=404,
        )
    elif not user.estado:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Error</title>
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        background-color: #f4f4f4;
                        margin: 0;
                        padding: 0;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                    }
                    .container {
                        background: #fff;
                        padding: 20px;
                        border-radius: 8px;
                        box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                        text-align: center;
                    }
                    h1 {
                        color: #e74c3c;
                    }
                    p {
                        color: #555;
                        font-size: 1.1em;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Error</h1>
                    <p>Inactive user. Please contact support.</p>
                </div>
            </body>
            </html>
            """,
            status_code=400,
        )

    hashed_password = get_password_hash(password=new_password)
    user.password = hashed_password
    session.add(user)
    session.commit()
    
    return HTMLResponse(
        content="""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Success</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background-color: #f4f4f4;
                    margin: 0;
                    padding: 0;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                }
                .container {
                    background: #fff;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                    text-align: center;
                }
                h1 {
                    color: #2ecc71;
                }
                p {
                    color: #555;
                    font-size: 1.1em;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Success</h1>
                <p>Your password has been reset successfully.</p>
            </div>
        </body>
        </html>
        """,
        status_code=200,
    )