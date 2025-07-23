import xml.etree.ElementTree as ET
from typing import Dict, List
import requests
import io
import os

def parse_element(element: ET.Element, schema: ET.Element) -> dict:
    name = element.attrib.get("name")
    type_ = element.attrib.get("type")
    min_occurs = element.attrib.get("minOccurs", "1")
    max_occurs = element.attrib.get("maxOccurs", "1")
    attributes = []
    children = []
    base_type = None

    complex_type = element.find("{http://www.w3.org/2001/XMLSchema}complexType")
    if complex_type is not None:
        # Buscar atributos directos del complexType
        for attr in complex_type.findall("{http://www.w3.org/2001/XMLSchema}attribute"):
            attributes.append({
                "name": attr.attrib.get("name"),
                "type": attr.attrib.get("type"),
                "use": attr.attrib.get("use", "optional")
            })

        # Manejar simpleContent con extension
        simple_content = complex_type.find("{http://www.w3.org/2001/XMLSchema}simpleContent")
        if simple_content is not None:
            extension = simple_content.find("{http://www.w3.org/2001/XMLSchema}extension")
            if extension is not None:
                base_type = extension.attrib.get("base")
                # Buscar atributos en la extensión
                for attr in extension.findall("{http://www.w3.org/2001/XMLSchema}attribute"):
                    attributes.append({
                        "name": attr.attrib.get("name"),
                        "type": attr.attrib.get("type"),
                        "use": attr.attrib.get("use", "optional")
                    })

        # Manejar sequence para elementos hijos
        sequence = complex_type.find("{http://www.w3.org/2001/XMLSchema}sequence")
        if sequence is not None:
            for child in sequence.findall("{http://www.w3.org/2001/XMLSchema}element"):
                children.append(parse_element(child, schema))

            for choice in sequence.findall("{http://www.w3.org/2001/XMLSchema}choice"):
                for child in choice.findall("{http://www.w3.org/2001/XMLSchema}element"):
                    children.append(parse_element(child, schema))
        choice = complex_type.find("{http://www.w3.org/2001/XMLSchema}choice")
        if choice is not None:
            for child in choice.findall("{http://www.w3.org/2001/XMLSchema}element"):
                children.append(parse_element(child, schema))
    # Detectar si es simpleContent basado en la estructura
    has_simple_content = (complex_type is not None and 
                         complex_type.find("{http://www.w3.org/2001/XMLSchema}simpleContent") is not None)
    
    # Detectar si tiene simpleType directamente
    has_simple_type = element.find("{http://www.w3.org/2001/XMLSchema}simpleType") is not None

    return {
        "name": name,
        "type": type_ or base_type,
        "minOccurs": min_occurs,
        "maxOccurs": max_occurs,
        "attributes": attributes,
        "children": children,
        "isSimpleContent": has_simple_content or has_simple_type,
        "hasComplexType": complex_type is not None,
        "baseType": base_type
    }


def parse_xsd_from_url(url: str) -> Dict[str, List[dict]]:
    response = requests.get(url)
    response.raise_for_status()

    tree = ET.parse(io.BytesIO(response.content))
    root = tree.getroot()
    namespace = "{http://www.w3.org/2001/XMLSchema}"

    sections = {}

    for el in root.findall(f"{namespace}element"):
        section_name = el.attrib.get("name")
        if not section_name:
            continue

        section_structure = []
        complex_type = el.find(f"{namespace}complexType")
        if complex_type is not None:
            sequence = complex_type.find(f"{namespace}sequence")
            if sequence is not None:
                for child in sequence.findall(f"{namespace}element"):
                    section_structure.append(parse_element(child, root))

        sections[section_name] = section_structure

    return sections

def parse_xsd_from_file(file_path: str) -> Dict[str, List[dict]]:
    dir_base = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(dir_base, file_path)
    tree = ET.parse(file_path)
    root = tree.getroot()
    namespace = "{http://www.w3.org/2001/XMLSchema}"

    sections = {}

    for el in root.findall(f"{namespace}element"):
        section_name = el.attrib.get("name")
        if not section_name:
            continue

        section_structure = []
        complex_type = el.find(f"{namespace}complexType")
        if complex_type is not None:
            sequence = complex_type.find(f"{namespace}sequence")
            if sequence is not None:
                for child in sequence.findall(f"{namespace}element"):
                    section_structure.append(parse_element(child, root))

        sections[section_name] = section_structure

    return sections
