from fastapi import APIRouter, Body, Request, Response, HTTPException, status,File, UploadFile, responses 
from fastapi.encoders import jsonable_encoder
#from model import  Prediccion, Datos_manuales, Estaciones
from typing import Any, List,Annotated
#import numpy as np
import os
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from sqlmodel import select , func

from model import Profesores, Roles, Total_profesores
router = APIRouter()
from PIL import Image
from api.deps import  SessionDep



# @router.post("/upload", response_description="Validar residuos", status_code=status.HTTP_201_CREATED)
# def obtener_prediccion_actual(request: Request, estaciones = Body(...)):
#     estaciones = jsonable_encoder(estaciones)
#     #datos_sensores: List[Datos_sensor] = list(
#         #request.app.database[estaciones["estacion"]].find().sort([('_id', -1)]).limit(1))

#     return 0



 
# @router.post("/uploadfile/image/")
# async def create_file(
#     session: SessionDep,
#     file: Annotated[bytes, File()]
#     )->Any:
#     #print(session)
#     #print(file)
#     return {"file_size": file}

# Crear un nuevo profesor
@router.post("/create", response_description="Agregar nuevo profesor", status_code=status.HTTP_201_CREATED)
async def create_professor(profesor: Profesores, session: SessionDep) -> Any:
    try:
        profesor_data = jsonable_encoder(profesor)
        new_profesor = Profesores(**profesor_data)
        
        session.add(new_profesor)
        session.commit()
        session.refresh(new_profesor)
        
        return new_profesor

    except IntegrityError as e:
        # Captura el error de clave única duplicada
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe este profesor. Por favor, usa un email o cedula diferente."
        ) from e

    except SQLAlchemyError as e:
        # Captura otros errores relacionados con SQLAlchemy
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al guardar el profesor en la base de datos. Por favor, intenta de nuevo."
        ) from e

    except Exception as e:
        # Captura cualquier otro error no esperado
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error en la solicitud. Verifica los datos ingresados."
        ) from e

# Obtener todos los profesores
@router.get("/", response_description="Listar todos los profesores", response_model=List[Profesores])
async def get_professors(session: SessionDep) -> Any:
    statement = select(Profesores)
    result = session.exec(statement).all()
    return result

# Obtener un profesor específico por ID
@router.get("/{profesor_id}", response_description="Obtener un profesor por ID")
async def get_professor(profesor_id: int, session: SessionDep) -> Any:
    statement = select(Profesores).where(Profesores.id == profesor_id)
    profesor = session.exec(statement).one_or_none()
    
    if not profesor:
        raise HTTPException(status_code=404, detail="Profesor no encontrado")
    
    return profesor

# Actualizar un profesor
@router.put("/{profesor_id}", response_description="Actualizar un profesor")
async def update_professor(profesor_id: int, profesor: Profesores, session: SessionDep) -> Any:
    statement = select(Profesores).where(Profesores.id == profesor_id)

    existing_profesor = session.exec(statement).one() 
    # hero_2 = results.one() 
    # existing_profesor = session.exec(statement).one_or_none()
    
    if not existing_profesor:
        raise HTTPException(status_code=404, detail="Profesor no encontrado")

    updated_profesor_data = jsonable_encoder(profesor)
    for key, value in updated_profesor_data.items():
        if key != "id":  # Evita modificar el ID manualmente
            setattr(existing_profesor, key, value)
  
    session.add(existing_profesor)
    session.commit()
    session.refresh(existing_profesor)
    return existing_profesor

# Eliminar un profesor
@router.delete("/{profesor_id}", response_description="Eliminar un profesor")
async def delete_professor(profesor_id: int, session: SessionDep) -> Any:
    statement = select(Profesores).where(Profesores.id == profesor_id)
    profesor = session.exec(statement).one_or_none()
    
    if not profesor:
        raise HTTPException(status_code=404, detail="Profesor no encontrado")
    
    session.delete(profesor)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/roles/count", response_description="Obtener el número de profesores por rol", response_model=List[Roles])
async def get_professors_count_by_role(session: SessionDep) -> Any:
    # Consulta para contar la cantidad de profesores agrupados por rol
    statement = select(
        Profesores.rol, func.count().label("numero_profesores")
    ).group_by(Profesores.rol)
    
    result = session.exec(statement).all()
    
    return result


@router.get("/count/total", response_description="Obtener el total de profesores", response_model=Total_profesores)
async def get_total_professors(session: SessionDep) -> Any:
    statement = select(func.count().label("total")).select_from(Profesores)
    result = session.exec(statement).one()
    return  {"total": result}