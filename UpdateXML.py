import xml.etree.ElementTree as ET

def _parse_indexed_id(unique_id):
    """
    Parsea un ID del frontend para separar el ID base de sus índices.
    Ejemplo: 'cvu_TrayectoriaAcademica_Trayectoria_0_Titulo'
    Retorna:
        - normalized_id: 'cvu_TrayectoriaAcademica_Trayectoria_Titulo'
        - indices: {'cvu_TrayectoriaAcademica_Trayectoria': 0}
    """
    parts = unique_id.split('_')
    normalized_parts = []
    indices = {}
    
    i = 0
    current_path_base = []
    while i < len(parts):
        current_part = parts[i]
        
        if i + 1 < len(parts) and parts[i+1].isdigit():
            current_path_base.append(current_part)
            normalized_parts.append(current_part)
            path_key = '_'.join(current_path_base)
            indices[path_key] = int(parts[i+1])
            i += 2  
        else:
            current_path_base.append(current_part)
            normalized_parts.append(current_part)
            i += 1
            
    normalized_id = '_'.join(normalized_parts)
    return normalized_id, indices

def _find_or_create_parent_element(root, target_path_parts, source_indices, mappings, institution):
    """
    Navega o crea la ruta hasta el elemento padre correcto en el XML de destino.
    Devuelve el elemento padre final.
    """
    current_element = root
    
    index_to_apply = next(iter(source_indices.values())) if source_indices else None

    for i in range(1, len(target_path_parts) - 1):
        part_name = target_path_parts[i]
        
        if index_to_apply is not None:
            existing_children = current_element.findall(part_name)
            if index_to_apply < len(existing_children):
                current_element = existing_children[index_to_apply]
            else:
                new_child = None
                for _ in range(len(existing_children), index_to_apply + 1):
                    new_child = ET.SubElement(current_element, part_name)
                current_element = new_child
            
            index_to_apply = None 
        else:
            found_child = current_element.find(part_name)
            if found_child is None:
                found_child = ET.SubElement(current_element, part_name)
            current_element = found_child
            
    return current_element

def _update_child_element(parent, element_name, new_value):
    """
    Dentro de un elemento padre ya localizado, busca un hijo por su nombre.
    - Si lo encuentra, actualiza su valor.
    - Si no lo encuentra, lo crea.
    """
    if element_name.startswith('@'):
        attr_name = element_name[1:]
        parent.set(attr_name, str(new_value))
        return

    existing_element = parent.find(element_name)
    
    if existing_element is not None:
        existing_element.text = str(new_value) if new_value is not None else ""
    else:
        new_element = ET.SubElement(parent, element_name)
        new_element.text = str(new_value) if new_value is not None else ""

def apply_updates_to_xml(xml_path, updates, mappings, institution):
    """
    Función principal que orquesta todo el proceso de actualización del XML.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except (FileNotFoundError, ET.ParseError):
        root_name = list(mappings.get(institution, {}).values())[0].split('_')[0] if mappings.get(institution) else "cvu"
        root = ET.Element(root_name, {"xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"})
        tree = ET.ElementTree(root)

    for source_id, new_value in updates.items():
        normalized_id, source_indices_by_path = _parse_indexed_id(source_id)

        # 2. Encontrar el mapeo en Mapeo.json
        target_id = mappings.get(institution, {}).get(normalized_id)
        if not target_id:
            print(f"Advertencia: No se encontró mapeo para '{normalized_id}' en la institución '{institution}'")
            continue

        target_path_parts = target_id.split('_')
        parent_element = _find_or_create_parent_element(root, target_path_parts, source_indices_by_path, mappings, institution)
        
        element_name_to_update = target_path_parts[-1]

        _update_child_element(parent_element, element_name_to_update, new_value)

    tree.write(xml_path, encoding='utf-8', xml_declaration=True)