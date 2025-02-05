from fastapi import APIRouter, Depends

from api.routes import areas, asignaturas, auth, informe, periodos, planificaciones, profesores, dashboard

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

api_router.include_router(profesores.router, prefix="/profesor", tags=["profesor"], dependencies=[Depends(auth.get_current_active_user)])
api_router.include_router(areas.router, prefix="/area", tags=["area"],  )

api_router.include_router(asignaturas.router, prefix="/asignatura", tags=["asignatura"],  dependencies=[Depends(auth.get_current_active_user)])
api_router.include_router(periodos.router, prefix="/periodo", tags=["periodo"],  dependencies=[Depends(auth.get_current_active_user)])
api_router.include_router(planificaciones.router, prefix="/planificacion", tags=["planificacion"],  dependencies=[Depends(auth.get_current_active_user)])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(auth.get_current_active_user)])
api_router.include_router(informe.router, prefix="/informe", tags=["informe"], dependencies=[Depends(auth.get_current_active_user)])
