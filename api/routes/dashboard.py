from datetime import datetime
import ftplib
import io
import os
from fastapi import APIRouter, Body, Depends, File, Form, Request, Response, HTTPException, UploadFile, status
from fastapi.encoders import jsonable_encoder
from typing import Any, List, Optional
from fastapi.responses import FileResponse
from sqlalchemy import String, alias, cast, extract, text
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



@router.get("/metricas/total-planificaciones-asignadas", response_description="Obtener el total de planificaciones asignadas")
async def get_total_planificaciones_asignadas(session: SessionDep) -> Any:
    try:
        statement = select(func.count()).select_from(Planificacion_Profesor)
        total = session.exec(statement).one()
        return {"total_planificaciones_asignadas": total}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener el total de planificaciones asignadas"
        ) from e
        
@router.get("/metricas/planificaciones-por-area", response_description="Obtener planificaciones por área")
async def get_planificaciones_por_area(session: SessionDep) -> Any:
    try:
        statement = (
            select(Areas.nombre, func.count().label("total_planificaciones"))
            .join(Asignaturas, Areas.id == Asignaturas.area_id)
            .join(Planificaciones, Asignaturas.id == Planificaciones.asignaturas_id)
            .group_by(Areas.nombre)
        )
        results = session.exec(statement).all()

        # Convertir las filas a una lista de diccionarios
        planificaciones = [{"nombre": row[0], "total_planificaciones": row[1]} for row in results]

        return {"planificaciones_por_area": planificaciones}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener las métricas de planificaciones por área"
        ) from e
        
        
@router.get("/metricas/planificaciones-aprobadas-vs-pendientes", response_description="Obtener planificaciones aprobadas vs pendientes")
async def get_planificaciones_aprobadas_vs_pendientes(session: SessionDep) -> Any:
    try:
        statement = (
            select(Planificacion_Profesor.estado, func.count().label("total"))
            .where(Planificacion_Profesor.estado.in_(["aprobado", "pendiente"]))
            .group_by(Planificacion_Profesor.estado)
        )
        results = session.exec(statement).all()
        
        if  len(results) == 0:
            return {"planificaciones_aprobadas_vs_pendientes": {"aprobado": 0, "pendiente": 0}}
        
        return {"planificaciones_aprobadas_vs_pendientes": {result.estado: result.total for result in results}}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener las métricas de planificaciones aprobadas vs pendientes"
        ) from e
        
@router.get("/metricas/profesores-con-mas-planificaciones-atrasadas", response_description="Obtener profesores con más planificaciones atrasadas")
async def get_profesores_con_mas_planificaciones_atrasadas(session: SessionDep):
    try:
        statement = (
            select(Profesores.nombre, func.count().label("total_atrasadas"))
            .join(Planificaciones, Profesores.id == Planificaciones.profesor_id)
            .join(Periodo, Planificaciones.periodo_id == Periodo.id)
            .join(Planificacion_Profesor, Planificaciones.id == Planificacion_Profesor.planificacion_id)  # Asegura la relación
            .where(Planificacion_Profesor.estado == "atrasado")
            .group_by(Profesores.nombre)
            .order_by(func.count().desc())
        )
        results = session.exec(statement).all()
        
       

        # Convertir los resultados en una lista de diccionarios
        profesores_atrasados = [{"nombre": row[0], "total_atrasadas": row[1]} for row in results]

        return {"profesores_con_mas_planificaciones_atrasadas": profesores_atrasados}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener los profesores con más planificaciones atrasadas"
        ) from e

@router.get("/metricas/planificaciones-por-periodo", response_description="Obtener planificaciones por periodo")
async def get_planificaciones_por_periodo(session: SessionDep) -> Any:
    try:
        statement = (
            select(Periodo.nombre, func.count().label("total_planificaciones"))
            .join(Planificaciones, Periodo.id == Planificaciones.periodo_id)
            .group_by(Periodo.nombre)
        )
        results = session.exec(statement).all()

        # Convertir a un formato serializable
        planificaciones_por_periodo = [
            {"nombre_periodo": row.nombre, "total_planificaciones": row.total_planificaciones}
            for row in results
        ]

        return {"planificaciones_por_periodo": planificaciones_por_periodo}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener las métricas de planificaciones por periodo"
        ) from e

#mis planificaciones por estado
@router.get("/metricas/mis-planificaciones-por-estado/{profesor_id}", response_description="Obtener las planificaciones de un profesor por estado")
async def get_mis_planificaciones_por_estado(
    session: SessionDep, 
    profesor_id: int, 
    periodo_id: int  # Nuevo parámetro: periodo_id
) :
    try:
        # Consulta para obtener las planificaciones del profesor filtradas por periodo_id
        statement = (
            select(Planificacion_Profesor.estado, func.count().label("total"))
            .join(Planificaciones, Planificacion_Profesor.planificacion_id == Planificaciones.id)
            .where(
                Planificaciones.profesor_id == profesor_id,
                Planificaciones.periodo_id == periodo_id  # Filtro por periodo_id
            )
            .group_by(Planificacion_Profesor.estado)
        )
        results = session.exec(statement).all()

        # Formatear los resultados como un diccionario {estado: total}
        return {"mis_planificaciones_por_estado": {result.estado: result.total for result in results}}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener las métricas de planificaciones por estado"
        ) from e
        
        
@router.get("/metricas/mis-planificaciones-atrasadas/{profesor_id}", response_description="Obtener las planificaciones atrasadas de un profesor")
async def get_mis_planificaciones_atrasadas(session: SessionDep,
                                            profesor_id: int,
                                            periodo_id: int  # Nuevo parámetro: periodo_id
) :
    try:
        statement = (
            select(func.count())
            .select_from(Planificaciones)
            .join(Periodo, Planificaciones.periodo_id == Periodo.id)
            .where(Planificaciones.profesor_id == profesor_id,
                   Planificaciones.fecha_subida > Periodo.fecha_fin,
                   Planificaciones.periodo_id == periodo_id)
        )
        total = session.exec(statement).one()
        return {"mis_planificaciones_atrasadas": total}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener el total de planificaciones atrasadas"
        ) from e
        
@router.get("/metricas/mis-planificaciones-proximas-a-vencer/{profesor_id}", response_description="Obtener las planificaciones próximas a vencer de un profesor")
async def get_mis_planificaciones_proximas_a_vencer(session: SessionDep, profesor_id: int,periodo_id: int):
    try:
        # Consulta corregida
        statement = (
            select(Planificaciones.titulo, Planificaciones.fecha_subida, Asignaturas.nombre, Asignaturas.codigo)
            .join(Asignaturas, Planificaciones.asignaturas_id == Asignaturas.id)
            .join(Periodo, Planificaciones.periodo_id == Periodo.id)
            .join(Planificacion_Profesor, Planificaciones.id == Planificacion_Profesor.planificacion_id)
            .where(
                Planificaciones.profesor_id == profesor_id,  # Ajuste en la relación
                Planificaciones.periodo_id == periodo_id,
                
                Planificaciones.fecha_subida.between(
                    func.now(), func.now() + text("INTERVAL '7 days'")
                ),
                Planificacion_Profesor.estado == "pendiente"
            )
        )
        results = session.exec(statement).all()

        # Convertir los resultados a una lista de diccionarios
        planificaciones = [
            {
            "titulo": row.titulo,
            "fecha_subida": row.fecha_subida,
            "asignatura": row.nombre,
            "codigo": row.codigo,
            
            } for row in results
        ]

        return {"mis_planificaciones_proximas_a_vencer": planificaciones}
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener las planificaciones próximas a vencer"
        ) from e

        
@router.get("/planificaciones-asignadas/{profesor_id}", response_description="Obtener las planificaciones asignadas a un profesor con áreas y asignaturas")
async def get_planificaciones_asignadas(session: SessionDep, profesor_id: int, periodo_id: int) :
    try:
        # Consulta para obtener las planificaciones asignadas al profesor, junto con las áreas y asignaturas
        statement = (
            select(
                Planificaciones.id.label("id_planificacion"),
                Planificaciones.titulo,
                Planificaciones.descripcion,
                Planificaciones.fecha_subida,
                Planificacion_Profesor.estado,
                Asignaturas.nombre.label("nombre_asignatura"),
                Areas.nombre.label("nombre_area")
            )
            .join(Asignaturas, Planificaciones.asignaturas_id == Asignaturas.id)
            .join(Periodo, Planificaciones.periodo_id == Periodo.id)
            .join(Areas, Asignaturas.area_id == Areas.id)
            .join(Planificacion_Profesor, Planificaciones.id == Planificacion_Profesor.planificacion_id)
            .where(Planificaciones.profesor_id == profesor_id, Planificaciones.periodo_id == periodo_id)
        )

        results = session.exec(statement).all()

        # Formatear los resultados en una lista de diccionarios
        planificaciones = [
            {
                "id_planificacion": result.id_planificacion,
                "titulo": result.titulo,
                "descripcion": result.descripcion,
                "fecha_subida": result.fecha_subida,
                "estado": result.estado,
                "nombre_asignatura": result.nombre_asignatura,
                "nombre_area": result.nombre_area,
            }
            for result in results
        ]

        return planificaciones

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener las planificaciones asignadas"
        ) from e
        
        
@router.get("/asignaturas-con-planificaciones/{profesor_id}/{periodo_id}", response_description="Obtener las asignaturas con el número de planificaciones asignadas a un profesor en un periodo específico")
async def get_asignaturas_con_planificaciones(
    session: SessionDep, 
    profesor_id: int, 
    periodo_id: int
) :
    try:
        # Consulta para obtener las asignaturas con el número de planificaciones asignadas al profesor en el periodo especificado
        statement = (
            select(
                Asignaturas.id.label("id_asignatura"),
                Asignaturas.nombre.label("nombre_asignatura"),
                func.count(Planificaciones.id).label("total_planificaciones")
            )
            .join(Planificaciones, Asignaturas.id == Planificaciones.asignaturas_id)
            .join(Planificacion_Profesor, Planificaciones.id == Planificacion_Profesor.planificacion_id)
            .where(
                Planificaciones.profesor_id == profesor_id,
                Planificaciones.periodo_id == periodo_id
            )
            .group_by(Asignaturas.id, Asignaturas.nombre, Asignaturas.codigo)
        )

        results = session.exec(statement).all()

        # Formatear los resultados en una lista de diccionarios
        asignaturas = [
            {
                "id_asignatura": result.id_asignatura,
                "nombre_asignatura": result.nombre_asignatura,
                "total_planificaciones": result.total_planificaciones,
            }
            for result in results
        ]

        return asignaturas

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener las asignaturas con planificaciones asignadas"
        ) from e