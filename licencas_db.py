"""
Banco de licenças do WebNest. Cada linha é UMA venda -- uma chave, um
cliente, e o "estado" dela ao longo do tempo:

  nao_ativada -> ainda não foi usada em nenhuma máquina (gerada, mas
                 o cliente ainda não digitou ela no sistema)
  ativa       -> já foi vinculada a UMA máquina específica (guardada
                 em `maquina_id`) -- é esse vínculo que impede a
                 mesma chave de ser usada em outro computador
  revogada    -> desativada manualmente (ex: cliente parou de pagar) --
                 o WebNest daquele cliente para de funcionar na
                 próxima verificação periódica
"""

import os
import sqlite3
import secrets
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "licencas.db")


def _conectar():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _conectar()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS licencas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT UNIQUE NOT NULL,
            cliente TEXT NOT NULL,
            observacoes TEXT,
            status TEXT NOT NULL DEFAULT 'nao_ativada',
            maquina_id TEXT,
            nome_maquina TEXT,
            criada_em TEXT NOT NULL,
            ativada_em TEXT,
            ultima_verificacao TEXT
        )
    """)
    conn.commit()
    conn.close()


def _gerar_chave():
    """Formato tipo WEBNEST-XXXX-XXXX-XXXX-XXXX -- fácil de digitar/ler em voz alta, difícil de adivinhar."""
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem 0/O/1/I, pra evitar confusão visual
    grupos = ["".join(secrets.choice(alfabeto) for _ in range(4)) for _ in range(4)]
    return "WEBNEST-" + "-".join(grupos)


def gerar_licenca(cliente, observacoes=""):
    cliente = (cliente or "").strip()
    if not cliente:
        raise ValueError("Informe o nome do cliente.")

    conn = _conectar()
    for _ in range(5):  # praticamente impossível colidir, mas tenta de novo se colidir por azar
        chave = _gerar_chave()
        existe = conn.execute("SELECT 1 FROM licencas WHERE chave = ?", (chave,)).fetchone()
        if not existe:
            break
    else:
        conn.close()
        raise RuntimeError("Não foi possível gerar uma chave única -- tente de novo.")

    conn.execute("""
        INSERT INTO licencas (chave, cliente, observacoes, status, criada_em)
        VALUES (?, ?, ?, 'nao_ativada', ?)
    """, (chave, cliente, observacoes, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    return chave


def obter_licenca(chave):
    conn = _conectar()
    linha = conn.execute("SELECT * FROM licencas WHERE chave = ?", (chave,)).fetchone()
    conn.close()
    return dict(linha) if linha else None


def listar_licencas():
    conn = _conectar()
    linhas = conn.execute("SELECT * FROM licencas ORDER BY criada_em DESC").fetchall()
    conn.close()
    return [dict(r) for r in linhas]


def ativar_licenca(chave, maquina_id, nome_maquina=""):
    """
    Tenta vincular a chave a essa máquina. Devolve (ok, mensagem):
    - (True, "ativada"): primeira ativação, vinculada com sucesso
    - (True, "ja_ativada_aqui"): já estava ativa NESSA MESMA máquina
      (reinstalação/reabertura normal -- não é bloqueado)
    - (False, "em_uso"): já está ativa em OUTRA máquina -- bloqueado
    - (False, "revogada"): a licença foi desativada manualmente
    - (False, "nao_encontrada"): chave não existe
    """
    conn = _conectar()
    linha = conn.execute("SELECT * FROM licencas WHERE chave = ?", (chave,)).fetchone()
    if linha is None:
        conn.close()
        return False, "nao_encontrada"

    if linha["status"] == "revogada":
        conn.close()
        return False, "revogada"

    agora = datetime.now().isoformat(timespec="seconds")

    if linha["status"] == "ativa":
        if linha["maquina_id"] == maquina_id:
            conn.execute("UPDATE licencas SET ultima_verificacao = ? WHERE chave = ?", (agora, chave))
            conn.commit()
            conn.close()
            return True, "ja_ativada_aqui"
        conn.close()
        return False, "em_uso"

    # nao_ativada -> primeira ativação
    conn.execute("""
        UPDATE licencas SET status = 'ativa', maquina_id = ?, nome_maquina = ?,
               ativada_em = ?, ultima_verificacao = ?
        WHERE chave = ?
    """, (maquina_id, nome_maquina, agora, agora, chave))
    conn.commit()
    conn.close()
    return True, "ativada"


def verificar_licenca(chave, maquina_id):
    """
    Confirma que a chave continua ativa E vinculada a ESSA máquina --
    usado na reverificação periódica, não só na ativação inicial.
    Devolve (ok, motivo) com os mesmos códigos de ativar_licenca.
    """
    conn = _conectar()
    linha = conn.execute("SELECT * FROM licencas WHERE chave = ?", (chave,)).fetchone()
    if linha is None:
        conn.close()
        return False, "nao_encontrada"
    if linha["status"] == "revogada":
        conn.close()
        return False, "revogada"
    if linha["status"] != "ativa" or linha["maquina_id"] != maquina_id:
        conn.close()
        return False, "em_uso"

    conn.execute("UPDATE licencas SET ultima_verificacao = ? WHERE chave = ?",
                 (datetime.now().isoformat(timespec="seconds"), chave))
    conn.commit()
    conn.close()
    return True, "ok"


def revogar_licenca(chave):
    conn = _conectar()
    cur = conn.execute("UPDATE licencas SET status = 'revogada' WHERE chave = ?", (chave,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def liberar_licenca(chave):
    """Reseta a licença pra 'nao_ativada', apagando o vínculo de máquina -- útil pra transferir pra outro computador, ou reativar depois de uma revogação por engano."""
    conn = _conectar()
    cur = conn.execute("""
        UPDATE licencas SET status = 'nao_ativada', maquina_id = NULL, nome_maquina = NULL,
               ativada_em = NULL, ultima_verificacao = NULL
        WHERE chave = ?
    """, (chave,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


init_db()
