from fastapi import FastAPI, HTTPException, File, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from validation import validation_main
import xml.etree.ElementTree as ET
from fastapi.middleware.cors import CORSMiddleware


users = {
    "axmadlar@gmail.com":"12345678",
    "usuario2@gmail.com":"12345678",
    "usuario3@gmail.com":"12345678"
}

class UserCredentials(BaseModel):
    email: str
    password: str

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/login")
async def login(credentials: UserCredentials):
    if credentials.email not in users:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email incorrecto",
        )
    
    if users[credentials.email] != credentials.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Contraseña incorrecta",
        )
    
    return {"message": "Inicio de sesión exitoso", "email": credentials.email}

@app.post("/xml_gen")
async def xml_generator(datos: dict):
    try:
        # Crear el elemento raíz <cvu>
        cvu = ET.Element("cvu", {
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"
        })

        # Crear la sección <personalData>
        personal_data = ET.SubElement(cvu, "personalData")

        # Agregar solo los datos seleccionados
        for clave, valor in datos.items():
            ET.SubElement(personal_data, clave).text = valor

        # Convertir el árbol XML a una cadena con la declaración XML
        xml_string = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml_string += ET.tostring(cvu, encoding="unicode")

        # Retornar el archivo XML como respuesta
        return Response(content=xml_string, media_type="application/xml")

    except Exception as e:
        print(f"Error en la generación del XML: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")

@app.post("/upload")
async def upload_xml(documento_xml: UploadFile = File(...)):
    try:
        result, code, json_data = validation_main(documento_xml)

        if result:
            print("Everything is OK")
            print(json_data)
            return {"valido": True, "data": json_data}  # Retorna un solo JSON válido
        else:
            raise HTTPException(status_code=code, detail="Documento XML inválido")

    except Exception as e:
        print(f"Error en validación: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")