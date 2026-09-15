import uuid
import requests
from requests.auth import HTTPDigestAuth
from datetime import timedelta
import xml.etree.ElementTree as ET
from src.utils.xml_parser import detectar_namespace
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
TIMEOUT = 20

def tem_gravacao_no_dia(nvr_ip, usuario, senha, canal_id, data):
    try:
        canal_numero = int(canal_id)
    except ValueError:
        return None

    track_id = (canal_numero * 100) + 1
    inicio_dia = data.replace(hour=0, minute=0, second=0, microsecond=0)
    fim_dia = inicio_dia + timedelta(days=1) - timedelta(seconds=1)
    search_id = "{" + str(uuid.uuid4()) + "}"
    url_search = f"http://{nvr_ip}/ISAPI/ContentMgmt/search"

    xml_busca = f"""<?xml version="1.0" encoding="UTF-8"?>
<CMSearchDescription>
    <searchID>{search_id}</searchID>
    <trackIDList><trackID>{track_id}</trackID></trackIDList>
    <timeSpanList>
        <timeSpan>
            <startTime>{inicio_dia.strftime("%Y-%m-%dT%H:%M:%SZ")}</startTime>
            <endTime>{fim_dia.strftime("%Y-%m-%dT%H:%M:%SZ")}</endTime>
        </timeSpan>
    </timeSpanList>
    <maxResults>1</maxResults>
    <searchResultPostion>0</searchResultPostion>
    <metadataList><metadataDescriptor>//recordType.meta.std-cgi.com</metadataDescriptor></metadataList>
</CMSearchDescription>"""

    try:
        response = requests.post(
            url_search,
            data=xml_busca.encode("utf-8"),
            auth=HTTPDigestAuth(usuario, senha),
            headers={"Content-Type": "application/xml", "Accept": "application/xml"},
            timeout=TIMEOUT,
            verify=False
        )
    except requests.exceptions.RequestException:
        return None

    if response.status_code != 200:
        return None

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError:
        return None

    ns = detectar_namespace(root)
    ns_map = {"hik": ns} if ns else {}

    path_num = ".//hik:numOfMatches" if ns else ".//numOfMatches"
    num_matches_el = root.find(path_num, ns_map) if ns_map else root.find(path_num)
    
    if num_matches_el is not None and num_matches_el.text:
        try:
            return int(num_matches_el.text.strip()) > 0
        except ValueError:
            pass

    path_item = ".//hik:searchMatchItem" if ns else ".//searchMatchItem"
    itens = root.findall(path_item, ns_map) if ns_map else root.findall(path_item)
    return len(itens) > 0
