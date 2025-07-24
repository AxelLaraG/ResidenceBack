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
async def update_base_data(changes_data: dict, institute: str = None):
    try:
        base_file_path = "./ResidenceBack/files/Base.json"
        
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
        
        elements_added = 0
        
        # Agregar elementos por sección
        for element in all_elements:
            element_name = element.get("name")
            element_data = element.get("data", {})
            unique_id = element.get("uniqueId", "")
            section = element.get("section")
            parent_element = element.get("parentElement")
            institution = institute
            context = element.get("context", {})
            
            if not section and unique_id and "_" in unique_id:
                section = unique_id.split("_")[0]
            
            # Si no tenemos el parent_element, extraerlo del uniqueId
            if not parent_element and unique_id and "_" in unique_id:
                unique_id_parts = unique_id.split("_")
                if len(unique_id_parts) > 2:
                    parent_element = unique_id_parts[1]
                
            if section not in current_base:
                current_base[section] = []
            
            existing_element = None

            for existing in current_base[section]:
                print(existing)
                if existing.get("context", {}).get("uniqueId") == unique_id:
                    existing_element = existing
                    break

            if existing_element:
                current_institutions = existing_element.get("context").get("institution", [])

                if not isinstance(current_institutions,list):
                    current_institutions = [current_institutions] if current_institutions else []

                if institution and institution not in current_institutions:
                    current_institutions.append(institution)
                    existing_element["context"]["institution"] = current_institutions
            else:
                element_with_context = {
                    **element_data,  # Incluir todos los datos originales del elemento
                    "context": {
                        "section": section,
                        "parent": parent_element,
                        "path": context.get("path", [element_name]),
                        "uniqueId": unique_id,
                        "institution": [institution] if institution else [],
                    }
                }

                current_base[section].append(element_with_context)
                elements_added += 1
                
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
        raise HTTPException(
            status_code=500, 
            detail=f"Error al actualizar la base de datos: {str(e)}"
        )

