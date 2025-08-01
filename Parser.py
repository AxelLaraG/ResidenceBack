import xml.etree.ElementTree as ET
from typing import Dict, List
import requests
import io
import os

def strip_prefix(tag):
    """Elimina prefijos de namespace como 'xs:' de un string."""
    return tag.split(':')[-1] if tag else None

def parse_xsd_structure(root: ET.Element) -> Dict[str, List[dict]]:
    """
    Parsea la estructura de un XSD, resolviendo los tipos con nombre para construir un árbol jerárquico.
    """
    namespace = "{http://www.w3.org/2001/XMLSchema}"
    
    schema_types = {}
    for type_def in root.findall(f".//{namespace}complexType[@name]"):
        schema_types[type_def.attrib["name"]] = type_def
    for type_def in root.findall(f".//{namespace}simpleType[@name]"):
        schema_types[type_def.attrib["name"]] = type_def
            
    memo = {}

    def parse_element_recursive(element_node: ET.Element, context_path="") -> dict:
        element_name = element_node.attrib.get("name")
        element_type_name = strip_prefix(element_node.attrib.get("type"))
        
        current_path = f"{context_path}/{element_name}" if context_path else element_name
        memo_key = f"{element_node.tag}-{current_path}-{element_type_name}"
        
        if memo_key in memo and len(context_path.split('/')) > 5:
            return memo[memo_key]

        children = []
        attributes = []
        base_type = None
        
        type_definition_node = element_node.find(f"{namespace}complexType")
        
        if element_node.tag == f"{namespace}complexType":
            type_definition_node = element_node
        elif type_definition_node is None and element_type_name in schema_types:
            type_definition_node = schema_types[element_type_name]

        if type_definition_node is not None and type_definition_node.tag != f"{namespace}simpleType":
            
            for attr in type_definition_node.findall(f"./{namespace}attribute"):
                attributes.append({
                    "name": attr.attrib.get("name"), 
                    "type": attr.attrib.get("type"),
                    "use": attr.attrib.get("use", "optional")
                })
            
            for content_type in ["simpleContent", "complexContent"]:
                content_node = type_definition_node.find(f"./{namespace}{content_type}")
                if content_node:
                    extension = content_node.find(f"./{namespace}extension")
                    if extension is not None:
                        base_type = extension.attrib.get("base")
                        base_type_name = strip_prefix(base_type)
                        
                        if base_type_name in schema_types:
                            base_type_node = schema_types[base_type_name]
                            parsed_base = parse_element_recursive(base_type_node, current_path)
                            children.extend(parsed_base.get("children", []))
                            attributes.extend(parsed_base.get("attributes", []))
                        
                        for attr in extension.findall(f"./{namespace}attribute"):
                            attributes.append({
                                "name": attr.attrib.get("name"), 
                                "type": attr.attrib.get("type"),
                                "use": attr.attrib.get("use", "optional")
                            })
                        
                        ext_sequence = extension.find(f"./{namespace}sequence")
                        ext_choice = extension.find(f"./{namespace}choice")
                        ext_container = ext_sequence if ext_sequence is not None else ext_choice
                        if ext_container is not None:
                            for child_element in ext_container.findall(f"./{namespace}element"):
                                children.append(parse_element_recursive(child_element, current_path))
                            if ext_sequence is not None:
                                for choice_in_seq in ext_sequence.findall(f"./{namespace}choice"):
                                    for child_in_choice in choice_in_seq.findall(f"./{namespace}element"):
                                        children.append(parse_element_recursive(child_in_choice, current_path))
            
            sequence = type_definition_node.find(f"./{namespace}sequence")
            choice = type_definition_node.find(f"./{namespace}choice")
            
            container = sequence if sequence is not None else choice
            if container is not None:
                for child_element in container.findall(f"./{namespace}element"):
                    children.append(parse_element_recursive(child_element, current_path))
                    
                if sequence is not None:
                    for choice_in_seq in sequence.findall(f"./{namespace}choice"):
                        for child_in_choice in choice_in_seq.findall(f"./{namespace}element"):
                            children.append(parse_element_recursive(child_in_choice, current_path))
                            
                if choice is not None:
                    for seq_in_choice in choice.findall(f"./{namespace}sequence"):
                        for child_in_seq in seq_in_choice.findall(f"./{namespace}element"):
                            children.append(parse_element_recursive(child_in_seq, current_path))

        parsed_data = {
            "name": element_name,
            "type": element_node.attrib.get("type") or base_type,
            "minOccurs": element_node.attrib.get("minOccurs", "1"),
            "maxOccurs": element_node.attrib.get("maxOccurs", "1"),
            "attributes": attributes,
            "children": children,
            "isSimpleContent": type_definition_node is not None and type_definition_node.find(f".//{namespace}simpleContent") is not None,
            "hasComplexType": type_definition_node is not None and type_definition_node.tag != f"{namespace}simpleType",
            "baseType": base_type
        }
        
        if len(current_path.split('/')) <= 5:
            memo[memo_key] = parsed_data
            
        return parsed_data

    sections = {}
    for top_level_element in root.findall(f"{namespace}element"):
        section_name = top_level_element.attrib.get("name")
        if section_name:
            sections[section_name] = parse_element_recursive(top_level_element).get("children", [])
            
    return sections


def parse_xsd_from_url(url: str) -> Dict[str, List[dict]]:
    """Obtiene un XSD desde una URL y lo parsea."""
    response = requests.get(url)
    response.raise_for_status()
    tree = ET.parse(io.BytesIO(response.content))
    root = tree.getroot()
    return parse_xsd_structure(root)


def parse_xsd_from_file(file_path: str) -> Dict[str, List[dict]]:
    """Parsea un archivo XSD local."""
    dir_base = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(dir_base, file_path)
    tree = ET.parse(full_path)
    root = tree.getroot()
    return parse_xsd_structure(root)