from datetime import date
from typing import Optional
import uuid

from sqlmodel import SQLModel,Field


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


from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import date

class Asignaturas(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    fecha_creacion: Optional[date] = Field(default_factory=date.today)
    codigo: str = Field(..., max_length=50, description="Código único de la asignatura")
    nombre: str = Field(..., max_length=100, description="Nombre de la asignatura")
    descripcion: Optional[str] = Field(default=None, description="Descripción de la asignatura")



class Periodo(SQLModel, table=True):
    id: int = Field(primary_key=True, default=None)
    fecha_inicio: date
    nombre: str
    descripcion: str = None
    fecha_fin: date
    fecha_creacion: date = Field(default_factory=date.today)



