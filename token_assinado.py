"""
Token de ativação assinado -- é o que o servidor de licenças devolve
depois de uma ativação/verificação bem-sucedida, e que o WebNest
guarda localmente (data/licenca.json) pra não precisar contatar o
servidor toda vez que abre.

A assinatura (HMAC-SHA256) garante que o token não foi forjado --
só quem tem o SEGREDO (o servidor, e o próprio código do WebNest,
onde ele vem embutido) consegue gerar um token que passe na
verificação. Isso não é uma proteção perfeita contra alguém disposto
a ler o código-fonte Python e extrair o segredo -- mas isso vale pra
qualquer proteção puramente em software sem hardware dedicado
(dongle físico). O objetivo aqui é impedir uso casual indevido entre
usuários de negócio comuns, não resistir a um atacante técnico
motivado.

MUITO IMPORTANTE: o valor de SEGREDO_COMPARTILHADO abaixo precisa ser
IDÊNTICO nos dois lados (aqui no servidor, e em webapp/licenca.py no
cliente). Se mudar aqui, precisa mudar lá também, e todo mundo que já
ativou vai precisar reativar.
"""

import hmac
import hashlib
import base64
import json
import time

SEGREDO_COMPARTILHADO = b"NE8McTfe7hwv2YgZ-rqaRgTnjQ9inWvxd65mOS5ZhcecodJ27F5sArtKi_rfnJdz"


def gerar_token(chave, maquina_id):
    payload = {"chave": chave, "maquina_id": maquina_id, "emitido_em": int(time.time())}
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode()
    assinatura = hmac.new(SEGREDO_COMPARTILHADO, payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{assinatura}"


def verificar_token(token):
    """Devolve o payload (dict) se o token for genuíno, ou None se for inválido/forjado/malformado."""
    try:
        payload_b64, assinatura = token.split(".", 1)
    except (ValueError, AttributeError):
        return None

    assinatura_esperada = hmac.new(SEGREDO_COMPARTILHADO, payload_b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(assinatura, assinatura_esperada):
        return None  # assinatura não bate -- token forjado ou corrompido

    try:
        payload_json = base64.urlsafe_b64decode(payload_b64.encode()).decode()
        return json.loads(payload_json)
    except Exception:
        return None
