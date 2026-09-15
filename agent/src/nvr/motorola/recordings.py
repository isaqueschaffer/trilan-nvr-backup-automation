import time
import requests
import logging
from datetime import datetime
from src.utils.xml_parser import parse_xml_seguro
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def buscar_datas_gravacao_motorola(nvr_ip, session, canal_id):
    """
    Consulta as datas que possuem gravações em um canal de um NVR Motorola.

    Retorna:
        (datas, True)  -> consulta realizada com sucesso
        ([], False)    -> falha na consulta
    """
    xml_header = '<?xml version="1.0" encoding="utf-8" ?>'
    token_val = getattr(session, 'tvt_token', '')
    token_xml = f"<token>{token_val}</token>" if token_val else ""

    xml_req = (
        f'{xml_header}'
        f'<request version="1.0" '
        f'systemType="NVMS-9000" '
        f'clientType="WEB">'
        f'{token_xml}'
        f'<condition>'
        f'<chlId>{canal_id}</chlId>'
        f'</condition>'
        f'</request>'
    )

    url = f"http://{nvr_ip}/queryDatesExistRec"
    max_tentativas = 3
    timeout = (10, 60)

    for tentativa in range(1, max_tentativas + 1):
        inicio = time.monotonic()
        try:
            logging.info(f"[Motorola {nvr_ip}] Buscando datas de gravação - canal={canal_id} tentativa={tentativa}/{max_tentativas}")
            
            response = session.post(
                url,
                data=xml_req.encode("utf-8"),
                headers={"Content-Type": "application/xml", "Accept": "application/xml, text/xml, */*"},
                timeout=timeout,
                verify=False
            )
            
            tempo_resposta = time.monotonic() - inicio
            logging.info(f"[Motorola {nvr_ip}] Resposta recebida em {tempo_resposta:.2f}s HTTP={response.status_code} canal={canal_id}")

            if response.status_code != 200:
                logging.warning(f"[Motorola {nvr_ip}] queryDatesExistRec retornou HTTP {response.status_code} canal={canal_id}")
                if tentativa < max_tentativas:
                    time.sleep(2 * tentativa)
                    continue
                return [], False

            if not response.content:
                logging.warning(f"[Motorola {nvr_ip}] Resposta vazia em queryDatesExistRec canal={canal_id}")
                if tentativa < max_tentativas:
                    time.sleep(2 * tentativa)
                    continue
                return [], False

            response_text = response.text.strip()
            if "success" not in response_text.lower():
                logging.warning(f"[Motorola {nvr_ip}] NVR não retornou sucesso em queryDatesExistRec canal={canal_id} resposta={response_text[:300]}")
                return [], False

            try:
                root = parse_xml_seguro(response.content)
            except Exception as xml_error:
                logging.error(f"[Motorola {nvr_ip}] Erro ao interpretar XML canal={canal_id}: {xml_error}")
                return [], False

            datas = []
            for item in root.findall(".//item"):
                if not item.text:
                    continue
                valor = item.text.strip()
                try:
                    dt = datetime.strptime(valor, "%Y-%m-%d")
                    datas.append(dt)
                except ValueError:
                    logging.warning(f"[Motorola {nvr_ip}] Data inválida recebida: '{valor}' canal={canal_id}")

            datas = sorted(set(datas))
            logging.info(f"[Motorola {nvr_ip}] Consulta concluída com sucesso - canal={canal_id} datas_encontradas={len(datas)} tempo={tempo_resposta:.2f}s")
            return datas, True

        except requests.exceptions.ConnectTimeout:
            tempo = time.monotonic() - inicio
            logging.warning(f"[Motorola {nvr_ip}] Timeout de conexão após {tempo:.2f}s canal={canal_id} tentativa={tentativa}/{max_tentativas}")
        except requests.exceptions.ReadTimeout:
            tempo = time.monotonic() - inicio
            logging.warning(f"[Motorola {nvr_ip}] Timeout aguardando resposta do NVR após {tempo:.2f}s canal={canal_id} tentativa={tentativa}/{max_tentativas}")
        except requests.exceptions.ConnectionError as e:
            logging.warning(f"[Motorola {nvr_ip}] Erro de conexão canal={canal_id}: {e}")
        except requests.exceptions.RequestException as e:
            logging.error(f"[Motorola {nvr_ip}] Erro HTTP em queryDatesExistRec canal={canal_id}: {e}")
            return [], False
        except Exception as e:
            logging.exception(f"[Motorola {nvr_ip}] Erro inesperado ao buscar datas canal={canal_id}: {e}")
            return [], False

        if tentativa < max_tentativas:
            espera = 2 ** tentativa
            logging.info(f"[Motorola {nvr_ip}] Aguardando {espera}s antes de tentar novamente...")
            time.sleep(espera)

    logging.error(f"[Motorola {nvr_ip}] Falha definitiva ao buscar datas de gravação canal={canal_id} após {max_tentativas} tentativas")
    return [], False
