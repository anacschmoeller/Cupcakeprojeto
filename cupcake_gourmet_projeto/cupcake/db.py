"""Persistência SQLite. SQL parametrizado em todas as consultas com entrada externa."""
import sqlite3
from pathlib import Path

from flask import current_app, g


def get_db():
    if "db" not in g:
        db = sqlite3.connect(current_app.config["DATABASE"])
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 5000")
        g.db = db
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    db.executescript(schema)
    db.commit()


def seed_products():
    db = get_db()
    if db.execute("SELECT COUNT(*) AS n FROM produtos").fetchone()["n"]:
        return
    products = [
        ("Chocolate Belga", "Massa de chocolate e cobertura cremosa.", 1200, "🍫", 1),
        ("Baunilha", "Massa macia e cobertura de baunilha.", 1100, "🧁", 1),
        ("Red Velvet", "Massa vermelha com cobertura suave.", 1400, "❤️", 1),
        ("Morango", "Cupcake delicado com cobertura de morango.", 1300, "🍓", 1),
        ("Limão", "Massa cítrica com cobertura aveludada.", 1200, "🍋", 1),
        ("Doce de Leite", "Recheio e cobertura de doce de leite.", 1500, "🍯", 1),
    ]
    with db:
        db.executemany("INSERT INTO produtos(nome,descricao,preco_centavos,emoji,disponivel) VALUES(?,?,?,?,?)", products)
