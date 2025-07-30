import json
import xml.etree.ElementTree as ET

def find_element_definition(xsd_structure, unique_id):
    """
    Busca la definición de un elemento en la estructura XSD usando su uniqueId.
    Retorna el elemento con sus propiedades (incluyendo maxOccurs) o None si no se encuentra.
    """
    if not xsd_structure or not unique_id:
        return None
    
    def search_in_structure(structure, target_unique_id, current_path=[]):
        if isinstance(structure, dict):
            for section_name, section_data in structure.items():
                current_section_path = current_path + [section_name]
                
                if isinstance(section_data, list):
                    for item in section_data:
                        result = search_in_structure(item, target_unique_id, current_section_path)
                        if result:
                            return result
                elif isinstance(section_data, dict):
                    result = search_in_structure(section_data, target_unique_id, current_section_path)
                    if result:
                        return result
        
        elif isinstance(structure, list):
            for item in structure:
                result = search_in_structure(item, target_unique_id, current_path)
                if result:
                    return result
    
    def search_element_recursive(elements, target_unique_id, path=[]):
        """Busca recursivamente en los elementos"""
        if not isinstance(elements, list):
            return None
            
        for element in elements:
            if not isinstance(element, dict):
                continue
                
            element_name = element.get('name', '')
            current_path = path + [element_name]
            current_unique_id = '_'.join(current_path)
            
            # Si encontramos el elemento que buscamos
            if current_unique_id == target_unique_id:
                return element
            
            # Buscar en los hijos si existen
            children = element.get('children', [])
            if children:
                result = search_element_recursive(children, target_unique_id, current_path)
                if result:
                    return result
                    
        return None
    
    # Buscar en toda la estructura XSD
    for section_name, section_elements in xsd_structure.items():
        if isinstance(section_elements, list):
            result = search_element_recursive(section_elements, unique_id, [section_name])
            if result:
                return result
    
    return None

def is_element_additive(element_def):
    """
    Verifica si un elemento permite múltiples ocurrencias o es parte de un contenedor aditivo
    """
    if not element_def:
        return False
    
    # Verificar maxOccurs directo
    max_occurs = element_def.get('maxOccurs', '1')
    if max_occurs == 'unbounded' or (max_occurs != '1' and max_occurs != '0'):
        return True
    
    # Verificar si tiene atributos que indiquen que es aditivo
    if element_def.get('type') == 'array' or element_def.get('multiple', False):
        return True
    
    # Verificar patrones comunes de elementos aditivos por nombre
    element_name = element_def.get('name', '').lower()
    additive_patterns = [
        'item', 'entry', 'record', 'element', 'publicacion', 
        'experiencia', 'titulo', 'actividad', 'proyecto'
    ]
    
    if any(pattern in element_name for pattern in additive_patterns):
        return True
    
    return False

def find_element_definition(xsd_structure, unique_id):
    """
    Busca la definición de un elemento en la estructura XSD usando su uniqueId.
    Versión mejorada que maneja mejor los elementos anidados.
    """
    if not xsd_structure or not unique_id:
        return None
    
    def search_element_recursive(elements, target_unique_id, path=[]):
        """Busca recursivamente en los elementos con mejor manejo de rutas"""
        if not isinstance(elements, list):
            return None
            
        for element in elements:
            if not isinstance(element, dict):
                continue
                
            element_name = element.get('name', '')
            current_path = path + [element_name]
            current_unique_id = '_'.join(current_path)
            
            # Si encontramos el elemento que buscamos
            if current_unique_id == target_unique_id:
                return element
            
            # También verificar coincidencias parciales para elementos anidados
            if target_unique_id.endswith('_' + element_name):
                partial_match = element.copy()
                partial_match['_matched_path'] = current_path
                return partial_match
            
            # Buscar en los hijos si existen
            children = element.get('children', [])
            if children:
                result = search_element_recursive(children, target_unique_id, current_path)
                if result:
                    return result
                    
        return None
    
    # Buscar en toda la estructura XSD
    for section_name, section_elements in xsd_structure.items():
        if isinstance(section_elements, list):
            result = search_element_recursive(section_elements, unique_id, [section_name])
            if result:
                return result
    
    return None

def find_or_create_element_path(root, path_parts, namespaces=None):
    """
    Encuentra o crea una ruta de elementos en un XML.
    Retorna el elemento padre donde se debe insertar/actualizar el elemento final.
    """
    current = root
    
    for i, part in enumerate(path_parts[:-1]):  # Excluimos el último elemento
        # Buscar si el elemento ya existe
        existing = current.find(part)
        if existing is not None:
            current = existing
        else:
            # Crear el elemento si no existe
            new_element = ET.SubElement(current, part)
            current = new_element
    
    return current

def handle_complex_element_update(parent_element, element_name, new_value, is_additive=False):
    """
    Maneja la actualización de elementos complejos.
    """
    if is_additive:
        # Para elementos aditivos, siempre crear uno nuevo
        new_element = ET.SubElement(parent_element, element_name)
        
        # Si el valor es un diccionario, crear subelementos
        if isinstance(new_value, dict):
            for key, value in new_value.items():
                sub_element = ET.SubElement(new_element, key)
                sub_element.text = str(value) if value is not None else ""
        else:
            new_element.text = str(new_value) if new_value is not None else ""
        
        return new_element
    else:
        # Para elementos no aditivos, buscar existente o crear nuevo
        existing = parent_element.find(element_name)
        
        if existing is not None:
            # Actualizar elemento existente
            if isinstance(new_value, dict):
                # Limpiar subelementos existentes
                existing.clear()
                for key, value in new_value.items():
                    sub_element = ET.SubElement(existing, key)
                    sub_element.text = str(value) if value is not None else ""
            else:
                existing.text = str(new_value) if new_value is not None else ""
        else:
            # Crear nuevo elemento
            new_element = ET.SubElement(parent_element, element_name)
            if isinstance(new_value, dict):
                for key, value in new_value.items():
                    sub_element = ET.SubElement(new_element, key)
                    sub_element.text = str(value) if value is not None else ""
            else:
                new_element.text = str(new_value) if new_value is not None else ""
        
        return existing if existing is not None else new_element

def parse_complex_value(value_str):
    """
    Intenta parsear un valor que podría ser un JSON u objeto complejo.
    """
    if not value_str:
        return value_str
    
    # Si parece ser JSON, intentar parsearlo
    if isinstance(value_str, str) and (value_str.strip().startswith('{') or value_str.strip().startswith('[')):
        try:
            return json.loads(value_str)
        except json.JSONDecodeError:
            return value_str
    
    return value_str