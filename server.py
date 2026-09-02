"""
Servidor central de licenças do WebNest -- roda separado do sistema
em si, hospedado publicamente (ex: Render.com), e é contatado pelo
WebNest de cada cliente só na hora de ativar e nas verificações
periódicas depois disso. NÃO faz parte do sistema de nesting em si --
é uma peça só do Thomazelli, pra controlar quem comprou e onde cada
licença está instalada.
"""

import os
from functools import wraps
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash

import licencas_db as db
from token_assinado import gerar_token
import backup_email

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "troque-esta-chave-tambem-lqk3n")

SENHA_ADMIN = os.environ.get("LICENSE_ADMIN_PASSWORD", "troque-esta-senha")

# manda o backup por e-mail periodicamente, sozinho, em segundo plano
# -- não faz nada se as variáveis de ambiente de e-mail não estiverem
# configuradas (veja backup_email.py)
backup_email.iniciar_backup_periodico_em_segundo_plano()


def admin_obrigatorio(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logado"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


# ============================================================
# API pública -- é isso que o WebNest de cada cliente contata
# ============================================================

@app.route("/ativar", methods=["POST"])
def api_ativar():
    dados = request.get_json(silent=True) or {}
    chave = (dados.get("chave") or "").strip().upper()
    maquina_id = (dados.get("maquina_id") or "").strip()
    nome_maquina = (dados.get("nome_maquina") or "").strip()

    if not chave or not maquina_id:
        return jsonify({"ok": False, "motivo": "dados_incompletos"}), 400

    ok, motivo = db.ativar_licenca(chave, maquina_id, nome_maquina)
    if not ok:
        return jsonify({"ok": False, "motivo": motivo}), 409

    token = gerar_token(chave, maquina_id)
    return jsonify({"ok": True, "motivo": motivo, "token": token})


@app.route("/verificar", methods=["POST"])
def api_verificar():
    dados = request.get_json(silent=True) or {}
    chave = (dados.get("chave") or "").strip().upper()
    maquina_id = (dados.get("maquina_id") or "").strip()

    if not chave or not maquina_id:
        return jsonify({"ok": False, "motivo": "dados_incompletos"}), 400

    ok, motivo = db.verificar_licenca(chave, maquina_id)
    if not ok:
        return jsonify({"ok": False, "motivo": motivo}), 409

    token = gerar_token(chave, maquina_id)
    return jsonify({"ok": True, "motivo": motivo, "token": token})


# ============================================================
# Painel administrativo -- só o Thomazelli usa isso, protegido por senha
# ============================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("senha") == SENHA_ADMIN:
            session["admin_logado"] = True
            return redirect(url_for("admin_painel"))
        flash("Senha incorreta.")
    return render_template("admin_login.html")


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin", methods=["GET"])
@admin_obrigatorio
def admin_painel():
    return render_template("admin_painel.html", licencas=db.listar_licencas(),
                            backup_email_configurado=backup_email.configurado(),
                            backup_email_dias=backup_email.DIAS_ENTRE_BACKUPS)


@app.route("/admin/gerar", methods=["POST"])
@admin_obrigatorio
def admin_gerar():
    try:
        chave = db.gerar_licenca(request.form.get("cliente"), request.form.get("observacoes", ""))
        flash(f"Licença gerada: {chave}")
    except ValueError as e:
        flash(str(e))
    return redirect(url_for("admin_painel"))


@app.route("/admin/revogar", methods=["POST"])
@admin_obrigatorio
def admin_revogar():
    chave = request.form.get("chave")
    db.revogar_licenca(chave)
    flash(f"Licença {chave} revogada.")
    return redirect(url_for("admin_painel"))


@app.route("/admin/liberar", methods=["POST"])
@admin_obrigatorio
def admin_liberar():
    chave = request.form.get("chave")
    db.liberar_licenca(chave)
    flash(f"Licença {chave} liberada -- pode ser ativada numa máquina nova agora.")
    return redirect(url_for("admin_painel"))


@app.route("/admin/backup", methods=["GET"])
@admin_obrigatorio
def admin_backup():
    """
    Baixa uma cópia do banco de licenças agora mesmo -- pra guardar em
    algum lugar FORA do Render (seu computador, Google Drive, e-mail
    pra você mesmo etc.). O disco persistente já protege contra
    reinício/redeploy, mas isso aqui é uma segunda camada de
    segurança, pra qualquer problema que afete o disco em si.
    """
    from flask import send_file
    from datetime import datetime
    nome_arquivo = f"licencas_backup_{datetime.now().strftime('%Y-%m-%d_%H%M')}.db"
    return send_file(db.DB_PATH, as_attachment=True, download_name=nome_arquivo)


@app.route("/admin/backup-email", methods=["POST"])
@admin_obrigatorio
def admin_backup_email():
    """Dispara o envio do backup por e-mail JÁ (sem esperar o prazo automático) -- útil pra testar se a configuração está funcionando."""
    ok, mensagem = backup_email.enviar_backup_agora()
    flash(mensagem)
    return redirect(url_for("admin_painel"))


@app.route("/", methods=["GET"])
def home():
    return redirect(url_for("admin_painel"))


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=porta, debug=False)
