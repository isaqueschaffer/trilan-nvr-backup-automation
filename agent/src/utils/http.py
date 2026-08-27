import requests
from requests.auth import HTTPDigestAuth
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TIMEOUT = 20

def fazer_get(url, usuario, senha, timeout=TIMEOUT):
    return requests.get(
        url,
        auth=HTTPDigestAuth(usuario, senha),
        timeout=timeout,
        verify=False
    )
