import pytest
from werkzeug.security import generate_password_hash

from cupcake import create_app
from cupcake.db import get_db, init_db, seed_products


@pytest.fixture()
def app(tmp_path):
    app = create_app({"TESTING": True, "SECRET_KEY": "test-key-not-for-deployment",
                      "DATABASE": str(tmp_path / "test.sqlite3")})
    with app.app_context():
        init_db()
        seed_products()
        db = get_db()
        with db:
            db.execute("INSERT INTO administradores(usuario,senha_hash) VALUES(?,?)",
                       ("ana", generate_password_hash("senha-forte-de-teste")))
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def csrf(client):
    client.get("/")
    with client.session_transaction() as sess:
        return sess["csrf_token"]
