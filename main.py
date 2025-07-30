from typing import List
from fastapi import FastAPI, Depends,HTTPException, File, UploadFile, status
from fastapi.responses import FileResponse, PlainTextResponse, Response
from pydantic import BaseModel

from ResidenceBack.Parser import parse_xsd_from_url
from .FileValidation import validation_main
from .Auth import create_jwt_token,verify_jwt_from_cookie
from .UpdateXML import find_element_definition,is_element_additive,find_element_definition,find_or_create_element_path,handle_complex_element_update,parse_complex_value
import xml.etree.ElementTree as ET
from fastapi.middleware.cors import CORSMiddleware
import json
from typing import Dict
import os
import requests as http_requests

xsd_urls = {
        "rizoma": "http://localhost:8080/SECIHTIServ/Rizoma.xsd",
        "prodep": "http://localhost:8080/PRODEPServ/PRODEP.xsd",
        "tecnm": "http://localhost:8080/TecNMServ/TecNM.xsd",
        "base": "./ResidenceBack/files/Base.json",
        "mapa": "./ResidenceBack/files/Mapeo.json"
    }

xml_urls = {
    "tecnm": f"http://localhost:8080/TecNMServ/files/",
    "prodep": f"http://localhost:8080/PRODEPServ/files/",
    "rizoma": f"http://localhost:8080/SECIHTIServ/files/"
}

users = [
    {"id":1,
    "email":"adminTec@gmail.com",
    "name":"Federico DelRazo Lopez",
    "password":"12345678",
    "role":"admin",
    "institution":"TecNM"},
    {"id":2,
     "name":"Juan Perez Lopez",
    "email":"user@gmail.com",
    "password":"12345678",
    "role":"user"},
    {"id":3,
     "name":"Maria Garcia Hernandez",
    "email":"adminPRODEP@gmail.com",
    "password":"12345678",
    "role":"admin",
    "institution":"PRODEP"}
    ]

class SharingUpdate(BaseModel):
    uniqueId: str
    institutions: List[str]

class UserCredentials(BaseModel):
    email: str
    password: str

class UpdateXmlData(BaseModel):
    institution: str
    data: Dict[str, str]

class FieldMapping(BaseModel):
    institution: str
    sourceUniqueId: str
    targetFieldName: str

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
    
    token = create_jwt_token({
        "id": user["id"], 
        "role": user["role"],
        "email": user["email"],
        "institution": user.get("institution", None),
        "name": user["name"]  # Agregar el nombre del usuario
    })  

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
    xsd_path = xsd_urls.get(opt.lower())
    if xsd_path.startswith(('http://','https://')):
        result = parse_xsd_from_url(xsd_path)
    else:
        with open(xsd_path,"r",encoding="utf-8") as f:
            result = json.load(f)
    return result

@app.post("/api/update-base")
async def update_base_data(changes_data: dict, institute: str = None):
    try:
        base_file_path = xsd_urls.get("base")
        mapping_file_path = xsd_urls.get("mapa")

        try:
            with open(base_file_path, "r", encoding="utf-8") as f:
                current_base = json.load(f)
        except FileNotFoundError:
            current_base = {}
        
        try:
            with open(mapping_file_path, "r", encoding="utf-8") as f:
                mappings = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            mappings = {} 

        manual_elements = changes_data.get("manual", [])
        automated_elements = changes_data.get("automated", [])
        removed_elements = changes_data.get("removed", [])
        pending_mappings = changes_data.get("mappings", {})
        
        all_elements = manual_elements + automated_elements

        if institute and pending_mappings:
            if institute not in mappings:
                mappings[institute] = {}
            mappings[institute].update(pending_mappings)
        
        elements_added = 0
        elements_removed = 0
        mappings_removed = 0

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
            
            if not parent_element and unique_id and "_" in unique_id:
                unique_id_parts = unique_id.split("_")
                if len(unique_id_parts) > 2:
                    parent_element = unique_id_parts[1]
                
            if section not in current_base:
                current_base[section] = []
            
            existing_element = None

            for existing in current_base[section]:
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
                element_data_copy =  element_data.copy()
                element_data_copy.pop("children", None)

                element_with_context = {
                    **element_data_copy,
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
        
        for element in removed_elements:
            unique_id = element.get("uniqueId", "")
            section = element.get("section")
            institution_to_remove_from = institute
            
            if not section and unique_id and "_" in unique_id:
                section = unique_id.split("_")[0]
            
            if section in current_base:
                element_to_fully_delete = -1
                
                for i, existing in enumerate(current_base[section]):
                    if existing.get("context", {}).get("uniqueId") == unique_id:
                        current_institutions = existing.get("context", {}).get("institution", [])
                        
                        if not isinstance(current_institutions, list):
                            current_institutions = [current_institutions] if current_institutions else []
                        
                        if institution_to_remove_from and institution_to_remove_from in current_institutions:
                            current_institutions.remove(institution_to_remove_from)
                            elements_removed += 1

                            if institution_to_remove_from in mappings and unique_id in mappings[institution_to_remove_from]:
                                del mappings[institution_to_remove_from][unique_id]
                                mappings_removed += 1
                                if not mappings[institution_to_remove_from]:
                                    del mappings[institution_to_remove_from]

                            if not current_institutions:
                                element_to_fully_delete = i
                            else:
                                existing["context"]["institution"] = current_institutions
                        break
                
                if element_to_fully_delete != -1:
                    current_base[section].pop(element_to_fully_delete)
                
                if not current_base[section]:
                    del current_base[section]
                
        with open(base_file_path, "w", encoding="utf-8") as f:
            json.dump(current_base, f, indent=2, ensure_ascii=False)
        
        with open(mapping_file_path, "w", encoding="utf-8") as f:
            json.dump(mappings, f, indent=2, ensure_ascii=False)
        
        return {
            "success": True,
            "message": f"Base.json y Mapeos actualizados. {elements_added} agregados, {elements_removed} removidos, {mappings_removed} mapeos eliminados.",
            "elements_added": elements_added,
            "elements_removed": elements_removed,
            "mappings_removed": mappings_removed
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error al actualizar la base de datos: {str(e)}"
        )

@app.post("/api/update-sharing")
async def update_sharing_settings(update_data: SharingUpdate):
    try:
        base_file_path = xsd_urls.get("base")
        
        try:
            with open(base_file_path, "r", encoding="utf-8") as f:
                current_base = json.load(f)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Base.json not found")

        element_found = False
        for section, elements in current_base.items():
            for element in elements:
                if element.get("context", {}).get("uniqueId") == update_data.uniqueId:
                    element["context"]["institution"] = update_data.institutions
                    element_found = True
                    break
            if element_found:
                break
        
        if not element_found:
            raise HTTPException(status_code=404, detail="Elemento no encontrado en Base.json")

        with open(base_file_path, "w", encoding="utf-8") as f:
            json.dump(current_base, f, indent=2, ensure_ascii=False)
            
        return {"success": True, "message": f"Permisos para {update_data.uniqueId} actualizados."}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al actualizar permisos: {str(e)}"
        )
    
@app.post("/api/update-xml")
async def update_xml(update_data: UpdateXmlData, payload: dict = Depends(verify_jwt_from_cookie)):
    try:
        username = payload.get("name")
        if not username:
            raise HTTPException(status_code=401, detail="Token inválido: falta el nombre de usuario")

        institution = update_data.institution
        institution_key = institution.lower()
        base_url = xml_urls.get(institution_key)

        if not base_url:
            raise HTTPException(status_code=404, detail=f"No se encontró la URL para la institución: {institution}")

        try:
            service_name = base_url.split('/')[3]
            xml_file_path = f"/srv/{service_name}/files/{username}.xml"
        except IndexError:
            raise HTTPException(status_code=500, detail=f"No se pudo analizar la URL para la institución: {institution}")

        mapping_file_path = os.path.join(xsd_urls.get("mapa"))
        rizoma_xsd = get_xsd_structure("rizoma")

        with open(mapping_file_path, "r", encoding="utf-8") as f:
            mappings = json.load(f)

        updates_made = {}

        for source_unique_id, new_value in update_data.data.items():
            element_def = find_element_definition(rizoma_xsd, source_unique_id)
            is_additive = is_element_additive(element_def)
            parsed_value = parse_complex_value(new_value)

            target_unique_id = mappings.get(institution, {}).get(source_unique_id)
            if not target_unique_id:
                continue

            if not os.path.exists(xml_file_path):
                continue

            try:
                tree = ET.parse(xml_file_path)
                root = tree.getroot()

                target_parts = target_unique_id.split('_')[1:]
                if not target_parts:
                    continue

                parent_element = find_or_create_element_path(root, target_parts)
                element_name = target_parts[-1]
                handle_complex_element_update(
                    parent_element,
                    element_name,
                    parsed_value,
                    is_additive
                )

                tree.write(xml_file_path, encoding='utf-8', xml_declaration=True)

                if institution not in updates_made:
                    updates_made[institution] = []
                updates_made[institution].append({
                    "source_id": source_unique_id,
                    "target_id": target_unique_id,
                    "is_additive": is_additive,
                    "updated": True
                })

            except ET.ParseError as e:
                print(f"Error parsing XML file {xml_file_path}: {e}")
                continue
            except Exception as e:
                print(f"Error updating XML file {xml_file_path}: {e}")
                continue

        return {
            "success": True,
            "message": f"Archivo XML para {institution} actualizado correctamente.",
            "updates_made": updates_made
        }

    except Exception as e:
        print(f"Error al actualizar el XML dinámicamente: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")

@app.post("/api/update-mapping")
async def update_mapping(mapping_data: FieldMapping, payload: dict = Depends(verify_jwt_from_cookie)):
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="No tienes permiso para realizar esta acción")

    mapping_file_path = os.path.join(os.path.dirname(__file__), "files", "Mapeo.json")
    
    try:
        with open(mapping_file_path, "r+", encoding="utf-8") as f:
            mappings = json.load(f)
            
            if mapping_data.institution not in mappings:
                mappings[mapping_data.institution] = {}
            
            mappings[mapping_data.institution][mapping_data.sourceUniqueId] = mapping_data.targetUniqueId
            
            f.seek(0)
            json.dump(mappings, f, indent=2)
            f.truncate()

        return {"success": True, "message": "Mapeo guardado correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al guardar el mapeo: {str(e)}")

@app.get("/api/xml-urls")
async def get_xml_urls():
    return xml_urls