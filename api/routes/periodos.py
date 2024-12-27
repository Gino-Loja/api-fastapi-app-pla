from fastapi import APIRouter, Body, Request, Response, HTTPException, status
from fastapi.encoders import jsonable_encoder
from typing import Any, List
from sqlalchemy import asc
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from sqlmodel import desc, select , func
from model import Periodo
from api.deps import SessionDep

router = APIRouter()

# Crear un nuevo periodo
@router.post("/create", response_description="Agregar nuevo periodo", status_code=status.HTTP_201_CREATED)
async def create_periodo(periodo: Periodo, session: SessionDep) -> Any:
    try:
        new_periodo = Periodo(**periodo.dict())
        
        session.add(new_periodo)
        session.commit()
        session.refresh(new_periodo)
        
        return new_periodo

    except SQLAlchemyError as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al guardar el periodo en la base de datos"
        ) from e

# Obtener todos los periodos
@router.get("/periodo/", response_description="Listar todos los periodos", response_model=List[Periodo])
async def get_periodos(session: SessionDep) -> Any:
    # Consulta ordenada por id descendente
    statement = select(Periodo).order_by(Periodo.id.desc())
    result = session.exec(statement).all()
    return result

# Obtener un periodo específico por ID
@router.get("/periodo/{periodo_id}", response_description="Obtener un periodo por ID")
async def get_periodo(periodo_id: int, session: SessionDep) -> Any:
    statement = select(Periodo).where(Periodo.id == periodo_id)
    periodo = session.exec(statement).one_or_none()
    
    if not periodo:
        raise HTTPException(status_code=404, detail="Periodo no encontrado")
    
    return periodo

# Actualizar un periodo
@router.put("/periodo/{periodo_id}", response_description="Actualizar un periodo")
async def update_periodo(periodo_id: int, periodo: Periodo, session: SessionDep) -> Any:
    statement = select(Periodo).where(Periodo.id == periodo_id)
    existing_periodo = session.exec(statement).one_or_none()
    
    if not existing_periodo:
        raise HTTPException(status_code=404, detail="Periodo no encontrado")

    updated_periodo_data = periodo.dict(exclude_unset=True)
    for key, value in updated_periodo_data.items():
        setattr(existing_periodo, key, value)
    
    session.add(existing_periodo)
    session.commit()
    session.refresh(existing_periodo)
    return existing_periodo

# Eliminar un periodo
@router.delete("/periodo/{periodo_id}", response_description="Eliminar un periodo")
async def delete_periodo(periodo_id: int, session: SessionDep) -> Any:
    statement = select(Periodo).where(Periodo.id == periodo_id)
    periodo = session.exec(statement).one_or_none()
    
    if not periodo:
        raise HTTPException(status_code=404, detail="Periodo no encontrado")
    
    session.delete(periodo)
    session.commit()
    return {"detail": "Periodo eliminado correctamente"}


@router.get("/total/count", response_description="Obtener el total de periodos")
async def get_total_periodos(session: SessionDep) -> Any:
    try:
        statement = select(func.count(Periodo.id))
        total_periodos = session.exec(statement).one()
        return {"total_periodos": total_periodos}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al contar los periodos"
        ) from e
    

@router.get("/last", response_description="Obtener el último periodo ingresado", response_model=Periodo)
async def get_ultimo_periodo(session: SessionDep) -> Any:
    try:
        # Consulta para obtener el último periodo basado en el ID (ordenado de forma descendente)
        statement = select(Periodo).order_by(Periodo.id.desc())
        ultimo_periodo = session.exec(statement).first()  # Obtiene el primer resultado que es el último periodo ingresado
        
        if not ultimo_periodo:
            raise HTTPException(status_code=404, detail="No se ha encontrado ningún periodo")
        
        return ultimo_periodo

    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener el último periodo desde la base de datos"
        ) from e
    
@router.get("/periodos/search", response_description="Buscar periodos por nombre o código", response_model=List[Periodo])
async def search_period(
    query: str, 
    session: SessionDep
) -> Any:
    try:
        # Construir la consulta para buscar por nombre o código
        statement = select(Periodo).where(
            (Periodo.nombre.ilike(f"%{query}%"))
        ).limit(7).order_by(Periodo.id.desc())  # Limitar resultados
        
        # Ejecutar la consulta
        result = session.exec(statement).all()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="No se encontraron periodos con los criterios proporcionados."
            )

        return result

    except SQLAlchemyError as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al realizar la búsqueda en la base de datos."
        ) from e