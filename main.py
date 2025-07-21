from fastapi import FastAPI, Depends,HTTPException, File, UploadFile, status
from fastapi.responses import FileResponse, PlainTextResponse, Response
from pydantic import BaseModel
from .FileValidation import validation_main
from .Auth import create_jwt_token,verify_jwt_from_cookie
import xml.etree.ElementTree as ET
from fastapi.middleware.cors import CORSMiddleware

users = [
    {"id":1,
    "email":"adminTec@gmail.com",
    "name":"FedericoDelRazoLopez",
    "password":"12345678",
    "role":"admin"},
    {"id":2,
     "name":"JuanPerezLopez",
    "email":"user@gmail.com",
    "password":"12345678",
    "role":"user"},
    {"id":3,
     "name":"MariaGarciaHernandez",
    "email":"adminPRODEP@gmail.com",
    "password":"12345678",
    "role":"admin"}
    ]

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
async def login(credentials: UserCredentials, response:Response):
    user = next((u for u in users if u["email"] == credentials.email), None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail = "Email incorrecto"
        )
    
    if user["password"] != credentials.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail = "Contraseña incorrecta"
        )
    
    token = create_jwt_token({"id": user["id"], 
                              "role": user["role"],
                              "email":user["email"] })
    
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        secure=False,
        samesite="Lax",
        max_age=60*60*2,
        path="/"
    )

    return {
        "success":True,
        "role": user["role"],
        "id": user["id"]
    }

@app.post("/logout")
async def logout(response: Response):
    try:
        response.delete_cookie("token")
        return {"success": True}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Error al cerrar sesión")
    


@app.get("/usuario_actual")
async def usuario_actual(payload: dict = Depends(verify_jwt_from_cookie)):
    return {"usuario": payload}

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
            return {"valido": True, "data": json_data}  # Retorna un solo JSON válido
        else:
            raise HTTPException(status_code=code, detail="Documento XML inválido")

    except Exception as e:
        print(f"Error en validación: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")