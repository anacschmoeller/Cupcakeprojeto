"""Controladores HTTP do site e área administrativa."""
import secrets
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import (Blueprint, abort, flash, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash

from .db import get_db

site = Blueprint("site", __name__)
FEE_CENTS = 500  # R$ 5,00 apenas para demonstração
STATES = {
    "RECEBIDO": {"EM_PREPARACAO", "CANCELADO"},
    "EM_PREPARACAO": {"PRONTO", "CANCELADO"},
    "PRONTO": {"CONCLUIDO", "CANCELADO"},
    "CONCLUIDO": set(),
    "CANCELADO": set(),
}
STATUS_LABELS = {"RECEBIDO":"Recebido", "EM_PREPARACAO":"Em preparação",
                 "PRONTO":"Pronto", "CONCLUIDO":"Concluído", "CANCELADO":"Cancelado"}


def positive_int(value):
    try:
        n = int(value)
    except (ValueError, TypeError):
        return None
    return n if 0 < n <= 99 else None


def parse_price(value):
    try:
        d = Decimal((value or "").strip().replace(",", "."))
        cents = d * 100
        if d <= 0 or cents != cents.to_integral_value() or cents > 10_000_000:
            return None
        return int(cents)
    except (InvalidOperation, ValueError):
        return None


def cart_contents():
    db = get_db()
    cart = session.get("cart", {})
    lines = []
    for key, raw_qty in cart.items():
        qty = positive_int(raw_qty)
        if not qty:
            continue
        try:
            product_id = int(key)
        except ValueError:
            continue
        product = db.execute("SELECT * FROM produtos WHERE id=?", (product_id,)).fetchone()
        if product:
            lines.append({"product":product, "qty":qty,
                          "subtotal":qty*product["preco_centavos"]})
    return lines, sum(line["subtotal"] for line in lines)


def admin_required(func):
    @wraps(func)
    def inner(*args, **kwargs):
        if not session.get("admin_id"):
            flash("Entre como administrador para continuar.", "erro")
            return redirect(url_for("site.login"))
        return func(*args, **kwargs)
    return inner


@site.get("/")
def index():
    products = get_db().execute("SELECT * FROM produtos WHERE disponivel=1 ORDER BY nome").fetchall()
    return render_template("catalogo.html", products=products)


@site.post("/carrinho/adicionar/<int:product_id>")
def add_cart(product_id):
    product = get_db().execute("SELECT id FROM produtos WHERE id=? AND disponivel=1", (product_id,)).fetchone()
    if not product:
        flash("Produto indisponível.", "erro")
        return redirect(url_for("site.index"))
    cart = dict(session.get("cart", {}))
    current = int(cart.get(str(product_id), 0))
    if current >= 99:
        flash("Limite de 99 unidades por produto.", "erro")
    else:
        cart[str(product_id)] = current + 1
        session["cart"] = cart
        flash("Cupcake adicionado ao carrinho!", "sucesso")
    return redirect(url_for("site.index"))


@site.get("/carrinho")
def cart():
    lines, subtotal = cart_contents()
    return render_template("carrinho.html", lines=lines, subtotal=subtotal)


@site.post("/carrinho/atualizar/<int:product_id>")
def update_cart(product_id):
    cart = dict(session.get("cart", {}))
    if str(product_id) not in cart:
        abort(404)
    raw = request.form.get("quantidade", "")
    if raw == "0":
        cart.pop(str(product_id), None)
    else:
        qty = positive_int(raw)
        if qty is None:
            flash("Informe quantidade de 1 a 99.", "erro")
            return redirect(url_for("site.cart"))
        cart[str(product_id)] = qty
    session["cart"] = cart
    return redirect(url_for("site.cart"))


@site.post("/carrinho/remover/<int:product_id>")
def remove_cart(product_id):
    cart = dict(session.get("cart", {}))
    cart.pop(str(product_id), None)
    session["cart"] = cart
    return redirect(url_for("site.cart"))


@site.route("/finalizar", methods=["GET", "POST"])
def checkout():
    lines, subtotal = cart_contents()
    if not lines:
        flash("Seu carrinho está vazio.", "erro")
        return redirect(url_for("site.cart"))
    if any(not line["product"]["disponivel"] for line in lines):
        flash("Há um produto indisponível no carrinho. Remova-o antes de continuar.", "erro")
        return redirect(url_for("site.cart"))

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        telefone = request.form.get("telefone", "").strip()
        modalidade = request.form.get("modalidade", "")
        endereco = request.form.get("endereco", "").strip()
        if len(nome) < 2 or len(telefone) < 8:
            flash("Informe seu nome e telefone (mínimo de 8 caracteres).", "erro")
        elif modalidade not in {"RETIRADA", "ENTREGA"}:
            flash("Selecione retirada ou entrega.", "erro")
        elif modalidade == "ENTREGA" and len(endereco) < 8:
            flash("Informe um endereço de entrega completo.", "erro")
        else:
            fee = FEE_CENTS if modalidade == "ENTREGA" else 0
            code = secrets.token_urlsafe(24)
            db = get_db()
            # Inserção atômica: um erro em qualquer item desfaz todo o pedido.
            with db:
                customer = db.execute("INSERT INTO clientes(nome, telefone) VALUES(?,?)",
                                      (nome, telefone))
                order = db.execute(
                    """INSERT INTO pedidos(codigo_publico,cliente_id,modalidade,endereco_entrega,
                       taxa_entrega_centavos,total_centavos)
                       VALUES(?,?,?,?,?,?)""",
                    (code, customer.lastrowid, modalidade,
                     endereco if modalidade == "ENTREGA" else None, fee, subtotal + fee))
                for line in lines:
                    prod = line["product"]
                    db.execute("""INSERT INTO itens_pedido(pedido_id,produto_id,nome_produto_historico,
                                  quantidade,preco_unitario_centavos) VALUES(?,?,?,?,?)""",
                               (order.lastrowid, prod["id"], prod["nome"], line["qty"], prod["preco_centavos"]))
            session["cart"] = {}
            return redirect(url_for("site.confirmation", token=code))
    return render_template("checkout.html", lines=lines, subtotal=subtotal, fee=FEE_CENTS)


@site.get("/pedido/<token>")
def confirmation(token):
    db = get_db()
    order = db.execute("""SELECT p.*, c.nome AS cliente_nome FROM pedidos p
                          JOIN clientes c ON c.id=p.cliente_id WHERE p.codigo_publico=?""", (token,)).fetchone()
    if not order:
        abort(404)
    items = db.execute("SELECT * FROM itens_pedido WHERE pedido_id=?", (order["id"],)).fetchall()
    return render_template("confirmacao.html", order=order, items=items)


@site.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("usuario", "").strip().lower()
        password = request.form.get("senha", "")
        admin = get_db().execute("SELECT * FROM administradores WHERE usuario=?", (username,)).fetchone()
        if admin and check_password_hash(admin["senha_hash"], password):
            # Nova sessão evita carregar um carrinho ou tokens de sessão anterior.
            session.clear()
            session["admin_id"] = admin["id"]
            flash("Bem-vinda à administração!", "sucesso")
            return redirect(url_for("site.admin_dashboard"))
        flash("Usuário ou senha incorretos.", "erro")
    return render_template("login.html")


@site.post("/admin/sair")
@admin_required
def logout():
    session.clear()
    flash("Você saiu da administração.", "sucesso")
    return redirect(url_for("site.index"))


@site.get("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    products = db.execute("SELECT * FROM produtos ORDER BY id DESC").fetchall()
    orders = db.execute("""SELECT p.*, c.nome AS cliente_nome, c.telefone
                           FROM pedidos p JOIN clientes c ON c.id=p.cliente_id
                           ORDER BY p.id DESC""").fetchall()
    order_items = {}
    for order in orders:
        order_items[order["id"]] = db.execute("SELECT * FROM itens_pedido WHERE pedido_id=?",(order["id"],)).fetchall()
    return render_template("admin.html", products=products, orders=orders,
                           order_items=order_items, status_labels=STATUS_LABELS, states=STATES)


@site.post("/admin/produtos")
@admin_required
def add_product():
    nome = request.form.get("nome", "").strip()
    descricao = request.form.get("descricao", "").strip()
    price = parse_price(request.form.get("preco", ""))
    emoji = request.form.get("emoji", "🧁").strip()[:4] or "🧁"
    if len(nome) < 2 or not descricao or price is None:
        flash("Informe nome, descrição e preço válido maior que zero.", "erro")
    else:
        db=get_db()
        with db:
            db.execute("INSERT INTO produtos(nome,descricao,preco_centavos,emoji) VALUES(?,?,?,?)",
                       (nome,descricao,price,emoji))
        flash("Produto cadastrado.", "sucesso")
    return redirect(url_for("site.admin_dashboard"))


@site.post("/admin/produtos/<int:product_id>/editar")
@admin_required
def edit_product(product_id):
    nome = request.form.get("nome", "").strip()
    descricao = request.form.get("descricao", "").strip()
    price = parse_price(request.form.get("preco", ""))
    availability = 1 if request.form.get("disponivel") == "1" else 0
    emoji = request.form.get("emoji", "🧁").strip()[:4] or "🧁"
    if len(nome) < 2 or not descricao or price is None:
        flash("Verifique os dados do produto.", "erro")
    else:
        db=get_db()
        with db:
            cursor=db.execute("""UPDATE produtos SET nome=?,descricao=?,preco_centavos=?,
                                  emoji=?,disponivel=? WHERE id=?""",
                              (nome,descricao,price,emoji,availability,product_id))
        flash("Produto atualizado." if cursor.rowcount else "Produto não encontrado.", "sucesso" if cursor.rowcount else "erro")
    return redirect(url_for("site.admin_dashboard"))


@site.post("/admin/pedidos/<int:order_id>/status")
@admin_required
def update_status(order_id):
    new_status=request.form.get("status", "")
    db=get_db()
    order=db.execute("SELECT status FROM pedidos WHERE id=?", (order_id,)).fetchone()
    if order is None:
        abort(404)
    if new_status not in STATES[order["status"]]:
        flash("Mudança de status não permitida.", "erro")
    else:
        with db:
            db.execute("UPDATE pedidos SET status=? WHERE id=?", (new_status,order_id))
        flash("Status atualizado.", "sucesso")
    return redirect(url_for("site.admin_dashboard"))
