from datetime import date
from typing import Optional
import uuid
from datetime import datetime

from fastapi import UploadFile
from sqlmodel import Relationship, SQLModel,Field


# class Datos_manuales(BaseModel):
#     fruto: StopIteration
#     severidad: int

# class Prediccion(BaseModel):
#     incidencia:int

# class Datos_manuales(BaseModel):
#     fruto:int
#     severidad:int

# class Estaciones(BaseModel):
#     estacion:str

class Profesores(SQLModel, table=True):
    #__tablename__ = "profesores"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(..., title="Nombre del Profesor")
    email: str = Field(..., title="Email del Profesor", index=True, unique=True)
    fecha_creacion: Optional[date] = Field(default=date.today(), title="Fecha de Creación")
    password: Optional[str] = Field(default=None, title="Contraseña")
    cedula: Optional[str] = Field(default=None, title="Cédula")
    telefono: Optional[str] = Field(default=None, title="Teléfono")
    direccion: Optional[str] = Field(default=None, title="Dirección")
    rol: Optional[str] = Field(default=None, title="Rol")

class Roles(SQLModel):
    #__tablename__ = "profesores"
    rol:  str
    numero_profesores: int



class Total_profesores(SQLModel):
    #__tablename__ = "profesores"
  
    total: int






class Periodo(SQLModel, table=True):
    id: int = Field(primary_key=True, default=None)
    fecha_inicio: date
    nombre: str
    descripcion: str = None
    fecha_fin: date
    fecha_creacion: date = Field(default_factory=date.today)

class Planificaciones(SQLModel, table=True):

    id: Optional[int] = Field(default=None, primary_key=True)  # Clave primaria
    titulo: str = Field(index=True)  # Campo de texto con índice
    descripcion: Optional[str] = None  # Campo opcional
    fecha_subida: date  # Marca de tiempo
    profesor_id: Optional[int] = Field(foreign_key="profesores.id")  # Clave foránea hacia "profesores"
    asignaturas_id: Optional[int] = Field(foreign_key="asignaturas.id")  # Clave foránea hacia "asignaturas"
    periodo_id: Optional[int] = Field(foreign_key="periodo.id") 
    



class Areas(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(..., max_length=100, description="Nombre del área")
    codigo: str = Field(..., max_length=50, unique=True, description="Código único del área")


class Asignaturas(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    fecha_creacion: Optional[date] = Field(default_factory=date.today)
    codigo: str = Field(..., max_length=50, description="Código único de la asignatura")
    nombre: str = Field(..., max_length=100, description="Nombre de la asignatura")
    descripcion: Optional[str] = Field(default=None, description="Descripción de la asignatura")
    area_id: Optional[int] = Field(foreign_key="areas.id")
    curso: str = Field(..., max_length=50, description="Curso de la asignatura")


class areas_profesor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profesor_id: int = Field(..., foreign_key="profesores.id", description="ID del profesor relacionado")
    area_id: int = Field(..., foreign_key="areas.id", description="ID del área relacionada")
    fecha_de_ingreso: date = Field(default_factory=date.today, description="Fecha de ingreso del profesor al área")


class Planificacion_Profesor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    planificacion_id: int = Field(..., foreign_key="planificaciones.id", description="ID de la planificación asociada")
    profesor_aprobador_id: Optional[int] = Field(default=None, foreign_key="profesores.id", description="ID del profesor que aprobó")
    fecha_de_actualizacion: Optional[date] = Field(default=None, description="Fecha de actualización")
    archivo: Optional[str] = Field(default=None, description="Archivo relacionado con la planificación")
    estado: Optional[str] = Field(default=None, description="Estado actual de la planificación")
    profesor_revisor_id: Optional[int] = Field(default=None, foreign_key="areas_profesor.id", description="ID del profesor que revisó")

class FormularioSubirPdf(SQLModel, table=False):
    pdf: UploadFile = Field(..., description="Archivo PDF")
    id_planificacion: int = Field(..., description="ID de la planificación")
    area_codigo:str = Field(..., description="Código de la área")
    nombre_usuario:str = Field(..., description="Nombre del usuario")
    id_usuario:int = Field(..., description="ID del usuario")
    nommbre_asignatura:str = Field(..., description="Nombre de la asignatura")
    periodo:str = Field(..., description="Nombre del periodo")
    fecha_subida:date = Field(..., description="Fecha de subida")
    
