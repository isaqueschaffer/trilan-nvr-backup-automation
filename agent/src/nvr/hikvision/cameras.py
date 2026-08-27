from src.utils.xml_parser import parse_xml_seguro, detectar_namespace, texto
from src.utils.http import fazer_get

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
