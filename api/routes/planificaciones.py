
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
from model import Areas, Comentarios, Comentarios_Dto, areas_profesor, Asignaturas, Periodo, Planificacion_Profesor, Planificaciones, Profesores
from api.deps import SessionDep, sender_email
import tempfile
import io
from typing import Optional
from utils import formatear_fecha, render_email_template_info, send_email

router = APIRouter()

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

# Crear un nuevo periodo

# Obtener todos los periodos


@router.post("/create", response_description="Agregar nueva planificación", status_code=status.HTTP_201_CREATED)
async def create_planificacion(planificacion: Planificaciones, session: SessionDep,background_tasks: BackgroundTasks) -> Any:
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
        # sender_email(fechtprofesor.email,
        #             "Planificación de asignaturas",
        #             f"Se ha creado una nueva planificación para la asignatura {fechtAsignatura.nombre} con fecha de entrega {planificacion.fecha_subida}")
        
        fecha_formateada = formatear_fecha(planificacion.fecha_subida)

        email_data = render_email_template_info(
        template_name="info_docente.html",
        email_to=fechtprofesor.email,
        message=f"Se ha creado una nueva planificación para la asignatura {fechtAsignatura.nombre} con fecha de entrega {fecha_formateada}",
        subject="Planificación de asignaturas"
        )
        
        background_tasks.add_task(
            send_email,
            email_to=fechtprofesor.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
        
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
async def update_planificacion(planificacion_id: int, updated_data: Planificaciones, session: SessionDep, request: Request,background_tasks: BackgroundTasks) -> Any:
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

        # Eliminar archivo de la base de datos y del servidor FTP
        planificacion_profesor = session.exec(
            select(Planificacion_Profesor).where(Planificacion_Profesor.planificacion_id == planificacion_id)
        ).one_or_none()
    
        if planificacion_profesor :
            # Eliminar archivo de FTP
            ftp_server: Optional[ftplib.FTP] = request.app.ftp
            if ftp_server:
                try:
                    if planificacion_profesor.archivo is not None:
                        ftp_server.delete(planificacion_profesor.archivo)
                except Exception as e:
                    print(f"Error al eliminar archivo del FTP: {e}")
            # Eliminar archivo de la base de datos
            planificacion_profesor.archivo = None
            session.add(planificacion_profesor)
            session.commit()

        # Actualizar los campos de la planificación existente
        updated_fields = updated_data.dict(exclude_unset=True)  # Solo incluir campos enviados
        for key, value in updated_fields.items():
            setattr(existing_planificacion, key, value)

        # Actualizar la fecha formateada (si es necesario)
        fecha_formateada = formatear_fecha(updated_data.fecha_subida)

        # Enviar email (si es necesario)
        email_data = render_email_template_info(
            template_name="info_docente.html",
            email_to=fechtprofesor.email,
            message=f"Se ha Actualizado la planificación para la asignatura {fechtAsignatura.nombre} con fecha de entrega de {fecha_formateada}",
            subject="Actualización de planificación de asignaturas"
        )

        background_tasks.add_task(
            send_email,
            email_to=fechtprofesor.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )

        # Guardar los cambios en la base de datos
        session.add(existing_planificacion)
        session.commit()
        session.refresh(existing_planificacion)

        return {"message": "Planificación actualizada correctamente", "data": existing_planificacion}

    except SQLAlchemyError as e:
        session.rollback()
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al guardar la planificación en la base de datos, tal vez la asignatura no está asignada a ningún área"
        ) from e
        

@router.get("/search/", response_description="Listar todas las planificaciones", response_model=List[Any])
async def get_all_planificaciones(
    query: int, 
    mes: str,
    year: str,
    session: SessionDep
) -> Any:
    try:
        # Realizamos el join entre todas las tablas necesarias
        query = (
            select(
                Planificaciones,
                Planificacion_Profesor.id,
                Planificacion_Profesor.planificacion_id,
                Profesores.nombre.label("profesor_nombre"),
                Asignaturas.nombre.label("asignatura_nombre"),
                Asignaturas.curso.label("curso_nombre"),  # Agregar el nombre del curso
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
                areas_profesor,
                Planificacion_Profesor.profesor_revisor_id == areas_profesor.id,
                isouter=True
            )
            .where(Planificaciones.periodo_id == query)
            .where(cast(extract('month', Planificaciones.fecha_subida), String).ilike(f'%{mes}%'))
            .where(cast(extract('year', Planificaciones.fecha_subida), String).ilike(f'%{year}%'))
        )
        
        # Ejecutar la consulta y obtener los resultados
        planificaciones = session.exec(query).all()

        # Obtener los IDs de profesores aprobadores y revisores
        profesor_aprobador_ids = [p[7] for p in planificaciones if p[7] is not None]  # índice 6 es profesor_aprobador_id
        profesor_revisor_ids = [p[8] for p in planificaciones if p[8] is not None]    # índice 7 es profesor_revisor_id

        # Consultar nombres de profesores aprobadores
        aprobadores = {}
        if profesor_aprobador_ids:
            query_aprobadores = select(Profesores).where(Profesores.id.in_(profesor_aprobador_ids))
            aprobadores = {p.id: p.nombre for p in session.exec(query_aprobadores)}

        # Consultar nombres de profesores revisores a través de Areas_Profesor
        revisores = {}
        if profesor_revisor_ids:
            query_revisores = (
                select(areas_profesor, Profesores.nombre)
                .join(Profesores, areas_profesor.profesor_id == Profesores.id)
                .where(areas_profesor.id.in_(profesor_revisor_ids))
            )
            revisores = {ap.id: nombre for ap, nombre in session.exec(query_revisores)}

        # Crear una lista de resultados con los campos deseados
        result = [
            {
                # Información básica de la planificación
                "titulo": planificacion.titulo,
                "descripcion": planificacion.descripcion,
                "fecha_subida": planificacion.fecha_subida,
                
                # IDs de relaciones
                "profesor_id": planificacion.profesor_id,
                "asignaturas_id": planificacion.asignaturas_id,
                "periodo_id": planificacion.periodo_id,

                "id": id,
                "id_planificacion": planificacion_id,
                
                # Nombres de las relaciones principales
                "profesor_nombre": profesor_nombre,
                "periodo_nombre": periodo_nombre,
                "asignatura_nombre": asignatura_nombre,
                "curso_nombre": curso_nombre,  # Agregar el nombre del curso
                
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
            }
            for (
                planificacion, id, planificacion_id, profesor_nombre, asignatura_nombre, curso_nombre, periodo_nombre,
                profesor_aprobador_id, profesor_revisor_id,
                area_id, area_nombre, area_codigo,
                fecha_de_actualizacion, estado, archivo
            ) in planificaciones
        ]
        
        return result

    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener las planificaciones: {str(e)}"
        )


@router.get("/search/revisor/", response_description="Listar todas las planificaciones de un profesor revisor", response_model=List[Any])
async def get_planificaciones_by_revisor(
    profesor_id: int,  # ID del profesor (no del areas_profesor)
    query: int,  # ID del periodo
    mes: str,  # Mes de la planificación
    year: str,  # Año de la planificación
    session: SessionDep
) -> Any:
    try:
        # Realizamos el join entre todas las tablas necesarias
        query_planificaciones = (
            select(
                Planificaciones,
                Planificacion_Profesor.id,
                Planificacion_Profesor.planificacion_id,
                Profesores.nombre.label("profesor_nombre"),
                Asignaturas.nombre.label("asignatura_nombre"),
                Asignaturas.curso.label("curso_nombre"),  # Agregar el nombre del curso

                Periodo.nombre.label("periodo_nombre"),
                
                Planificacion_Profesor.profesor_aprobador_id,
                Planificacion_Profesor.profesor_revisor_id,
                Areas.id.label("area_id"),
                Areas.nombre.label("area_nombre"),
                Areas.codigo.label("area_codigo"),
                Planificacion_Profesor.fecha_de_actualizacion,
                Planificacion_Profesor.estado,
                Planificacion_Profesor.archivo,
            )
            .join(Profesores, Planificaciones.profesor_id == Profesores.id)
            .join(Asignaturas, Planificaciones.asignaturas_id == Asignaturas.id)
            .join(Periodo, Planificaciones.periodo_id == Periodo.id)
            .join(Areas, Asignaturas.area_id == Areas.id)
            .join(
                Planificacion_Profesor,
                Planificaciones.id == Planificacion_Profesor.planificacion_id
            )
            .join(
                areas_profesor,
                Planificacion_Profesor.profesor_revisor_id == areas_profesor.id,
                isouter=True
            )
            .where(areas_profesor.profesor_id == profesor_id)  # Filtrar por el ID del profesor en areas_profesor
            .where(Planificaciones.periodo_id == query)  # Filtrar por el periodo
            .where(cast(extract('month', Planificaciones.fecha_subida), String).ilike(f'%{mes}%'))  # Filtrar por mes
            .where(cast(extract('year', Planificaciones.fecha_subida), String).ilike(f'%{year}%'))  # Filtrar por año
        )
        
        # Ejecutar la consulta y obtener los resultados
        planificaciones = session.exec(query_planificaciones).all()

        # Obtener los IDs de profesores aprobadores y revisores
        profesor_aprobador_ids = [p[7] for p in planificaciones if p[7] is not None]  # índice 6 es profesor_aprobador_id
        profesor_revisor_ids = [p[8] for p in planificaciones if p[8] is not None]    # índice 7 es profesor_revisor_id

        # Consultar nombres de profesores aprobadores
        aprobadores = {}
        if profesor_aprobador_ids:
            query_aprobadores = select(Profesores).where(Profesores.id.in_(profesor_aprobador_ids))
            aprobadores = {p.id: p.nombre for p in session.exec(query_aprobadores)}

        # Consultar nombres de profesores revisores a través de Areas_Profesor
        revisores = {}
        if profesor_revisor_ids:
            query_revisores = (
                select(areas_profesor, Profesores.nombre)
                .join(Profesores, areas_profesor.profesor_id == Profesores.id)
                .where(areas_profesor.id.in_(profesor_revisor_ids))
            )
            revisores = {ap.id: nombre for ap, nombre in session.exec(query_revisores)}

        # Crear una lista de resultados con los campos deseados
        result = [
            {
                # Información básica de la planificación
                "titulo": planificacion.titulo,
                "descripcion": planificacion.descripcion,
                "fecha_subida": planificacion.fecha_subida,
                
                # IDs de relaciones
                "profesor_id": planificacion.profesor_id,
                "asignaturas_id": planificacion.asignaturas_id,
                "periodo_id": planificacion.periodo_id,

                "id": id,
                "id_planificacion": planificacion_id,
                
                # Nombres de las relaciones principales
                "profesor_nombre": profesor_nombre,
                "periodo_nombre": periodo_nombre,
                "asignatura_nombre": asignatura_nombre,
                "curso_nombre": curso_nombre,  # Agregar el nombre del curso
                
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
            }
            for (
                planificacion, id, planificacion_id, profesor_nombre, asignatura_nombre,curso_nombre, periodo_nombre,
                profesor_aprobador_id, profesor_revisor_id,
                area_id, area_nombre, area_codigo,
                fecha_de_actualizacion, estado, archivo
            ) in planificaciones
        ]
        
        return result

    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener las planificaciones: {str(e)}"
        )


BASE_UPLOAD_DIR = "uploads"

@router.put("/subir-pdf/")
async def subir_pdf(
    db: SessionDep,
    request: Request,
    background_tasks: BackgroundTasks,

    pdf: UploadFile = File(...),
    id_planificacion: int = Form(...),
    area_codigo: str = Form(...),
    id_usuario: int = Form(...),
    nombre_asignatura: str = Form(...),
    periodo_nombre: str = Form(...),   
    curso_nombre: str = Form(...),
    id_profesor_asignado: int = Form(...),
):
    # Validar conexión al servidor FTP
    ftp_server: Optional[ftplib.FTP] = request.app.ftp
    if not ftp_server:
        raise HTTPException(status_code=500, detail="No hay conexión con el servidor FTP.")

    try:
        ftp_server.cwd('/')
    except Exception as e:
        print(f"Error regresando al directorio inicial: {e}")
    try:
        # Verificar si ya existe un registro de planificación_profesor
        query_planificacion_profesor = select(Planificacion_Profesor).where(
            Planificacion_Profesor.id == id_planificacion
        )
        result = db.exec(query_planificacion_profesor)
        
        planificacion_profesor: Optional[Planificacion_Profesor] = result.first()
        
        profesor_revisor = db.exec(select(areas_profesor).where(
            areas_profesor.id == planificacion_profesor.profesor_revisor_id
        ))
        
        planificacion_profesor_revisor_id: Optional[areas_profesor] = profesor_revisor.first()
        
        
        profesor_asignado = db.exec(select(Profesores).where(
            Profesores.id == id_profesor_asignado
        )).first()
        
        
        

        if not planificacion_profesor:
            raise HTTPException(status_code=404, detail="Planificación no encontrada")

        # Lógica para determinar el estado
        
        
        if planificacion_profesor_revisor_id.profesor_id == id_usuario:
            estado = "revisado"
            email_data = render_email_template_info(
                template_name="info_docente.html",
                email_to=profesor_asignado.email,
                message=f"Se ha Actualizado el estado de la planificación: [{estado.upper()}] de la asignatura {nombre_asignatura} del curso {curso_nombre}. Consultar estado con el identificador {id_planificacion}.",
                subject="Actualización de planificación de asignaturas"
            )

            background_tasks.add_task(
                send_email,
                email_to=profesor_asignado.email,
                subject=email_data.subject,
                html_content=email_data.html_content,
            )
            
        elif planificacion_profesor.profesor_aprobador_id == id_usuario:
            estado = "aprobado"
            email_data = render_email_template_info(
                template_name="info_docente.html",
                email_to=profesor_asignado.email,
                message=f"Se ha Actualizado el estado de la planificación a: [{estado.upper()}]de la asignatura {nombre_asignatura} del curso{curso_nombre}. Consultar estado con el identificador {id_planificacion}.",
                subject="Actualización de planificación de asignaturas"
            )

            background_tasks.add_task(
                send_email,
                email_to=profesor_asignado.email,
                subject=email_data.subject,
                html_content=email_data.html_content,
            )
        else:
            estado = "entregado"
        
            
            
        if not planificacion_profesor.archivo:
            print("archivo no existe pero fue entregado")
            
            estado = "entregado"
            
            def enviar_email_revisor():
                profesor_aprobador = db.exec(select(Profesores).where(
                Profesores.id == planificacion_profesor.profesor_aprobador_id
                )).first()
                email_data = render_email_template_info(
                template_name="info_docente.html",
                email_to=profesor_aprobador.email,
                message=f"Se ha realizado la entrega de la planificación en la asignatura {nombre_asignatura} del curso {curso_nombre}. Consultar estado con el identificador {id_planificacion}.",
                subject="Actualización de planificación de asignaturas"
                
                )
                send_email(
                    email_to=profesor_aprobador.email,
                    subject=email_data.subject,
                    html_content=email_data.html_content,
                )
                
            background_tasks.add_task(enviar_email_revisor)
            
       
            
          
        
        # Crear la ruta del archivo
        ruta_carpeta = f"uploads/{periodo_nombre}/{area_codigo}/{curso_nombre}/{nombre_asignatura}"
        nombre_archivo = f"{id_planificacion}_{id_profesor_asignado}_{nombre_asignatura}_{estado}.pdf"
        ruta_completa = f"{ruta_carpeta}/{nombre_archivo}"

        # Verificar y crear directorios en el servidor FTP
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

        # Verificar si el archivo ya existe
        archivos_en_directorio = ftp_server.nlst()
        
        if planificacion_profesor.archivo:
            directorio, filename = os.path.split(planificacion_profesor.archivo)
            if filename in archivos_en_directorio:
                # Eliminar el archivo existente
                ftp_server.delete(planificacion_profesor.archivo)

        # Subir el nuevo archivo
        contenido = await pdf.read()
        ftp_server.storbinary(f"STOR {nombre_archivo}", io.BytesIO(contenido))

        # Actualizar el registro en la base de datos
        planificacion_profesor.archivo = ruta_completa
        planificacion_profesor.estado = estado

        # Guardar cambios en la base de datos
        db.add(planificacion_profesor)
        db.commit()
        db.refresh(planificacion_profesor)
        try:
            ftp_server.cwd('/')
        except Exception as e:
            print(f"Error regresando al directorio inicial: {e}")

        return {
            "mensaje": "Archivo actualizado exitosamente.",
            "ruta_archivo": ruta_completa,
            "estado": estado
        }
    except Exception as e:
        print(e)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al subir el archivo: {str(e)}")




@router.get("/descargar-planificacion/", response_description="Descargar archivo de planificación")
async def descargar_planificacion(
    ruta_archivo: str,
    session: SessionDep,
    response: Response,
    request: Request,
) -> Response:
    """
    Endpoint to download a planning file from FTP server
    
    Args:
        ruta_archivo (str): Path to the file to be downloaded
        session (SessionDep): Database session
        response (Response): FastAPI response object
        request (Request): FastAPI request object
    
    Returns:
        FileResponse: The requested file
    """
    # Validate input to prevent null character injection
    if not ruta_archivo or '\0' in ruta_archivo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ruta de archivo inválida"
        )

    ftp_server: Optional[ftplib.FTP] = request.app.ftp
    if not ftp_server:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="No hay conexión con el servidor FTP."
        )
    try:
        ftp_server.cwd('/')
    except Exception as e:
        print(f"Error regresando al directorio inicial: {e}")
    
    try:
        # Store the initial directory

        # Validate planificacion exists in database
        query = select(Planificacion_Profesor).where(Planificacion_Profesor.archivo == ruta_archivo)
        planificacion = session.exec(query).one_or_none()

        if not planificacion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Planificación no encontrada para la ruta especificada."
            )
        
        # Safely split path
        directorio, filename = os.path.split(ruta_archivo)
        
        try:
            # Change to correct directory in FTP
          
            ftp_server.cwd(directorio)  
        except Exception as e:
            print(f"Error cambiando directorio FTP: {e}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El directorio {directorio} no existe en el servidor FTP."
            )

        # Create a temporary file for download
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            try:
                # Download file directly to temporary file
                ftp_server.retrbinary(f"RETR {filename}", temp_file.write)
            except Exception as e:
                print(f"Error descargando archivo: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error al descargar el archivo desde el servidor FTP."
                )
            finally:
                # Always return to the initial directory
                try:
                    ftp_server.cwd('/')
                except Exception as e:
                    print(f"Error regresando al directorio inicial: {e}")

        # Return file as a downloadable response
        return FileResponse(
            path=temp_file.name, 
            media_type='application/pdf', 
            filename=filename,
            # Optional: add headers for download
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except HTTPException as http_exc:
        # Re-raise HTTP exceptions
        raise http_exc
    
    except Exception as e:
        print(e)
        # Print unexpected errors
        print(f"Error inesperado: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrió un error interno al procesar la solicitud."
        )
    
        # Ensure FTP connection is closed



@router.get("/search/me/", response_description="Listar todas las planificaciones de un profesor", response_model=List[Any])
async def get_all_planificaciones(
    profesor_id: int,
    query: int, 
    mes: str,
    year: str,
    session: SessionDep
) -> Any:
    try:
        # Realizamos el join entre todas las tablas necesarias
        query_planificaciones = (
            select(
                Planificaciones,
                Planificacion_Profesor.id,
                Planificacion_Profesor.planificacion_id,
                Profesores.nombre.label("profesor_nombre"),
                Asignaturas.nombre.label("asignatura_nombre"),
                Asignaturas.curso.label("curso_nombre"),

                Periodo.nombre.label("periodo_nombre"),
                Planificacion_Profesor.profesor_aprobador_id,
                Planificacion_Profesor.profesor_revisor_id,
                Areas.id.label("area_id"),
                Areas.nombre.label("area_nombre"),
                Areas.codigo.label("area_codigo"),
                Planificacion_Profesor.fecha_de_actualizacion,
                Planificacion_Profesor.estado,
                Planificacion_Profesor.archivo,
            )
            .join(Profesores, Planificaciones.profesor_id == Profesores.id)
            .join(Asignaturas, Planificaciones.asignaturas_id == Asignaturas.id)
            .join(Periodo, Planificaciones.periodo_id == Periodo.id)
            .join(Areas, Asignaturas.area_id == Areas.id)
            .join(
                Planificacion_Profesor,
                Planificaciones.id == Planificacion_Profesor.planificacion_id
            )
            .join(
                areas_profesor,
                Planificacion_Profesor.profesor_revisor_id == areas_profesor.id,
                isouter=True
            )
            .where(Planificaciones.profesor_id == profesor_id)  # Filtrar por el ID del profesor asignado
            .where(Planificaciones.periodo_id == query)
            .where(cast(extract('month', Planificaciones.fecha_subida), String).ilike(f'%{mes}%'))
            .where(cast(extract('year', Planificaciones.fecha_subida), String).ilike(f'%{year}%'))
     
        )
        
        # Ejecutar la consulta y obtener los resultados
        planificaciones = session.exec(query_planificaciones).all()

        # Obtener los IDs de profesores aprobadores y revisores
        profesor_aprobador_ids = [p[7] for p in planificaciones if p[7] is not None]
        profesor_revisor_ids = [p[8] for p in planificaciones if p[8] is not None]

        # Consultar nombres de profesores aprobadores
        aprobadores = {}
        if profesor_aprobador_ids:
            query_aprobadores = select(Profesores).where(Profesores.id.in_(profesor_aprobador_ids))
            aprobadores = {p.id: p.nombre for p in session.exec(query_aprobadores)}

        # Consultar nombres de profesores revisores a través de Areas_Profesor
        revisores = {}
        if profesor_revisor_ids:
            query_revisores = (
                select(areas_profesor, Profesores.nombre)
                .join(Profesores, areas_profesor.profesor_id == Profesores.id)
                .where(areas_profesor.id.in_(profesor_revisor_ids))
            )
            revisores = {ap.id: nombre for ap, nombre in session.exec(query_revisores)}

        # Crear una lista de resultados con los campos deseados
        result = [
            {
                "titulo": planificacion.titulo,
                "descripcion": planificacion.descripcion,
                "fecha_subida": planificacion.fecha_subida,
                "profesor_id": planificacion.profesor_id,
                "asignaturas_id": planificacion.asignaturas_id,
                "periodo_id": planificacion.periodo_id,
                "id": id,
                "id_planificacion": planificacion_id,
                "profesor_nombre": profesor_nombre,
                "periodo_nombre": periodo_nombre,
                "asignatura_nombre": asignatura_nombre,
                "curso_nombre": curso_nombre,
                "area_id": area_id,
                "area_nombre": area_nombre,
                "area_codigo": area_codigo,
                "profesor_aprobador_id": profesor_aprobador_id,
                "profesor_aprobador_nombre": aprobadores.get(profesor_aprobador_id) if profesor_aprobador_id else None,
                "profesor_revisor_id": profesor_revisor_id,
                "profesor_revisor_nombre": revisores.get(profesor_revisor_id) if profesor_revisor_id else None,
                "fecha_de_actualizacion": fecha_de_actualizacion,
                "estado": estado,
                "archivo": archivo,
            }
            for (
                planificacion, id, planificacion_id, profesor_nombre, asignatura_nombre,curso_nombre, periodo_nombre,
                profesor_aprobador_id, profesor_revisor_id,
                area_id, area_nombre, area_codigo,
                fecha_de_actualizacion, estado, archivo
            ) in planificaciones
        ]
        
        return result

    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener las planificaciones: {str(e)}"
        )


@router.post("/comentar-planificacion/", response_description="Comentar una planificación", status_code=status.HTTP_201_CREATED)
async def comentar_planificacion(
    comentario: Comentarios_Dto,
    session: SessionDep 
):
    try:
        # Consulta la planificación del profesor
        query_planificacion_profesor = select(Planificacion_Profesor).where(
            Planificacion_Profesor.id == comentario.planificacion_profesor_id
        )
        result = session.exec(query_planificacion_profesor)
        planificacion_profesor = result.first()  # Devuelve el primer resultado

        if not planificacion_profesor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Planificación no encontrada"
            )

        # Consulta al profesor
        profesor_query = select(Profesores).where(Profesores.id == comentario.profesor_id)
        fechtprofesor = session.exec(profesor_query).one_or_none()

        if not fechtprofesor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profesor no encontrado"
            )

        # Crear el objeto de comentario
        comentario_data = Comentarios(
            id_profesor=comentario.profesor_id,
            planificacion_profesor_id=comentario.planificacion_profesor_id,
            comentario=comentario.comentario,
            fecha_enviado=datetime.now(pytz.timezone('America/Guayaquil'))
        )

        # Guardar el comentario en la base de datos
        session.add(comentario_data)
        session.commit()
        session.refresh(comentario_data)

        # Enviar el correo electrónico
        try:
            sender_email(
                fechtprofesor.email,  # Asegúrate de que esta propiedad exista
                f"Comentario de Planificación: {comentario.nombre_planificacion}_{comentario.periodo_nombre}",
                comentario.comentario  # El comentario como cuerpo del correo
            )
        except Exception as e:
            print(f"Error al enviar el email: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Fallo al enviar el email"
            )

        return comentario_data
        
    except Exception as e:
        print(f"Error en la API: {e}")
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al guardar el comentario en la base de datos"
        ) from e




@router.get("/comentarios/", response_description="Listar todos los comentarios de planificaciones", response_model=List[Any])
async def get_all_comentarios_planificacion(
    planificacion_profesor_id: int,
    session: SessionDep
):
    
    print(planificacion_profesor_id)
    try:
        # Realizamos el join entre todas las tablas necesarias
        query = (
            select(Comentarios)
            .where(Comentarios.planificacion_profesor_id == planificacion_profesor_id)
            
            )
        
        # Ejecutar la consulta y obtener los resultados
        comentarios = session.exec(query).all()
        

        # Obtener los IDs de profesores 
        profesor_ids = [p.id_profesor for p in comentarios if p.id_profesor is not None]
        
        # Consultar nombres de profesores
        nombres_profesores = select(Profesores).where(Profesores.id.in_(profesor_ids))
        nombres_profesores = session.exec(nombres_profesores).all()
        
        nombres_profesores = {p.id: p.nombre for p in nombres_profesores}
        
        # Crear una lista de resultados con los campos deseados
        result = [
            {
                "id": comentario.id,
                "id_profesor": comentario.id_profesor,
                "planificacion_profesor_id": comentario.planificacion_profesor_id,
                "comentario": comentario.comentario,
                "fecha_enviado": comentario.fecha_enviado,
                "nombre_profesor": nombres_profesores.get(comentario.id_profesor),
            }
            for comentario in comentarios
        ]
        
        return result
        
        
        # Consultar nombres de profesores aprobadores
        # Crear una lista de resultados con los campos deseados con los nombres de los profesores
        
        
        # result = [
        #     {
        #         "id": comentario.id,
        #         "id_profesor": comentario.id_profesor,
        #         "planificacion_profesor_id": comentario.planificacion_profesor_id,
        #         "comentario": comentario.comentario,
        #         "fecha_enviado": comentario.fecha_enviado,
        #     }
        #     for comentario in comentarios
        # ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener las planificaciones: {str(e)}"
        )   
                

@router.delete("/delete/{planificacion_id}", response_description="Eliminar una planificación", status_code=status.HTTP_204_NO_CONTENT)
async def delete_planificacion(planificacion_id: int, session: SessionDep, request: Request) :
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

        # Verificar si existe un archivo asociado y eliminarlo de FTP
        planificacion_profesor = session.exec(
            select(Planificacion_Profesor).where(Planificacion_Profesor.planificacion_id == planificacion_id)
        ).one_or_none()
        
        if planificacion_profesor:
            ftp_server: Optional[ftplib.FTP] = request.app.ftp
            if ftp_server:
                
                if planificacion_profesor.archivo is not None:
                                        
                    try:
                        ftp_server.delete(planificacion_profesor.archivo)
                    except Exception as e:
                        print(f"Error al eliminar archivo del FTP: {e}")
            
            # Eliminar archivo de la base de datos
          

        # Eliminar la planificación de la base de datos
        session.delete(existing_planificacion)
        session.commit()

        return {"message": "Planificación eliminada correctamente"}

    except SQLAlchemyError as e:
        session.rollback()
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al eliminar la planificación"
        ) from e   

