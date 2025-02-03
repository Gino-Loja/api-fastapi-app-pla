

from datetime import datetime
import ftplib
import io
import os

from fastapi import APIRouter, File, Form, Request, Response, HTTPException, UploadFile, status,BackgroundTasks
from fastapi.encoders import jsonable_encoder
from typing import Any, List, Optional
from fastapi.responses import FileResponse
import pytz
from sqlalchemy import String, alias, cast, extract
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select , func
from model import Informe_Profesor_DTO, Periodo,  Profesores, Informe_Profesor
from api.deps import SessionDep, sender_email
import tempfile
import io
from typing import Optional
from utils import formatear_fecha, render_email_template_info, send_email

router = APIRouter()


@router.post("/informe/create/", response_description="Crear un nuevo informe", status_code=status.HTTP_201_CREATED)
async def create_informe(
    session: SessionDep,
    request: Request,
    background_tasks: BackgroundTasks,
     profesor_id:  int = Form(...),
    periodo_id:  int = Form(...),
    estado:  str = Form(...),
    
    pdf: UploadFile = File(...),

):
    try:
        # Validar conexión al servidor FTP
        ftp_server: Optional[ftplib.FTP] = request.app.ftp
        if not ftp_server:
            raise HTTPException(status_code=500, detail="No hay conexión con el servidor FTP.")

        # Verificar si el profesor existe
        profesor = session.exec(select(Profesores).where(Profesores.id == profesor_id)).one_or_none()
        profesor_revisor = session.exec(select(Profesores).where(Profesores.rol == "Rector")).one_or_none()

        if not profesor and not profesor_revisor:
            raise HTTPException(status_code=404, detail="Profesor no encontrado.")

        # Verificar si el período existe
        periodo = session.exec(select(Periodo).where(Periodo.id == periodo_id)).one_or_none()
        if not periodo:
            raise HTTPException(status_code=404, detail="Período no encontrado.")

        # Crear la ruta del archivo en el servidor FTP
        
        
        
        ruta_carpeta = f"uploads/informe/{periodo.nombre}/"
        nombre_archivo = f"{profesor.nombre}_{estado}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        ruta_completa = f"{ruta_carpeta}{nombre_archivo}"

        # Crear directorios en el servidor FTP si no existen
        partes = ruta_carpeta.split("/")
        for i in range(1, len(partes) + 1):
            subpath = "/".join(partes[:i])
            try:
                ftp_server.mkd(subpath)
            except ftplib.error_perm:
                # Ignorar error si el directorio ya existe
                pass

        # Cambiar al directorio correspondiente
        ftp_server.cwd(ruta_carpeta)

        # Subir el archivo al servidor FTP
        contenido = await pdf.read()
        ftp_server.storbinary(f"STOR {nombre_archivo}", io.BytesIO(contenido))

        # Guardar la ruta del archivo en el informe
        try:
            ftp_server.cwd('/')
        except Exception as e:
            print(f"Error regresando al directorio inicial: {e}")

        informe_listo = Informe_Profesor(
            
            estado=estado,
            periodo_id=periodo_id,
            archivo=ruta_completa,
            profesor_aprobador_id=profesor_revisor.id,
            profesor_id=profesor.id,
            
        )

        # Guardar el informe en la base de datos
        
        session.add(informe_listo)
        session.commit()
        session.refresh(informe_listo)

        # Enviar un correo electrónico al profesor
        email_data = render_email_template_info(
            template_name="info_docente.html",
            email_to=profesor.email,
            message=f"Se ha creado un nuevo informe para el período {periodo.nombre}. Puedes descargarlo desde la plataforma.",
            subject="Nuevo Informe Creado"
        )

        background_tasks.add_task(
            send_email,
            email_to=profesor.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )

        return {"message": "Informe creado exitosamente", "informe": informe_listo}

    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error al crear el informe: {str(e)}")
    
    
@router.put("/informe/update/{informe_id}", response_description="Actualizar un informe", status_code=status.HTTP_200_OK)
async def update_informe(
    session: SessionDep,
    request: Request,
    background_tasks: BackgroundTasks,
    informe_id: int,
    profesor_id: int,
    pdf: UploadFile = File(None),
    
):
    try:
        # Validar conexión al servidor FTP
        ftp_server: Optional[ftplib.FTP] = request.app.ftp
        if not ftp_server:
            raise HTTPException(status_code=500, detail="No hay conexión con el servidor FTP.")

        # Verificar si el informe existe
        informe = session.exec(select(Informe_Profesor).where(Informe_Profesor.id == informe_id)).one_or_none()
        if not informe:
            raise HTTPException(status_code=404, detail="Informe no encontrado.")

        # Verificar si el profesor existe
        profesor = session.exec(select(Profesores).where(Profesores.id == profesor_id)).one_or_none()
        if not profesor:
            raise HTTPException(status_code=404, detail="Profesor no encontrado.")

        # Verificar si el período existe
        periodo = session.exec(select(Periodo).where(Periodo.id == informe.periodo_id)).one_or_none()
        if not periodo:
            raise HTTPException(status_code=404, detail="Período no encontrado.")
        
        if profesor.rol == "Rector":
            estado = "aprobado"
        else:
            estado = "entregado"

        # Si se proporciona un nuevo archivo, actualizarlo en el servidor FTP
        if pdf:
            # Eliminar el archivo anterior si existe
            if informe.archivo:
                try:
                    ftp_server.delete(informe.archivo)
                except Exception as e:
                    print(f"Error al eliminar archivo anterior: {e}")

            # Crear la ruta del nuevo archivo
            ruta_carpeta = f"uploads/informe/{periodo.nombre}/"
            nombre_archivo = f"{profesor.nombre}_{estado}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            ruta_completa = f"{ruta_carpeta}{nombre_archivo}"

            # Subir el nuevo archivo al servidor FTP
            contenido = await pdf.read()
            ftp_server.storbinary(f"STOR {nombre_archivo}", io.BytesIO(contenido))
            ftp_server.cwd('/')

            # Actualizar la ruta del archivo en el informe
            informe.archivo = ruta_completa
        informe.estado = estado

        # Actualizar la fecha de actualización
        informe.fecha_de_actualizacion = datetime.now(pytz.timezone('America/Guayaquil'))
        try:
            ftp_server.cwd('/')
        except Exception as e:
            print(f"Error regresando al directorio inicial: {e}")


        # Guardar los cambios en la base de datos
        session.add(informe)
        session.commit()
        session.refresh(informe)

        # Enviar un correo electrónico al profesor
        email_data = render_email_template_info(
            template_name="info_docente.html",
            email_to=profesor.email,
            message=f"Se ha actualizado el informe para el período {periodo.nombre}. Puedes descargarlo desde la plataforma.",
            subject="Informe Actualizado"
        )

        background_tasks.add_task(
            send_email,
            email_to=profesor.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )


        return {"message": "Informe actualizado exitosamente", "informe": informe}

    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar el informe: {str(e)}")
    
    
@router.delete("/informe/delete/{informe_id}", response_description="Eliminar un informe", status_code=status.HTTP_204_NO_CONTENT)
async def delete_informe(
    informe_id: int,
    session: SessionDep,
    request: Request
):
    try:
        # Validar conexión al servidor FTP
        ftp_server: Optional[ftplib.FTP] = request.app.ftp
        if not ftp_server:
            raise HTTPException(status_code=500, detail="No hay conexión con el servidor FTP.")

        # Verificar si el informe existe
        informe = session.exec(select(Informe_Profesor).where(Informe_Profesor.id == informe_id)).one_or_none()
        if not informe:
            raise HTTPException(status_code=404, detail="Informe no encontrado.")

        # Eliminar el archivo del servidor FTP si existe
        if informe.archivo:
            try:
                ftp_server.delete(informe.archivo)
            except Exception as e:
                print(f"Error al eliminar archivo del FTP: {e}")
        
        try:
            ftp_server.cwd('/')
        except Exception as e:
            print(f"Error regresando al directorio inicial: {e}")

        # Eliminar el informe de la base de datos
        session.delete(informe)
        session.commit()

        return {"message": "Informe eliminado exitosamente"}

    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar el informe: {str(e)}")
    
@router.get("/informe/download/{informe_id}", response_description="Descargar archivo de informe")
async def download_informe(
    informe_id: int,
    session: SessionDep,
    request: Request
):
    try:
        # Validar conexión al servidor FTP
        ftp_server: Optional[ftplib.FTP] = request.app.ftp
        if not ftp_server:
            raise HTTPException(status_code=500, detail="No hay conexión con el servidor FTP.")

        # Verificar si el informe existe
        informe = session.exec(select(Informe_Profesor).where(Informe_Profesor.id == informe_id)).one_or_none()
        if not informe:
            raise HTTPException(status_code=404, detail="Informe no encontrado.")

        # Verificar si el archivo existe
        if not informe.archivo:
            raise HTTPException(status_code=404, detail="Archivo no encontrado.")

        # Obtener el nombre del archivo
        directorio, nombre_archivo = os.path.split(informe.archivo)

        # Cambiar al directorio correspondiente en el servidor FTP
        ftp_server.cwd(directorio)

        # Crear un archivo temporal para la descarga
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            try:
                # Descargar el archivo desde el servidor FTP
                ftp_server.retrbinary(f"RETR {nombre_archivo}", temp_file.write)
            except Exception as e:
                print(f"Error al descargar archivo: {e}")
                raise HTTPException(status_code=500, detail="Error al descargar el archivo desde el servidor FTP.")
            finally:
                # Regresar al directorio raíz del servidor FTP
                ftp_server.cwd('/')

        # Devolver el archivo como respuesta
        return FileResponse(
            path=temp_file.name,
            media_type='application/pdf',
            filename=nombre_archivo,
            headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"}
        )

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error al descargar el informe: {str(e)}")
    
    
@router.get("/informe/conteo-por-periodo/", response_description="Obtener el conteo total de informes por período")
async def get_conteo_informes_por_periodo(
    periodo_id: int,
    session: SessionDep
):
    try:
        # Verificar si el período existe
        periodo = session.exec(select(Periodo).where(Periodo.id == periodo_id)).one_or_none()
        if not periodo:
            raise HTTPException(status_code=404, detail="Período no encontrado.")

        # Consulta para contar los informes asociados al período
        conteo = session.exec(
            select(func.count()).where(Informe_Profesor.periodo_id == periodo_id)
        ).one()

        return { "total_informes": conteo}

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener el conteo de informes: {str(e)}")
    
@router.get("/informe/listar-por-periodo/", response_description="Listar todos los informes por período")
async def listar_informes_por_periodo(
    periodo_id: int,
    session: SessionDep
):
    try:
        # Verificar si el período existe
        periodo = session.exec(select(Periodo).where(Periodo.id == periodo_id)).one_or_none()
        if not periodo:
            raise HTTPException(status_code=404, detail="Período no encontrado.")

        # Consulta para obtener todos los informes asociados al período, incluyendo el nombre del profesor
        informes = session.exec(
            select(
                Informe_Profesor,
                Profesores.nombre.label("profesor_nombre"),  # Seleccionar el nombre del profesor
                Periodo.nombre.label("periodo_nombre")  # Seleccionar el nombre del periodo
            )
            .join(Profesores, Informe_Profesor.profesor_id == Profesores.id)  # Join con la tabla Profesores
            .join(Periodo, Informe_Profesor.periodo_id == Periodo.id)  # Join con la tabla Periodo
            .where(Informe_Profesor.periodo_id == periodo_id)
        ).all()

        # Formatear la respuesta
        resultados = [
            {
                "id": informe.id,
                "estado": informe.estado,
                "periodo_id": informe.periodo_id,
                "archivo": informe.archivo,
                "profesor_aprobador_id": informe.profesor_aprobador_id,
                "profesor_id": informe.profesor_id,
                "profesor_nombre": profesor_nombre,  # Incluir el nombre del profesor
                "fecha_de_actualizacion": informe.fecha_de_actualizacion.isoformat() if informe.fecha_de_actualizacion else None,
                "periodo_nombre": periodo_nombre,  # Incluir el nombre del periodo
            }
            for informe, profesor_nombre, periodo_nombre in informes  # Desempaquetar el resultado del join
        ]

        return resultados

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error al listar los informes: {str(e)}")