"""
Envio automático de backup do banco de licenças por e-mail -- rede de
segurança extra além do disco persistente. Configurado via variáveis
de ambiente do Render (mesma convenção já usada pras outras
configurações do servidor de licenças):

  BACKUP_EMAIL_REMETENTE      -- conta de e-mail que envia (ex: Gmail)
  BACKUP_EMAIL_SENHA_APP      -- senha de APP dessa conta (não a senha normal)
  BACKUP_EMAIL_DESTINATARIO   -- pra onde manda (pode ser a mesma conta)
  BACKUP_EMAIL_DIAS           -- de quantos em quantos dias manda (padrão: 7)
  BACKUP_EMAIL_SMTP_HOST      -- padrão: smtp.gmail.com
  BACKUP_EMAIL_SMTP_PORT      -- padrão: 587

Se essas variáveis não estiverem configuradas, o recurso simplesmente
fica desligado -- não trava nem afeta o resto do servidor.
"""

import os
import time
import smtplib
import ssl
import threading
from email.message import EmailMessage
from datetime import datetime

import licencas_db as db

SMTP_HOST = os.environ.get("BACKUP_EMAIL_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("BACKUP_EMAIL_SMTP_PORT", "587"))
REMETENTE = os.environ.get("BACKUP_EMAIL_REMETENTE", "").strip()
SENHA_APP = os.environ.get("BACKUP_EMAIL_SENHA_APP", "").strip().replace(" ", "")  # espaço é erro comum ao colar senha de app
DESTINATARIO = os.environ.get("BACKUP_EMAIL_DESTINATARIO", "").strip() or REMETENTE
DIAS_ENTRE_BACKUPS = int(os.environ.get("BACKUP_EMAIL_DIAS", "7"))

_ARQUIVO_CONTROLE = os.path.join(os.path.dirname(db.DB_PATH), "ultimo_backup_enviado.txt")


def configurado():
    return bool(REMETENTE and SENHA_APP and DESTINATARIO)


def enviar_backup_agora():
    """Manda o backup por e-mail JÁ, sem esperar o prazo -- usado tanto pelo botão manual quanto pelo laço automático. Devolve (ok, mensagem)."""
    if not configurado():
        return False, ("E-mail de backup não configurado -- defina BACKUP_EMAIL_REMETENTE, "
                        "BACKUP_EMAIL_SENHA_APP e BACKUP_EMAIL_DESTINATARIO nas variáveis de "
                        "ambiente do serviço no Render.")

    if not os.path.isfile(db.DB_PATH):
        return False, "Banco de licenças ainda não existe -- nada pra fazer backup."

    agora = datetime.now()
    total_licencas = len(db.listar_licencas())

    msg = EmailMessage()
    msg["Subject"] = f"Backup licenças WebNest -- {agora.strftime('%d/%m/%Y')}"
    msg["From"] = REMETENTE
    msg["To"] = DESTINATARIO
    msg.set_content(
        f"Backup automático do banco de licenças do WebNest.\n\n"
        f"Data: {agora.strftime('%d/%m/%Y %H:%M')}\n"
        f"Total de licenças no banco: {total_licencas}\n\n"
        f"Guarde esse arquivo em lugar seguro -- ele contém todas as chaves já geradas."
    )

    with open(db.DB_PATH, "rb") as f:
        conteudo = f.read()
    nome_arquivo = f"licencas_backup_{agora.strftime('%Y-%m-%d')}.db"
    msg.add_attachment(conteudo, maintype="application", subtype="octet-stream", filename=nome_arquivo)

    try:
        contexto = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as servidor:
            servidor.starttls(context=contexto)
            servidor.login(REMETENTE, SENHA_APP)
            servidor.send_message(msg)
    except Exception as e:
        return False, f"Falha ao enviar o backup por e-mail: {type(e).__name__}: {e}"

    try:
        with open(_ARQUIVO_CONTROLE, "w") as f:
            f.write(str(time.time()))
    except Exception:
        pass  # não é crítico -- só afeta quando o próximo automático dispara

    return True, f"Backup enviado com sucesso pra {DESTINATARIO}."


def iniciar_backup_periodico_em_segundo_plano():
    """
    Roda em segundo plano, enviando o backup a cada DIAS_ENTRE_BACKUPS
    dias -- sem travar a inicialização do servidor se o e-mail não
    estiver configurado. A data do último envio fica salva no MESMO
    disco persistente do banco, então sobrevive a reinícios --
    sem isso, o servidor "esqueceria" quando foi o último envio toda
    vez que reiniciasse, e o backup nunca aconteceria de verdade.
    """
    if not configurado():
        return  # recurso desligado -- nem inicia a thread à toa

    def _loop():
        while True:
            deve_enviar = True
            if os.path.isfile(_ARQUIVO_CONTROLE):
                try:
                    with open(_ARQUIVO_CONTROLE) as f:
                        ultimo = float(f.read().strip())
                    dias_desde = (time.time() - ultimo) / 86400
                    deve_enviar = dias_desde >= DIAS_ENTRE_BACKUPS
                except Exception:
                    deve_enviar = True

            if deve_enviar:
                try:
                    enviar_backup_agora()
                except Exception:
                    pass  # tenta de novo na próxima rodada do laço, não derruba a thread

            time.sleep(3600)  # confere de novo em 1 hora se já é hora de mandar

    threading.Thread(target=_loop, daemon=True).start()
