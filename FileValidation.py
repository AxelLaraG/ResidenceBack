import os
import xml.etree.ElementTree as ET
from lxml import etree
from fastapi import UploadFile
from io import BytesIO

dir_base = os.path.dirname(os.path.abspath(__file__))

def validation_main(xml_file: UploadFile) -> tuple[bool, list]:
    content = xml_file.file.read()  
    xml_file.file.seek(0)  

    result, code = validate_schema(content)
    if result:
        result, code = validate_xml_with_dtd(content)
        if result:
            json = xml_to_json(content)
            return True, 0, json
        else:
            return False, code, {}
    else:
        return False, code, {}

def validate_schema(xml_content: bytes) -> tuple[bool, list]:
    try:
        schema_path = os.path.join(dir_base, "files/XSD/Rizoma.xsd")
        
        with open(schema_path, 'rb') as xsd_file:
            xmlschema_doc = etree.parse(xsd_file)
            xmlschema = etree.XMLSchema(xmlschema_doc)
        
        xml_doc = etree.parse(BytesIO(xml_content))  # Usamos BytesIO para evitar modificar el archivo original
        
        if xmlschema.validate(xml_doc):
            return True, 0
        else:
            validation_errors = [str(error) for error in xmlschema.error_log]
            return False, validation_errors  
    
    except Exception as e:
        return False, [f"Error inesperado: {str(e)}"]

def validate_xml_with_dtd(xml_content: bytes) -> tuple[bool, int]:
    try:
        dtd_path = os.path.join(dir_base, "files/DTD/Rizoma.dtd")

        if not os.path.exists(dtd_path):
            raise FileNotFoundError(f"El archivo DTD no se encuentra en la ruta: {dtd_path}")
        
        with open(dtd_path, 'rb') as dtd_file:
            dtd = etree.DTD(dtd_file)
        
        xml_doc = etree.parse(BytesIO(xml_content))  # Reusamos BytesIO para evitar problemas
        
        if dtd.validate(xml_doc):
            return True, 0
        else:
            print(dtd.error_log.filter_from_errors()) 
            return False, 1003  
            
    except FileNotFoundError as fnf_error:
        print(fnf_error)  
        return False, 1004
    except etree.XMLSyntaxError as syntax_error:
        print(f"Error de sintaxis XML: {syntax_error}")
        return False, 1005
    except Exception as e:
        print(f"Error inesperado: {e}")
        return False, 1004
    
def xml_to_json(xml_content: bytes) -> dict:
    try:
        tree = ET.parse(BytesIO(xml_content))
        root = tree.getroot()

        def parse_element(element):
            parsed_data = {}
            # Convertir atributos
            if element.attrib:
                parsed_data["@attributes"] = element.attrib
            # Convertir hijos
            for child in element:
                child_data = parse_element(child)
                if child.tag in parsed_data:
                    if isinstance(parsed_data[child.tag], list):
                        parsed_data[child.tag].append(child_data)
                    else:
                        parsed_data[child.tag] = [parsed_data[child.tag], child_data]
                else:
                    parsed_data[child.tag] = child_data
            # Convertir texto si es relevante
            text = element.text.strip() if element.text else None
            if text:
                if parsed_data:
                    parsed_data["#text"] = text
                else:
                    return text
            return parsed_data

        return {root.tag: parse_element(root)}
    
    except Exception as e:
        return {"error": f"Error al convertir XML a JSON: {str(e)}"}