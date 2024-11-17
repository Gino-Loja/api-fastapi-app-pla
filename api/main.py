from fastapi import APIRouter

from api.routes import asignaturas, auth, periodos, profesores

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

api_router.include_router(profesores.router, prefix="/profesor", tags=["profesor"])
api_router.include_router(asignaturas.router, prefix="/asignatura", tags=["asignatura"])
api_router.include_router(periodos.router, prefix="/periodo", tags=["periodo"])
