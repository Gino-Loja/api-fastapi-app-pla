import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import emails  # type: ignore
import jwt
from jinja2 import Template
from jwt.exceptions import InvalidTokenError
from sqlmodel import select

from core.config import settings
from core.db import engine
from model import Planificacion_Profesor, Planificaciones, Profesores

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from datetime import datetime, timedelta
from api.deps import SessionDep, get_db
from pytz import timezone as tz
from sqlmodel import Session, select

@dataclass
class EmailData:
    html_content: str
    subject: str

DIAS = {
    'Monday': 'Lunes',
    'Tuesday': 'Martes',
    'Wednesday': 'Miércoles',
    'Thursday': 'Jueves',
    'Friday': 'Viernes',
    'Saturday': 'Sábado',
    'Sunday': 'Domingo'
}

MESES = {
    'January': 'Enero',
    'February': 'Febrero',
    'March': 'Marzo',
    'April': 'Abril',
    'May': 'Mayo',
    'June': 'Junio',
    'July': 'Julio',
    'August': 'Agosto',
    'September': 'Septiembre',
    'October': 'Octubre',
    'November': 'Noviembre',
    'December': 'Diciembre'
}

def formatear_fecha(fecha):
    if isinstance(fecha, str):
        fecha_datetime = datetime.fromisoformat(fecha.replace('Z', '+00:00'))
        fecha_datetime = fecha_datetime.astimezone(ZoneInfo("America/Guayaquil"))
    else:
        fecha_datetime = fecha.astimezone(ZoneInfo("America/Guayaquil"))
    
    # Obtener el formato en inglés primero
    fecha_eng = fecha_datetime.strftime('%A, %d de %B de %Y hasta las %I:%M %p')
    
    # Traducir al español
    for eng, esp in DIAS.items():
        fecha_eng = fecha_eng.replace(eng, esp)
    for eng, esp in MESES.items():
        fecha_eng = fecha_eng.replace(eng, esp)
    
    return fecha_eng
def render_email_template(*, template_name: str, context: dict[str, Any]) -> str:
    template_str = (
        Path(__file__).parent / "email-templates" / "build" / template_name
    ).read_text()
    html_content = Template(template_str).render(context)
    return html_content


def send_email(
    *,
    email_to: str,
    subject: str = "",
    html_content: str = "",
) -> None:
    """
    Send email using Gmail SMTP server.
    
    Note: For Gmail, you need to:
    1. Enable 2-Factor Authentication
    2. Generate an App Password for use with this application
    """
    #assert settings.emails_enabled, "no provided configuration for email variables"
    
    message = emails.Message(
        subject=subject,
        html=html_content,
        mail_from=('no-reply', settings.EMAILS_FROM_EMAIL),
    )
    
    

    # Configuración específica para Gmail
    
    smtp_options = {
        "host": settings.SMTP_HOST,  # Servidor SMTP de Gmail
        "port": settings.SMTP_PORT,               # Puerto para TLS
        "tls": True,              # Habilitar TLS
        "user": settings.EMAILS_FROM_EMAIL,  # Tu dirección de Gmail
        "password": settings.SMTP_PASSWORD,  # Tu contraseña de aplicación
        "timeout": 10
    }
    
    try:
        
        response = message.send(to=email_to, smtp=smtp_options)
        
        if response.status_code != 250:
            logger.error(f"Failed to send email. Status code: {response.status_code}")
            logger.error(f"Error: {response.error}")
        else:
            logger.info("Email sent successfully")
            
        logger.info(f"Send email result: {response}")
        
    except Exception as e:
        logger.error(f"Exception while sending email: {str(e)}")
        raise
    
    
    
def generate_reset_password_email(email_to: str, email: str, token: str) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Password recovery for user {email}"
    link = f"{settings.BACKEND_URL}auth/password-reset-form/{token}"
    html_content = render_email_template(
        template_name="reset_password.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "username": email,
            "email": email_to,
            "valid_hours": settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS,
            "link": link,
        },
    )
    return EmailData(html_content=html_content, subject=subject)


def render_email_template_info(subject:str, template_name: str, email_to: str, message: str) -> EmailData:
    
    template_str = (
        Path(__file__).parent / "email-templates" / "build" / template_name
    ).read_text()
    html_content = render_email_template(
        template_name="info_docente.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "username": settings.EMAILS_FROM_EMAIL,
            "email": email_to,
            "message": message,
        },
    )
    return EmailData(html_content=html_content, subject=subject)




def generate_password_reset_token(email: str) -> str:
    delta = timedelta(hours=settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS)
    now = datetime.now(timezone.utc)
    expires = now + delta
    exp = expires.timestamp()
    encoded_jwt = jwt.encode(
        {"exp": exp, "nbf": now, "sub": email},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def verify_password_reset_token(token: str) -> str | None:
    try:
        decoded_token = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return str(decoded_token["sub"])
    except InvalidTokenError:
        return None
    
    


def check_and_send_reminders() :
    with Session(engine) as session:  # Crear una sesión manualmente

        tasks = session.query(Planificaciones).all()
        now = datetime.now(tz("America/Guayaquil"))

        for task in tasks:
            time_until_deadline = task.deadline - now
            
            fecha_formateada = formatear_fecha(task.deadline)


            # Enviar recordatorio 1 día antes
            if timedelta(days=1) <= time_until_deadline < timedelta(days=1, hours=1):
                
                email = render_email_template_info(
                    template_name="info_docente.html",
                    subject=f"Recordatorio: {task.title}",
                    email_to=task.professor_email,
                    message=f"Le recordamos que la tarea {task.title} tiene una fecha límite el {fecha_formateada}."
                )
                send_email(
                    email_to=task.professor_email,
                    subject=email.subject,
                    html_content=email.html_content,
                )

            # Enviar recordatorio 3 horas antes
            if timedelta(hours=3) <= time_until_deadline < timedelta(hours=3, minutes=1):
                email =  render_email_template_info(
                        template_name="info_docente.html",

                        subject=f"Último recordatorio: {task.title}",
                        email_to=task.professor_email,
                        message=f"La tarea {task.title} tiene una fecha límite en 3 horas ({fecha_formateada})."
                    )
                send_email(
                        email_to=task.professor_email,
                        subject=email.subject,
                        html_content=email.html_content,
                    )
            
                
            if timedelta(hours=1) <= time_until_deadline < timedelta(hours=1, minutes=1):
                email = render_email_template_info(
                    template_name="info_docente.html",

                    subject=f"Último recordatorio: {task.title}",
                    email_to=task.professor_email,
                    message=f"La tarea {task.title} tiene una fecha límite en 1 horas ({fecha_formateada})."
                )
                send_email(
                    email_to=task.professor_email,
                    subject=email.subject,
                    html_content=email.html_content,
                )


def check_and_update_states():
    """
    Verifica las planificaciones con fecha_subida pasada y actualiza su estado a 'no_entregado'
    solo si están en estado 'pendiente'.
    """
    try:
        print("Actualizando estados de planificaciones...")
        with Session(engine) as session:
            now = datetime.now(tz("America/Guayaquil"))

            # Obtener todas las planificaciones que están en estado "pendiente"
            statement = select(Planificacion_Profesor).where(
                Planificacion_Profesor.estado == "pendiente"
            )
            planificaciones = session.exec(statement).all()

            for planificacion in planificaciones:
                # Obtener los detalles de la planificación
                planificacion_detalle = session.exec(
                    select(Planificaciones).where(Planificaciones.id == planificacion.planificacion_id)
                ).one_or_none()

                # Verificar si la planificación tiene fecha_subida pasada
                if planificacion_detalle and planificacion_detalle.fecha_subida < now:
                    # Cambiar el estado a 'no_entregado'
                    planificacion.estado = "no_entregado"
                    session.add(planificacion)

                    # Notificar al profesor
                    profesor = session.exec(
                        select(Profesores).where(Profesores.id == planificacion_detalle.profesor_id)
                    ).one_or_none()

                    if profesor:
                        fecha_formateada = formatear_fecha(planificacion_detalle.fecha_subida)

                        email = render_email_template_info(
                            template_name='info_docente.html',
                            subject=f"Notificación: Planificación atrasada - {planificacion_detalle.titulo}",
                            email_to=profesor.email,
                            message=(
                                f"La planificación {planificacion_detalle.titulo} marcada para el "
                                f"{fecha_formateada} se encuentra atrasada. "
                                "Por favor, comuníquese con el docente administrador."
                            )
                        )
                        send_email(
                            email_to=profesor.email,
                            subject=email.subject,
                            html_content=email.html_content,
                        )

            # Confirmar los cambios en la base de datos
            session.commit()

    except Exception as e:
        print(f"Error al actualizar estados de planificaciones: {e}")