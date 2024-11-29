import ftplib
from typing import Optional
from fastapi import Depends, FastAPI
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
from api.deps import SessionDep, cerrar_conexion_ftp, conexion_ftp


origins = [
    "*"
]




@asynccontextmanager
async def lifespan(app: FastAPI):

    ftp: Optional[ftplib.FTP] = conexion_ftp()
    # device = 'cuda' if torch.cuda.is_available() else 'cpu'
    # model = YOLO('Modelos/best.pt').to(device)
    app.ftp = ftp
    print('inicializao')
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



app.include_router(api_router)