import ftplib
from typing import Optional
from fastapi import Depends, FastAPI, Request
from dotenv import dotenv_values
from fastapi import  FastAPI

#from pymongo import MongoClient
#import joblib  # importa las bibliotecas joblib para cargar el
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import select
#import cv2
config = dotenv_values(".env")
from api.main import api_router
from api.deps import SessionDep, cerrar_conexion_ftp, conexion_ftp, reconectar_ftp
from starlette.middleware.base import BaseHTTPMiddleware


origins = [
    "*"
]




@asynccontextmanager
async def lifespan(app: FastAPI):

    ftp: Optional[ftplib.FTP] = conexion_ftp()
    # device = 'cuda' if torch.cuda.is_available() else 'cpu'
    # model = YOLO('Modelos/best.pt').to(device)
    app.ftp = ftp
    yield
    cerrar_conexion_ftp(ftp)



app = FastAPI(lifespan=lifespan)

app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
     
    )

class FTPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Obtén la conexión FTP
        ftp = request.app.ftp
        # Reconectar si es necesario
        ftp = reconectar_ftp(ftp)
        # Actualiza la conexión en la aplicación para que esté disponible en todos los endpoints
        request.app.ftp = ftp
        # Llama al siguiente middleware o endpoint
        response = await call_next(request)
        return response
    
# class FTPMiddleware(BaseHTTPMiddleware):
#     async def dispatch(self, request: Request, call_next):
#         try:
#             # Obtain FTP connection
#             ftp = request.app.ftp
            
#             # More robust reconnection
#             if not ftp or not hasattr(ftp, 'sock') or ftp.sock is None:
#                 ftp = conexion_ftp()
#                 if not ftp:
#                     raise HTTPException(
#                         status_code=503, 
#                         detail="Unable to establish FTP connection"
#                     )
            
#             # Verify connection is active
#             try:
#                 ftp.pwd()  # Check if connection is still alive
#             except ftplib.all_errors:
#                 ftp = conexion_ftp()
            
#             # Update app's FTP connection
#             request.app.ftp = ftp
            
#             response = await call_next(request)
#             return response
        
#         except Exception as e:
#             print(f"FTP Middleware Error: {e}")
#             raise HTTPException(
#                 status_code=500, 
#                 detail="Internal server error with FTP connection"
#             )


app.add_middleware(FTPMiddleware)
app.include_router(api_router)