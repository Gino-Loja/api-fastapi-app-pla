from fastapi import APIRouter, Body, Request, Response, HTTPException, status
from fastapi.encoders import jsonable_encoder
from typing import Any, List
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from sqlmodel import select , func
from model import Areas, Asignaturas
from api.deps import SessionDep

router = APIRouter()

# Crear una nueva asignatura
@router.post("/create", response_description="Agregar nueva asignatura", status_code=status.HTTP_201_CREATED)
async def create_asignatura(asignatura: Asignaturas, session: SessionDep) -> Any:
    try:
        asignatura_data = jsonable_encoder(asignatura)
        new_asignatura = Asignaturas(**asignatura_data)
        
        session.add(new_asignatura)
        session.commit()
        session.refresh(new_asignatura)
        
        return new_asignatura

    except IntegrityError as e:
        # Captura el error de clave única duplicada
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una asignatura con este código. Por favor, usa un código diferente."
        ) from e

    except SQLAlchemyError as e:
        # Captura otros errores relacionados con SQLAlchemy
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al guardar la asignatura en la base de datos. Por favor, intenta de nuevo."
        ) from e

    except Exception as e:
        # Captura cualquier otro error no esperado
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error en la solicitud. Verifica los datos ingresados."
        ) from e

# Obtener todas las asignaturas
# @router.get("/", response_description="Listar todas las asignaturas", response_model=List[Asignaturas])
# async def get_asignaturas(session: SessionDep) -> Any:
#     statement = select(Asignaturas)
#     result = session.exec(statement).all()
#     return result
@router.get("/", response_description="Listar todas las asignaturas con su área", response_model=List[Any])
async def get_asignaturas(session: SessionDep) -> Any:
    try:
        # Consulta para obtener asignaturas junto con el id_area y el nombre del área
        statement = (
            select(
                Asignaturas.id,
                Asignaturas.nombre,
                Asignaturas.area_id,
                Areas.nombre.label("area_nombre"),
                Asignaturas.curso,
                Asignaturas.fecha_creacion,
                Asignaturas.descripcion,
                Asignaturas.codigo,
                
            )
            .join(Areas, Asignaturas.area_id == Areas.id)
        )

        # Ejecutar la consulta
        asignaturas = session.exec(statement).all()


        # Formatear los resultados a partir de las tuplas
        result = [
            {
                "id": id,
                "nombre": nombre,
                "area_id": area_id,
                "area_nombre": area_nombre,
                "curso": curso,
                "fecha_creacion": fecha_creacion,
                "descripcion": descripcion,
                "codigo": codigo,

            }
            for id, nombre, area_id, area_nombre, curso, fecha_creacion, descripcion, codigo in asignaturas
        ]

        return result

    except Exception as e:
        # Manejo de errores
        print(f"Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener las asignaturas: {str(e)}"
        )


# Obtener una asignatura específica por ID
@router.get("/{asignatura_id}", response_description="Obtener una asignatura por ID")
async def get_asignatura(asignatura_id: int, session: SessionDep) -> Any:
    statement = select(Asignaturas).where(Asignaturas.id == asignatura_id)
    asignatura = session.exec(statement).one_or_none()
    
    if not asignatura:
        raise HTTPException(status_code=404, detail="Asignatura no encontrada")
    
    return asignatura

# Actualizar una asignatura
@router.put("/{asignatura_id}", response_description="Actualizar una asignatura")
async def update_asignatura(asignatura_id: int, asignatura: Asignaturas, session: SessionDep) -> Any:
    
    statement = select(Asignaturas).where(Asignaturas.id == asignatura_id)
    existing_asignatura = session.exec(statement).one_or_none()
    
    if not existing_asignatura:
        raise HTTPException(status_code=404, detail="Asignatura no encontrada")

    updated_asignatura_data = jsonable_encoder(asignatura)
    for key, value in updated_asignatura_data.items():
            if value is not None:  # No actualizamos si el valor es None
                setattr(existing_asignatura, key, value)
    
    session.add(existing_asignatura)
    session.commit()
    session.refresh(existing_asignatura)
    return existing_asignatura

# Eliminar una asignatura
@router.delete("/{asignatura_id}", response_description="Eliminar una asignatura")
async def delete_asignatura(asignatura_id: int, session: SessionDep) -> Any:
    statement = select(Asignaturas).where(Asignaturas.id == asignatura_id)
    asignatura = session.exec(statement).one_or_none()
    
    if not asignatura:
        raise HTTPException(status_code=404, detail="Asignatura no encontrada")
    
    session.delete(asignatura)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

    # statement = select(func.count().label("total")).select_from(Profesores)
    # result = session.exec(statement).one()
    # return  {"total": result}

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
    

@router.get("/asignaturas/search", response_description="Buscar asignaturas por nombre o código", response_model=List[Asignaturas])
async def search_subject(
    query: str, 
    session: SessionDep
) -> Any:
    try:
        # Construir la consulta para buscar por nombre o código
        statement = select(Asignaturas).where(
            (Asignaturas.nombre.ilike(f"%{query}%")) | (Asignaturas.codigo.ilike(f"%{query}%"))
        ).limit(7)  # Limitar resultados para no saturar la respuesta
        
        # Ejecutar la consulta
        result = session.exec(statement).all()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="No se encontraron asignaturas con los criterios proporcionados."
            )

        return result

    except SQLAlchemyError as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al realizar la búsqueda en la base de datos."
        ) from e


