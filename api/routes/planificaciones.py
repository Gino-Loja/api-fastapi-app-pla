
from fastapi import APIRouter, Body, Depends, Request, Response, HTTPException, status
from fastapi.encoders import jsonable_encoder
from typing import Any, List
from sqlalchemy import alias
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from sqlmodel import select , func
from model import Areas, Areas_Profesor, Asignaturas, Periodo, Planificacion_Profesor, Planificaciones, Profesores
from api.deps import SessionDep, sender_email
from sqlalchemy.orm import aliased

router = APIRouter()

# Crear un nuevo periodo

# Obtener todos los periodos


@router.post("/create", response_description="Agregar nueva planificación", status_code=status.HTTP_201_CREATED)
async def create_planificacion(planificacion: Planificaciones, session: SessionDep) -> Any:
    try:
        # Verificar si el usuario (profesor) existe y obtener su email


        profesor = select(Profesores).where(Profesores.id == planificacion.profesor_id)

        fechtprofesor = session.exec(profesor).one_or_none()


        asignatura = select(Asignaturas).where(Asignaturas.id == planificacion.asignaturas_id)
        fechtAsignatura = session.exec(asignatura).one_or_none()
        
        
        if not fechtprofesor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario con id {planificacion.profesor_id} no encontrado"
            )
        
       
        # Verificar si el usuario tiene un email asociado
        sender_email(fechtprofesor.email,
                    "Planificación de asignaturas",
                    f"Se ha creado una nueva planificación para la asignatura {fechtAsignatura.nombre} con fecha de entrega {planificacion.fecha_subida}")
        # Crear una nueva instancia del modelo Planificacion
        
        planificaciones_data = jsonable_encoder(planificacion)

        new_planificacion = Planificaciones(**planificaciones_data)
        
        # Guardar en la base de datos
        session.add(new_planificacion)
        session.commit()
        session.refresh(new_planificacion)
        
        # Retornar la planificación creada junto con el email del usuario
        return new_planificacion

    except SQLAlchemyError as e:
        # Si ocurre un error, revertir cambios
        print(e)
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al guardar la planificación en la base de datos, talvez la asignatura no esta asignada a ningún area"
        ) from e


@router.put("/update/{planificacion_id}", response_description="Actualizar una planificación", status_code=status.HTTP_200_OK)
async def update_planificacion(planificacion_id: int, updated_data: Planificaciones, session: SessionDep) -> Any:
    try:
        # Verificar si la planificación existe
        existing_planificacion = session.exec(
            select(Planificaciones).where(Planificaciones.id == planificacion_id)
        ).one_or_none()

        if not existing_planificacion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la planificación con ID {planificacion_id}"
            )
        
        profesor = select(Profesores).where(Profesores.id == updated_data.profesor_id)

        fechtprofesor = session.exec(profesor).one_or_none()


        asignatura = select(Asignaturas).where(Asignaturas.id == updated_data.asignaturas_id)
        fechtAsignatura = session.exec(asignatura).one_or_none()
        
        
        if not fechtprofesor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario con id {updated_data.profesor_id} no encontrado"
            )

        # Actualizar los campos de la planificación existente
        updated_fields = updated_data.dict(exclude_unset=True)  # Solo incluir campos enviados
        for key, value in updated_fields.items():
            setattr(existing_planificacion, key, value)

        sender_email(fechtprofesor.email,
                    "Actualizacion de planificación de asignaturas",
                    f"Se ha Actualizado la planificación para la asignatura {fechtAsignatura.nombre} con fecha de entrega de {updated_data.fecha_subida}")

        session.add(existing_planificacion)
        session.commit()
        session.refresh(existing_planificacion)

        return {"message": "Planificación actualizada correctamente", "data": existing_planificacion}

    except SQLAlchemyError as e:
        session.rollback()
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al guardar la planificación en la base de datos, talvez la asignatura no esta asignada a ningún area"
        ) from e



@router.get("/search/", response_description="Listar todas las planificaciones", response_model=List[Any])
async def get_all_planificaciones(
    query: int, 
    session: SessionDep
) -> Any:
    try:
        # Realizamos el join entre todas las tablas necesarias
        query = (
            select(
                Planificaciones,
                Profesores.nombre.label("profesor_nombre"),
                Asignaturas.nombre.label("asignatura_nombre"),
                Periodo.nombre.label("periodo_nombre"),
                # Información del profesor aprobador
                Planificacion_Profesor.profesor_aprobador_id,
                # Información del profesor revisor
                Planificacion_Profesor.profesor_revisor_id,
                # Información del área
                Areas.id.label("area_id"),
                Areas.nombre.label("area_nombre"),
                Areas.codigo.label("area_codigo"),
                # Información adicional de la planificación
                Planificacion_Profesor.fecha_de_actualizacion,
                Planificacion_Profesor.estado,
                Planificacion_Profesor.archivo,
                Planificacion_Profesor.comentario
            )
            .join(Profesores, Planificaciones.profesor_id == Profesores.id)
            .join(Asignaturas, Planificaciones.asignaturas_id == Asignaturas.id)
            .join(Periodo, Planificaciones.periodo_id == Periodo.id)
            .join(Areas, Asignaturas.area_id == Areas.id)
            .join(
                Planificacion_Profesor,
                Planificaciones.id == Planificacion_Profesor.planificacion_id
            )
            # Join para obtener la información del profesor revisor
            .join(
                Areas_Profesor,
                Planificacion_Profesor.profesor_revisor_id == Areas_Profesor.id,
                isouter=True
            )
            .where(Planificaciones.periodo_id == query)
        )
        
        # Ejecutar la consulta y obtener los resultados
        planificaciones = session.exec(query).all()

        # Obtener los IDs de profesores aprobadores y revisores
        profesor_aprobador_ids = [p[4] for p in planificaciones if p[4] is not None]  # índice 4 es profesor_aprobador_id
        profesor_revisor_ids = [p[5] for p in planificaciones if p[5] is not None]    # índice 5 es profesor_revisor_id

        # Consultar nombres de profesores aprobadores
        aprobadores = {}
        if profesor_aprobador_ids:
            query_aprobadores = select(Profesores).where(Profesores.id.in_(profesor_aprobador_ids))
            aprobadores = {p.id: p.nombre for p in session.exec(query_aprobadores)}

        # Consultar nombres de profesores revisores a través de Areas_Profesor
        revisores = {}
        if profesor_revisor_ids:
            query_revisores = (
                select(Areas_Profesor, Profesores.nombre)
                .join(Profesores, Areas_Profesor.profesor_id == Profesores.id)
                .where(Areas_Profesor.id.in_(profesor_revisor_ids))
            )
            revisores = {ap.id: nombre for ap, nombre in session.exec(query_revisores)}

        # Crear una lista de resultados con los campos deseados
        result = [
            {
                # Información básica de la planificación
                "id": planificacion.id,
                "titulo": planificacion.titulo,
                "descripcion": planificacion.descripcion,
                "fecha_subida": planificacion.fecha_subida,
                
                # IDs de relaciones
                "profesor_id": planificacion.profesor_id,
                "asignaturas_id": planificacion.asignaturas_id,
                "periodo_id": planificacion.periodo_id,
                
                # Nombres de las relaciones principales
                "profesor_nombre": profesor_nombre,
                "periodo_nombre": periodo_nombre,
                "asignatura_nombre": asignatura_nombre,
                
                # Información del área
                "area_id": area_id,
                "area_nombre": area_nombre,
                "area_codigo": area_codigo,
                
                # Información del profesor aprobador
                "profesor_aprobador_id": profesor_aprobador_id,
                "profesor_aprobador_nombre": aprobadores.get(profesor_aprobador_id) if profesor_aprobador_id else None,
                
                # Información del profesor revisor
                "profesor_revisor_id": profesor_revisor_id,
                "profesor_revisor_nombre": revisores.get(profesor_revisor_id) if profesor_revisor_id else None,
                
                # Información adicional de la planificación
                "fecha_de_actualizacion": fecha_de_actualizacion,
                "estado": estado,
                "archivo": archivo,
                "comentario": comentario
            }
            for (
                planificacion, profesor_nombre, asignatura_nombre, periodo_nombre,
                profesor_aprobador_id, profesor_revisor_id,
                area_id, area_nombre, area_codigo,
                fecha_de_actualizacion, estado, archivo, comentario
            ) in planificaciones
        ]
        
        return result

    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener las planificaciones: {str(e)}"
        )