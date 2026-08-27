import logging
import hashlib
from pathlib import Path

TIMEOUT_NVR = 60

def baixar_arquivo(sessao, url, destino: Path, min_bytes=0, valida_xml=False) -> bool:
    try:
        with sessao.get(url, stream=True, timeout=TIMEOUT_NVR) as r:
            if r.status_code not in (200, 401):
                logging.error(f"HTTP {r.status_code}: {url}")
                return False
            with open(destino, "wb") as f:
                for chunk in r.iter_content(1024 * 1024):
                    if chunk:
                        f.write(chunk)
        dados = destino.read_bytes()
        if len(dados) < min_bytes:
            raise ValueError("Arquivo muito pequeno (falha de autenticacao).")
        if valida_xml and b"<ResponseStatus" in dados[:500]:
            raise ValueError("Resposta de erro XML recebida.")
        sha256 = hashlib.sha256(dados).hexdigest()
        logging.info(f"  Salvo: {destino.name} ({len(dados)/1024:.1f} KB) SHA-256: {sha256[:16]}...")
        return True
    except Exception as e:
        logging.error(f"  Erro download {destino.name}: {e}")
        destino.unlink(missing_ok=True)
        return False
