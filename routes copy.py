from fastapi import APIRouter, Body, Request, Response, HTTPException, status,File, UploadFile, responses 
from fastapi.encoders import jsonable_encoder
#from model import  Prediccion, Datos_manuales, Estaciones
from typing import List,Annotated
#import numpy as np
import os
router = APIRouter()
from PIL import Image

from test import detect
import io

# @router.get("/query", response_description="Lista el primer documento insertado", response_model=Prediccion)
# def get_datos_sensores(request: Request):
    
#     return {"incidencia": prediction[0]}


# @router.post("/predict", response_description="Create a new book", status_code=status.HTTP_201_CREATED, response_model=Prediccion)
# def obtener_prediccion_actual(request: Request, datos_manules: Datos_manuales = Body(...)):
#     datos_manules = jsonable_encoder(datos_manules)
#     datos_sensores: List[Datos_sensor] = list(
#         request.app.database["sacha"].find().sort([('_id', -1)]).limit(1))

#     X_test = np.array([
#         datos_manules["fruto"], datos_manules["severidad"], datos_sensores[0][
#             "rain"], datos_sensores[0]["temperatura"], datos_sensores[0]["rh"],
#         datos_sensores[0]["dew_point"], datos_sensores[0]["wind_speed"],
#         datos_sensores[0]["gust_speed"],
#         datos_sensores[0]["wind_direction"]
#     ])
#     prediction = request.app.model.predict(X_test.reshape(1, -1))
#     return {"incidencia": prediction[0]}


@router.post("/upload", response_description="Validar residuos", status_code=status.HTTP_201_CREATED)
def obtener_prediccion_actual(request: Request, estaciones = Body(...)):
    estaciones = jsonable_encoder(estaciones)
    #datos_sensores: List[Datos_sensor] = list(
        #request.app.database[estaciones["estacion"]].find().sort([('_id', -1)]).limit(1))

    return 0

@router.post("/uploadfile/")
async def create_upload_file(file: UploadFile, request: Request):
    
    image_processed, cls = detect(file.file, request.app.model)
    
    image_send = io.BytesIO(image_processed)    
    
   
    return  responses.StreamingResponse(image_send, media_type='image/jpeg', headers={"clase": str(cls)})
         
 
@router.post("/uploadfile/image/")
async def create_file(file: Annotated[bytes, File()]):
    #print(file)
    return {"file_size": file}


@router.get("/get_image/")
async def get_image():
    file_path = "carton.jpg"
    if os.path.exists(file_path):
        return responses.StreamingResponse(file_path, media_type='image/jpeg')
    else:
        return {"error": "File not found"}