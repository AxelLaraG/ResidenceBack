from fastapi import FastAPI, Depends,HTTPException, File, UploadFile, status
from fastapi.responses import FileResponse, PlainTextResponse, Response
from pydantic import BaseModel

from ResidenceBack.Parser import parse_xsd_from_file, parse_xsd_from_url
from .FileValidation import validation_main
from .Auth import create_jwt_token,verify_jwt_from_cookie
import xml.etree.ElementTree as ET
from fastapi.middleware.cors import CORSMiddleware
import json

users = [
    {"id":1,
    "email":"adminTec@gmail.com",
    "name":"FedericoDelRazoLopez",
    "password":"12345678",
    "role":"admin",
    "institution":"TecNM"},
    {"id":2,
     "name":"JuanPerezLopez",
    "email":"user@gmail.com",
    "password":"12345678",
    "role":"user"},
    {"id":3,
     "name":"MariaGarciaHernandez",
    "email":"adminPRODEP@gmail.com",
    "password":"12345678",
    "role":"admin",
    "institution":"PRODEP"}
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
                              "email":user["email"],
                              "institution": user["institution"] if "institution" in user else None})
    
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

@app.get("/api/xsd")
def get_xsd_structure(opt:str =""):
    xsd_urls = {
        "rizoma": "http://localhost:8080/SECIHTIServ/Rizoma.xsd",
        "prodep": "http://localhost:8080/PRODEPServ/PRODEP.xsd",
        "tecnm": "http://localhost:8080/TecNMServ/TecNM.xsd",
        "base": "./files/XSD/Base.xsd"
    }
    xsd_path = xsd_urls.get(opt.lower())
    if xsd_path.startswith(('http://','https://')):
        result = parse_xsd_from_url(xsd_path)
    else:
        with open("./ResidenceBack/files/Base.json","r",encoding="utf-8") as f:
            result = json.load(f)
    return result

@app.post("/api/update-base")
async def update_base_data(changes_data: dict):
    try:
        base_file_path = "./ResidenceBack/files/Base.json"
        
        # Leer el archivo Base.json actual
        try:
            with open(base_file_path, "r", encoding="utf-8") as f:
                current_base = json.load(f)
        except FileNotFoundError:
            # Si no existe, crear estructura básica
            current_base = {}
        
        # Procesar los cambios recibidos
        manual_elements = changes_data.get("manual", [])
        automated_elements = changes_data.get("automated", [])
        
        # Combinar todos los elementos
        all_elements = manual_elements + automated_elements
        
        print(f"Procesando {len(all_elements)} elementos para agregar a Base.json")
        print(f"Estructura recibida: {changes_data}")
        
        # Debug: mostrar algunos elementos de ejemplo
        if all_elements:
            print(f"Ejemplo de elemento: {all_elements[0]}")
        
        elements_added = 0
        
        # Agregar elementos por sección
        for element in all_elements:
            element_name = element.get("name")
            element_data = element.get("data", {})
            unique_id = element.get("uniqueId", "")
            
            # Extraer la sección del uniqueId
            # Los IDs tienen formato: "seccion_elemento" o "seccion_parentelement_elemento"
            if unique_id and "_" in unique_id:
                section = unique_id.split("_")[0]
            else:
                print(f"⚠️ No se pudo determinar la sección para {element_name}")
                continue
            
            if not section or not element_name:
                print(f"⚠️ Datos faltantes: section={section}, name={element_name}")
                continue
                
            # Asegurar que la sección existe en el base
            if section not in current_base:
                current_base[section] = []
            
            # Verificar si el elemento ya existe
            element_exists = any(
                existing.get("name") == element_name 
                for existing in current_base[section]
            )
            
            if not element_exists:
                current_base[section].append(element_data)
                elements_added += 1
                print(f"✅ Agregado: {element_name} a sección {section}")
            else:
                print(f"⚠️ Ya existe: {element_name} en sección {section}")
        
        # Guardar el archivo actualizado
        with open(base_file_path, "w", encoding="utf-8") as f:
            json.dump(current_base, f, indent=2, ensure_ascii=False)
        
        return {
            "success": True,
            "message": f"Base.json actualizado. Se agregaron {elements_added} elementos nuevos de {len(all_elements)} procesados",
            "elements_processed": len(all_elements),
            "elements_added": elements_added
        }
        
    except Exception as e:
        print(f"Error al actualizar Base.json: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error al actualizar la base de datos: {str(e)}"
        )

