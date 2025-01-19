from datetime import datetime
import ftplib
import io
import os
from fastapi import APIRouter, Body, Depends, File, Form, Request, Response, HTTPException, UploadFile, status
from fastapi.encoders import jsonable_encoder
from typing import Any, List, Optional
from fastapi.responses import FileResponse
from sqlalchemy import String, alias, cast, extract
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from zoneinfo import ZoneInfo
from sqlmodel import SQLModel, select , func
from model import Areas, Comentarios, Comentarios_Dto, areas_profesor, Asignaturas, Periodo, Planificacion_Profesor, Planificaciones, Profesores
from api.deps import SessionDep, sender_email
from sqlalchemy.orm import aliased
from ftplib import FTP
import io
from typing import Optional
from pytz import timezone as tz
from utils import render_email_template_info, send_email

router = APIRouter()
class Total_profesores(SQLModel):
    #__tablename__ = "profesores"
  
    total: int


@router.get("/areas/count", response_description="Obtener el total de áreas")
async def get_total_areas(session: SessionDep) -> Any:
    try:
        statement = select(func.count(Areas.id).label("total_areas"))
        result = session.exec(statement).one()
        return {"total_areas": result}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener el total de áreas"
        ) from e


@router.get("/profesores/count", response_description="Obtener el total de profesores", response_model=Total_profesores)
async def get_total_professors(session: SessionDep) -> Any:
    statement = select(func.count().label("total")).select_from(Profesores)
    result = session.exec(statement).one()
    return  {"total": result}


@router.get("/asignaturas/count", response_description="Obtener el total de asignaturas")
async def get_total_asignaturas(session: SessionDep) -> Any:
    try:
        # Consulta para contar la cantidad total de asignaturas
        statement = select(func.count(Asignaturas.id).label("total_asignaturas"))
        result = session.exec(statement).one()
        print(result)
        
        return {"total_asignaturas": result}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener el total de asignaturas"
        ) from e
    
    
@router.get("/planificaciones/count-by-estado", response_description="Obtener la cantidad de planificaciones por estado")
async def get_planificaciones_count_by_estado(session: SessionDep) -> Any:
    try:
        # Consulta para contar planificaciones agrupadas por estado
        statement = (
            select(Planificacion_Profesor.estado, func.count(Planificacion_Profesor.id).label("total"))
            .group_by(Planificacion_Profesor.estado)
        )
        results = session.exec(statement).all()

        # Formatear los resultados como un diccionario
        estado_counts = {result.estado: result.total for result in results}

        return estado_counts
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener las planificaciones por estado"
        ) from e


@router.get("/docentes/atrasados", response_description="Obtener lista de docentes con planificaciones atrasadas")
async def get_docentes_atrasados(session: SessionDep) -> Any:
    try:
        # Alias de tablas para facilitar la consulta
        profesores_alias = aliased(Profesores)
        planificaciones_alias = aliased(Planificaciones)
        periodos_alias = aliased(Periodo)

        # Consulta para obtener docentes con planificaciones atrasadas
        statement = (
            select(
                profesores_alias.id,
                profesores_alias.nombre,
                planificaciones_alias.titulo,
                planificaciones_alias.fecha_subida,
                periodos_alias.nombre.label("nombre_periodo"),
                periodos_alias.fecha_fin.label("fecha_limite")
            )
            .join(planificaciones_alias, planificaciones_alias.profesor_id == profesores_alias.id)
            .join(periodos_alias, planificaciones_alias.periodo_id == periodos_alias.id)
            .where(planificaciones_alias.fecha_subida > periodos_alias.fecha_fin)
        )

        results = session.exec(statement).all()

        # Formatear los resultados
        docentes_atrasados = [
            {
                "id_profesor": result.id,
                "nombre_profesor": result.nombre,
                "titulo_planificacion": result.titulo,
                "fecha_subida": result.fecha_subida,
                "nombre_periodo": result.nombre_periodo,
                "fecha_limite": result.fecha_limite,
            }
            for result in results
        ]

        return {"docentes_atrasados": docentes_atrasados}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener docentes con planificaciones atrasadas"
        ) from e


@router.get("/docentes/por-estado", response_description="Obtener lista de docentes según el estado de la planificación")
async def get_docentes_por_estado(session: SessionDep, estado: Optional[str] = None) -> Any:
    """
    Endpoint para obtener la lista de docentes según el estado de sus planificaciones.

    Parámetros:
    - estado (opcional): Estado de la planificación (e.g., "aprobado", "pendiente", "revisado", etc.).
      Si no se especifica, devuelve todos los docentes con planificaciones en cualquier estado.

    Retorna:
    - Una lista de docentes con planificaciones que coinciden con el estado especificado o con cualquier estado.
    """
    try:
        # Alias de tablas para facilitar la consulta
        profesores_alias = aliased(Profesores)
        planificaciones_profesor_alias = aliased(Planificacion_Profesor)
        planificaciones_alias = aliased(Planificaciones)

        # Construir la consulta base
        statement = (
            select(
                profesores_alias.id,
                profesores_alias.nombre,
                planificaciones_alias.titulo,
                planificaciones_profesor_alias.estado,
                planificaciones_profesor_alias.fecha_de_actualizacion
            )
            .join(planificaciones_alias, planificaciones_alias.profesor_id == profesores_alias.id)
            .join(planificaciones_profesor_alias, planificaciones_profesor_alias.planificacion_id == planificaciones_alias.id)
        )

        # Agregar filtro de estado si se proporciona
        if estado:
            statement = statement.where(planificaciones_profesor_alias.estado == estado)

        # Ejecutar la consulta
        results = session.exec(statement).all()

        # Formatear los resultados
        docentes = [
            {
                "id_profesor": result.id,
                "nombre_profesor": result.nombre,
                "titulo_planificacion": result.titulo,
                "estado_planificacion": result.estado,
                "fecha_actualizacion": result.fecha_de_actualizacion,
            }
            for result in results
        ]

        return {"estado": estado if estado else "todos", "docentes": docentes}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener la lista de docentes por estado"
        ) from e



@router.get("/docentes/estado", response_description="Obtener lista de docentes por estado")
async def get_usuarios_por_estado(session: SessionDep, estado: Optional[str] = None) -> Any:
    """
    Endpoint para obtener la lista de usuarios según su estado.

    Parámetros:
    - estado: "activo" o "inactivo". Si no se pasa, se devuelven todos los usuarios.

    Retorna:
    - Una lista de usuarios filtrada por el estado especificado.
    """
    try:
        # Construir la consulta base
        statement = select(Profesores.id, Profesores.nombre, Profesores.email, Profesores.estado)

        # Filtrar por estado si se especifica
        if estado:
            if estado.lower() == "activo":
                statement = statement.where(Profesores.estado == True)
            elif estado.lower() == "inactivo":
                statement = statement.where(Profesores.estado == False)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Estado inválido. Los valores permitidos son 'activo' o 'inactivo'."
                )

        # Ejecutar la consulta
        results = session.exec(statement).all()

        # Formatear los resultados
        usuarios = [
            {
                "id_usuario": result.id,
                "nombre": result.nombre,
                "email": result.email,
                "estado_docente": "activo" if result.estado else "inactivo",
            }
            for result in results
        ]

        return {"estado": estado or "todos", "usuarios": usuarios}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener la lista de usuarios"
        ) from e
