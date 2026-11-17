"""Inicialização do Cupcake Gourmet e comandos de manutenção."""
import os
import secrets
from pathlib import Path

import click
from flask import Flask, abort, g, request, session

from .db import close_db, get_db, init_db, seed_products


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "chave-exclusiva-de-desenvolvimento-nao-publicar"),
        DATABASE=str(Path(app.instance_path) / "cupcake.sqlite3"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=1024 * 1024,
    )
    if os.environ.get("DATABASE_PATH"):
        app.config["DATABASE"] = os.environ["DATABASE_PATH"]
    if test_config:
        app.config.update(test_config)
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)

    app.teardown_appcontext(close_db)

    @app.template_filter("reais")
    def reais(centavos):
        valor = int(centavos or 0) / 100
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @app.before_request
    def check_csrf():
        if request.method == "POST":
            provided = request.form.get("csrf_token", "")
            expected = session.get("csrf_token", "")
            if not expected or not secrets.compare_digest(provided, expected):
                abort(400, description="Formulário expirado. Atualize a página e tente novamente.")

    @app.context_processor
    def common_values():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(24)
        cart = session.get("cart", {})
        return {"csrf_token": session["csrf_token"],
                "cart_count": sum(int(q) for q in cart.values()),
                "admin_logged_in": bool(session.get("admin_id"))}

    @app.cli.command("init-db")
    def init_db_command():
        init_db()
        seed_products()
        click.echo("Banco criado e três produtos de exemplo cadastrados.")

    @app.cli.command("create-admin")
    @click.option("--usuario", prompt="Nome de usuário")
    @click.password_option(prompt="Senha do administrador", confirmation_prompt=True)
    def create_admin_command(usuario, password):
        from werkzeug.security import generate_password_hash
        usuario = usuario.strip().lower()
        if len(usuario) < 3 or len(password) < 10:
            raise click.ClickException("Use usuário com 3+ caracteres e senha com 10+ caracteres.")
        db = get_db()
        try:
            with db:
                db.execute("INSERT INTO administradores (usuario, senha_hash) VALUES (?, ?)",
                           (usuario, generate_password_hash(password)))
        except Exception as exc:
            raise click.ClickException("Usuário já existe ou o banco não foi inicializado.") from exc
        click.echo("Administrador cadastrado. Não compartilhe a senha.")

    from .routes import site
    app.register_blueprint(site)
    return app
