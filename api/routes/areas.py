from fastapi import APIRouter, Body, Request, Response, HTTPException, status
from fastapi.encoders import jsonable_encoder
from typing import Any, List
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from sqlmodel import select, func
from api.deps import SessionDep
from model import  Areas, areas_profesor, Profesores

router = APIRouter()

# Crear una nueva área
@router.post("/create", response_description="Agregar nueva área", status_code=status.HTTP_201_CREATED)
async def create_area(area: Areas, session: SessionDep) -> Any:
    try:
        area_data = jsonable_encoder(area)
        new_area = Areas(**area_data)

        session.add(new_area)
        session.commit()
        session.refresh(new_area)

        return new_area

    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un área con este código. Por favor, usa un código diferente."
        ) from e

    except SQLAlchemyError as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al guardar el área en la base de datos. Por favor, intenta de nuevo."
        ) from e

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error en la solicitud. Verifica los datos ingresados."
        ) from e

# Obtener todas las áreas
@router.get("/", response_description="Listar todas las áreas", response_model=List[Areas])
async def get_areas(session: SessionDep) -> Any:
    statement = select(Areas)
    result = session.exec(statement).all()
    return result

# Obtener un área específica por ID
@router.get("/{area_id}", response_description="Obtener un área por ID")
async def get_area(area_id: int, session: SessionDep) -> Any:
    statement = select(Areas).where(Areas.id == area_id)
    area = session.exec(statement).one_or_none()

    if not area:
        raise HTTPException(status_code=404, detail="Área no encontrada")

    return area

# Actualizar un área
@router.put("/{area_id}", response_description="Actualizar un área")
async def update_area(area_id: int, area: Areas, session: SessionDep) -> Any:
    statement = select(Areas).where(Areas.id == area_id)
    existing_area = session.exec(statement).one_or_none()

    if not existing_area:
        raise HTTPException(status_code=404, detail="Área no encontrada")

    updated_area_data = jsonable_encoder(area)
    for key, value in updated_area_data.items():
        if value is not None:  
            setattr(existing_area, key, value)

    session.add(existing_area)
    session.commit()
    session.refresh(existing_area)
    return existing_area

@router.delete("/{area_id}", response_description="Eliminar un área")
async def delete_area(area_id: int, session: SessionDep) -> Any:
    try:
        statement = select(Areas).where(Areas.id == area_id)
        existing_area = session.exec(statement).one_or_none()

        if not existing_area:
            raise HTTPException(status_code=404, detail="Área no encontrada")

        session.delete(existing_area)
        session.commit()

        return {
            "message": "Área eliminada exitosamente",
            "deleted_id": area_id
        }

    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar el área porque tiene registros relacionados"
        ) from e

    except SQLAlchemyError as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al eliminar el área de la base de datos"
        ) from e

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error en la solicitud de eliminación"
        ) from e
        
# Eliminar un área
@router.delete("/delete/{area_id}", response_description="Eliminar un área")
async def delete_area(area_id: int, session: SessionDep) -> Any:
    statement = select(areas_profesor).where(areas_profesor.id == area_id)
    area = session.exec(statement).one_or_none()

    if not area:
        raise HTTPException(status_code=404, detail="Área no encontrada")

    session.delete(area)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# Contar el total de áreas
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

# Buscar áreas por nombre o código
@router.get("/areas/search", response_description="Buscar áreas por nombre o código", response_model=List[Areas])
async def search_area(query: str, session: SessionDep) -> Any:
    try:
        statement = select(Areas).where(
            (Areas.nombre.ilike(f"%{query}%")) | (Areas.codigo.ilike(f"%{query}%"))
        ).limit(7)

        result = session.exec(statement).all()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontraron áreas con los criterios proporcionados."
            )

        return result

    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al realizar la búsqueda en la base de datos."
        ) from e
    
# obetner areas con campo especifico

@router.get("/areas-profesor/search", response_description="Buscar áreas por nombre o código", response_model=List[Any])
async def search_area( session: SessionDep) -> Any:
    try:
        # Realizamos un join entre AreaProfesor, Profesores y Areas
        statement = select(
            areas_profesor.id,
            Profesores.nombre.label("profesor_nombre"),
            Areas.nombre.label("area_nombre"),
            areas_profesor.profesor_id,
            areas_profesor.area_id,
            areas_profesor.fecha_de_ingreso
        ).join(
            Profesores, areas_profesor.profesor_id == Profesores.id
        ).join(
            Areas, areas_profesor.area_id == Areas.id
        )
    
        result = session.exec(statement).all()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontraron áreas o profesores con los criterios proporcionados."
            )

        # Formatear la respuesta para retornar solo los nombres
        return [{
                "id": id,
                "profesor_nombre": profesor_nombre,
                  "area_nombre": area_nombre,
                  'profesor_id': profesor_id,
                  'area_id': area_id,
                  'fecha_de_ingreso': fecha_de_ingreso
                  } for id,profesor_nombre,area_nombre,profesor_id, area_id, fecha_de_ingreso in result]

    except SQLAlchemyError as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al realizar la búsqueda en la base de datos."
        ) from e
    



@router.post("/areas-profesor", response_description="Guardar área para el profesor", status_code=status.HTTP_201_CREATED)
async def create_area_profesor(data: areas_profesor, session: SessionDep):
    try:
        # Verificar si el profesor ya está asignado a esta área
        existing_assignment = session.query(areas_profesor).filter(
            areas_profesor.profesor_id == data.profesor_id,
            areas_profesor.area_id == data.area_id
        ).first()

        # Si ya existe una asignación, lanzar una excepción
        if existing_assignment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El profesor ya está asignado a esta área."
            )

        # Crear un nuevo registro en la tabla areas_profesor
        new_entry = areas_profesor(
            profesor_id=data.profesor_id,
            area_id=data.area_id,
        )
        session.add(new_entry)
        session.commit()
        session.refresh(new_entry)

        return {"message": "Área asignada exitosamente al profesor", "data": new_entry}

    except Exception as e:
        session.rollback()  # Hacer rollback en caso de error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al guardar el registro en la base de datos: {str(e)}"
        )
        
@router.put("/areas-profesor/update/{area_id}", response_description="Actualizar un área para el profesor")
async def update_area_profesor(area_id: int, data: areas_profesor, session: SessionDep) -> Any:
    try:
        # Buscar el registro existente
        statement = select(areas_profesor).where(areas_profesor.id == area_id)
        existing_entry = session.exec(statement).one_or_none()

        if not existing_entry:
            raise HTTPException(status_code=404, detail="Asignación no encontrada")

        # Verificar si ya existe otra asignación del profesor a la misma área (excluyendo el registro actual)
        duplicate_assignment = session.query(areas_profesor).filter(
            areas_profesor.profesor_id == data.profesor_id,
            areas_profesor.area_id == data.area_id,
            areas_profesor.id != area_id  # Excluir el registro actual
        ).first()

        # Si ya existe una asignación duplicada, lanzar una excepción
        if duplicate_assignment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El profesor ya está asignado a esta área."
            )

        # Actualizar los campos del registro con los nuevos datos
        updated_data = jsonable_encoder(data)
        for key, value in updated_data.items():
            if value is not None:  # No actualizamos si el valor es None
                setattr(existing_entry, key, value)

        session.add(existing_entry)
        session.commit()
        session.refresh(existing_entry)

        return {"message": "Área actualizada exitosamente", "data": existing_entry}

    except Exception as e:
        session.rollback()  # Rollback en caso de error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar el registro en la base de datos: {str(e)}"
        )     

@router.get("/profesor/{profesor_id}/areas", response_description="Obtener áreas de un profesor", response_model=List[Any])
async def get_areas_profesor(profesor_id: int, session: SessionDep) -> Any:
    try:
        # Realizamos un join entre areas_profesor, Profesores y Areas
        statement = select(
            Areas.id,
            Areas.nombre,
            Areas.codigo
        ).join(
            areas_profesor, Areas.id == areas_profesor.area_id  # Unimos Areas con areas_profesor
        ).join(
            Profesores, areas_profesor.profesor_id == Profesores.id  # Unimos areas_profesor con Profesores
        ).where(
            Profesores.id == profesor_id  # Filtramos por el ID del profesor
        )

        result = session.exec(statement).all()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontraron áreas asignadas a este profesor."
            )

        # Formatear la respuesta para retornar los datos de las áreas
        return [{
            "id": id,
            "nombre": nombre,
            "codigo": codigo
        } for id, nombre, codigo in result]

    except SQLAlchemyError as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al realizar la búsqueda en la base de datos."
        ) from e