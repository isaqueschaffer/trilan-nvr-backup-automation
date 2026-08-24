import requests
import xml.etree.ElementTree as ET
from requests.auth import HTTPDigestAuth
from datetime import datetime, timedelta
import re
import uuid
import logging
import base64

TIMEOUT = 20
DIAS_VERIFICAR = 15
NS_URI = "http://www.hikvision.com/ver20/XMLSchema"
NS = {"hik": NS_URI}

def fazer_get(url, usuario, senha):
    return requests.get(
        url,
        auth=HTTPDigestAuth(usuario, senha),
        timeout=TIMEOUT,
        verify=False
    )

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

def buscar_cameras_nvr(nvr_ip, usuario, senha):
    url_config = f"http://{nvr_ip}/ISAPI/ContentMgmt/InputProxy/channels"
    url_status = f"http://{nvr_ip}/ISAPI/ContentMgmt/InputProxy/channels/status"
    try:
        resp_config = fazer_get(url_config, usuario, senha)
        if resp_config.status_code != 200:
            return None

        root = parse_xml_seguro(resp_config.content)
        ns = detectar_namespace(root)
        cameras = {}
        elementos = root.findall("hik:InputProxyChannel", {"hik": ns}) if ns else root.findall("InputProxyChannel")

        if not elementos:
            return None

        for canal in elementos:
            if ns:
                canal_id = texto(canal, "hik:id", ns)
                nome = texto(canal, "hik:name", ns)
                source = canal.find("hik:sourceInputPortDescriptor", {"hik": ns})
            else:
                canal_id = texto(canal, "id", None)
                nome = texto(canal, "name", None)
                source = canal.find("sourceInputPortDescriptor")

            ip = ""
            if source is not None:
                ip = texto(source, "hik:ipAddress", ns) if ns else texto(source, "ipAddress", None)

            cameras[canal_id] = {"nome": nome, "ip": ip, "online": None}

        if not cameras:
            return None

        try:
            resp_status = fazer_get(url_status, usuario, senha)
            if resp_status.status_code == 200:
                root_status = parse_xml_seguro(resp_status.content)
                ns_status = detectar_namespace(root_status)
                status_els = root_status.findall("hik:InputProxyChannelStatus", {"hik": ns_status}) if ns_status else root_status.findall("InputProxyChannelStatus")

                for st in status_els:
                    cid = texto(st, "hik:id", ns_status) if ns_status else texto(st, "id", None)
                    online = texto(st, "hik:online", ns_status) if ns_status else texto(st, "online", None)
                    if cid in cameras:
                        cameras[cid]["online"] = online.lower() == "true"
        except Exception:
            pass

        return cameras
    except Exception:
        return None

def buscar_cameras_dvr(nvr_ip, usuario, senha):
    url = f"http://{nvr_ip}/ISAPI/System/Video/inputs/channels"
    try:
        resp = fazer_get(url, usuario, senha)
        if resp.status_code != 200:
            return None

        root = parse_xml_seguro(resp.content)
        ns = detectar_namespace(root)
        cameras = {}
        elementos = root.findall("hik:VideoInputChannel", {"hik": ns}) if ns else root.findall("VideoInputChannel")

        if not elementos:
            return None

        for canal in elementos:
            if ns:
                canal_id = texto(canal, "hik:id", ns)
                nome = texto(canal, "hik:name", ns)
                res_desc = texto(canal, "hik:resDesc", ns)
            else:
                canal_id = texto(canal, "id", None)
                nome = texto(canal, "name", None)
                res_desc = texto(canal, "resDesc", None)

            online = res_desc.upper() != "NO VIDEO" if res_desc else True
            cameras[canal_id] = {"nome": nome, "ip": nvr_ip, "online": online}

        return cameras
    except Exception:
        return None

def buscar_cameras(nvr_ip, usuario, senha):
    cameras = buscar_cameras_nvr(nvr_ip, usuario, senha)
    if cameras: return cameras, "NVR", None
    cameras = buscar_cameras_dvr(nvr_ip, usuario, senha)
    if cameras: return cameras, "DVR", None
    
    cameras, sessao = buscar_cameras_motorola(nvr_ip, usuario, senha)
    if cameras: return cameras, "MOTOROLA", sessao
    
    return {}, "DESCONHECIDO", None

def buscar_cameras_motorola(nvr_ip, usuario, senha):
    session = requests.Session()
    pwd_b64 = base64.b64encode(senha.encode('utf-8')).decode('utf-8')
    xml_header = '<?xml version="1.0" encoding="utf-8" ?>'
    
    try:
        # Tenta o fluxo novo de login (reqLogin -> doLogin com hash SHA-512)
        xml_req = f'{xml_header}<request version="1.0" systemType="NVMS-9000" clientType="WEB"/>'
        r_req = session.post(f"http://{nvr_ip}/reqLogin", data=xml_req.encode('utf-8'), headers={"Content-Type": "application/xml"}, timeout=10, verify=False)
        
        login_efetuado = False
        r = None
        
        if r_req.status_code == 200 and "success" in r_req.text:
            root_req = parse_xml_seguro(r_req.content)
            nonce = texto(root_req, ".//nonce", None)
            token = texto(root_req, ".//token", None)
            
            if nonce and token:
                import hashlib
                pwd_md5 = hashlib.md5(senha.encode('utf-8')).hexdigest().upper()
                hash_final = hashlib.sha512((pwd_md5 + "#" + nonce).encode('utf-8')).hexdigest()
                
                xml_login = f'{xml_header}<request version="1.0" systemType="NVMS-9000" clientType="WEB"><token>{token}</token><content><userName><![CDATA[{usuario}]]></userName><password><![CDATA[{hash_final}]]></password></content></request>'
                
                r = session.post(f"http://{nvr_ip}/doLogin", data=xml_login.encode('utf-8'), headers={"Content-Type": "application/xml"}, timeout=10, verify=False)
                if r.status_code == 200 and "success" in r.text:
                    login_efetuado = True
                    
        # Se falhou ou não suporta reqLogin, tenta o login antigo (Base64)
        if not login_efetuado:
            xml_login = f'{xml_header}<request version="1.0" systemType="NVMS-9000" clientType="WEB"><content><userName><![CDATA[{usuario}]]></userName><password><![CDATA[{pwd_b64}]]></password></content></request>'
            r = session.post(f"http://{nvr_ip}/doLogin", data=xml_login.encode('utf-8'), headers={"Content-Type": "application/xml"}, timeout=10, verify=False)
            if r.status_code == 200 and "success" in r.text:
                login_efetuado = True
                
        if login_efetuado and r is not None:
            root = parse_xml_seguro(r.content)
            session_id = texto(root, ".//sessionId", None)
            if not session_id:
                return None, None
            session.cookies.set('auInfo_N9K', pwd_b64)
            session.cookies.set('sessionId', session_id.strip('{}'))
            
            # Save token for later requests
            token_val = token if 'token' in locals() and token else ""
            session.tvt_token = token_val
            token_xml = f"<token>{token_val}</token>" if token_val else ""
            
            # Buscando canais
            xml_chls = f'{xml_header}<request version="1.0" systemType="NVMS-9000" clientType="WEB">{token_xml}</request>'
            r2 = session.post(f"http://{nvr_ip}/queryChlsExistRec", data=xml_chls.encode('utf-8'), headers={"Content-Type": "application/xml"}, timeout=10, verify=False)
            if r2.status_code == 200:
                root2 = parse_xml_seguro(r2.content)
                cameras = {}
                for item in root2.findall(".//item"):
                    cid = item.get("id", "")
                    nome = item.text or ""
                    cameras[cid] = {"nome": nome, "ip": nvr_ip, "online": True}
                return cameras, session
    except Exception as e:
        logging.error(f"Erro no login motorola {nvr_ip}: {e}")
        pass
    return None, None

def buscar_datas_gravacao_motorola(nvr_ip, session, canal_id):
    xml_header = '<?xml version="1.0" encoding="utf-8" ?>'
    token_val = getattr(session, 'tvt_token', '')
    token_xml = f"<token>{token_val}</token>" if token_val else ""
    
    xml_req = f'{xml_header}<request version="1.0" systemType="NVMS-9000" clientType="WEB">{token_xml}<condition><chlId>{canal_id}</chlId></condition></request>'
    try:
        r = session.post(f"http://{nvr_ip}/queryDatesExistRec", data=xml_req.encode('utf-8'), headers={"Content-Type": "application/xml"}, timeout=10, verify=False)
        if r.status_code == 200:
            root = parse_xml_seguro(r.content)
            datas = []
            for item in root.findall(".//item"):
                if item.text:
                    try:
                        dt = datetime.strptime(item.text.strip(), "%Y-%m-%d")
                        datas.append(dt)
                    except ValueError:
                        pass
            return datas
    except Exception as e:
        logging.error(f"Erro ao buscar datas motorola em {nvr_ip} canal {canal_id}: {e}")
        pass
    return []

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

def gerar_mapa_dias(dias_com_gravacao):
    hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    datas_set = set(d.strftime("%Y-%m-%d") for d in dias_com_gravacao)
    mapa = ""
    for i in range(DIAS_VERIFICAR - 1, -1, -1):
        data = hoje - timedelta(days=i)
        if data.strftime("%Y-%m-%d") in datas_set:
            mapa += "█"
        else:
            mapa += "░"
    return mapa

from concurrent.futures import ThreadPoolExecutor, as_completed

def verificar_gravacao_nvr(nvr_ip, usuario, senha):
    logging.info(f"  Verificando gravação para {nvr_ip}...")
    try:
        cameras, tipo, sessao = buscar_cameras(nvr_ip, usuario, senha)
        if not cameras:
            logging.info(f"  Nenhuma câmera encontrada para verificação de gravação.")
            return [], tipo

        hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        resultados = []
        
        if tipo == "MOTOROLA":
            # Motorola: Processamento mais rápido via endpoint agrupado por datas
            for canal_id, camera in cameras.items():
                datas_gravadas = buscar_datas_gravacao_motorola(nvr_ip, sessao, canal_id)
                # Filtra apenas os dias que estão no range de verificação
                dias_com_gravacao = []
                for dt in datas_gravadas:
                    if (hoje - timedelta(days=DIAS_VERIFICAR)) <= dt <= hoje:
                        dias_com_gravacao.append(dt)
                        
                resultados.append({
                    "canal": canal_id,
                    "nome": camera["nome"],
                    "ip": camera["ip"],
                    "online": camera["online"],
                    "total_dias": len(dias_com_gravacao),
                    "mapa": gerar_mapa_dias(dias_com_gravacao)
                })
            return resultados, tipo

        with ThreadPoolExecutor(max_workers=10) as executor:
            for canal_id, camera in cameras.items():
                nome = camera["nome"]
                ip = camera["ip"]
                online = camera["online"]

                # Removemos o bloqueio de câmeras offline para permitir a checagem
                # do histórico de gravação dos 15 dias (pois as gravações ficam no NVR).

                # Submit checks for all 15 days for this camera
                future_to_day = {
                    executor.submit(tem_gravacao_no_dia, nvr_ip, usuario, senha, canal_id, hoje - timedelta(days=i)): (hoje - timedelta(days=i))
                    for i in range(DIAS_VERIFICAR)
                }

                dias_com_gravacao = []
                for future in as_completed(future_to_day):
                    data_ref = future_to_day[future]
                    try:
                        res = future.result()
                        if res is True:
                            dias_com_gravacao.append(data_ref)
                    except Exception:
                        pass

                if online is None:
                    online = len(dias_com_gravacao) > 0

                resultados.append({
                    "canal": canal_id,
                    "nome": nome,
                    "ip": ip,
                    "online": online,
                    "total_dias": len(dias_com_gravacao),
                    "mapa": gerar_mapa_dias(dias_com_gravacao)
                })

        return resultados, tipo
    except Exception as e:
        logging.error(f"  Erro ao verificar gravação: {e}")
        return [], "DESCONHECIDO"

