from fastapi import APIRouter, Body, Request, Response, HTTPException, status
from fastapi.encoders import jsonable_encoder
from typing import Any, List
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from sqlmodel import select , func
from model import Asignaturas
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
@router.get("/", response_description="Listar todas las asignaturas", response_model=List[Asignaturas])
async def get_asignaturas(session: SessionDep) -> Any:
    statement = select(Asignaturas)
    result = session.exec(statement).all()
    return result

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