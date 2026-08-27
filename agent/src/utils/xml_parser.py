import xml.etree.ElementTree as ET
import re

def detectar_namespace(root):
    match = re.match(r"\{(.*?)\}", root.tag)
    return match.group(1) if match else None

def texto(elemento, caminho, namespace):
    if elemento is None:
        return ""
    el = elemento.find(caminho, {"hik": namespace}) if namespace else elemento.find(caminho)
    if el is not None and el.text:
        return el.text.strip()
    return ""

def limpar_xml(content_bytes):
    texto_str = content_bytes.decode('utf-8', errors='replace')
    resultado = []
    for ch in texto_str:
        cp = ord(ch)
        if (cp == 0x9 or cp == 0xA or cp == 0xD or
            (0x20 <= cp <= 0xD7FF) or
            (0xE000 <= cp <= 0xFFFD) or
            (0x10000 <= cp <= 0x10FFFF)):
            resultado.append(ch)
    return ''.join(resultado)

def parse_xml_seguro(content_bytes):
    try:
        return ET.fromstring(content_bytes)
    except ET.ParseError:
        conteudo_limpo = limpar_xml(content_bytes)
        return ET.fromstring(conteudo_limpo)
