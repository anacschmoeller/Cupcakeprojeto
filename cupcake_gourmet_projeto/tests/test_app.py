from cupcake.db import get_db


def add(client, csrf, product_id=1):
    return client.post(f"/carrinho/adicionar/{product_id}", data={"csrf_token": csrf})


def login(client, csrf):
    return client.post("/admin/login", data={"csrf_token": csrf,
                  "usuario": "ana", "senha": "senha-forte-de-teste"})


def test_catalogo_e_layout_responsivo(client):
    result = client.get("/")
    assert result.status_code == 200
    assert b"viewport" in result.data
    assert "Chocolate Belga" in result.get_data(as_text=True)


def test_formulario_sem_csrf_e_rejeitado(client):
    assert client.post("/carrinho/adicionar/1").status_code == 400


def test_carrinho_adicionar_alterar_remover(client, csrf):
    add(client, csrf)
    assert "R$ 12,00" in client.get("/carrinho").get_data(as_text=True)
    client.post("/carrinho/atualizar/1", data={"csrf_token": csrf, "quantidade": "3"})
    assert "R$ 36,00" in client.get("/carrinho").get_data(as_text=True)
    client.post("/carrinho/remover/1", data={"csrf_token": csrf})
    assert "carrinho está vazio" in client.get("/carrinho").get_data(as_text=True)


def test_quantidade_invalida_nao_e_aceita(client, csrf):
    add(client, csrf)
    client.post("/carrinho/atualizar/1", data={"csrf_token": csrf, "quantidade": "-5"})
    with client.session_transaction() as sess:
        assert sess["cart"]["1"] == 1


def test_produto_indisponivel_nao_entra_no_carrinho(app, client, csrf):
    with app.app_context():
        with get_db() as db:
            db.execute("UPDATE produtos SET disponivel=0 WHERE id=1")
    add(client, csrf)
    with client.session_transaction() as sess:
        assert sess.get("cart", {}) == {}


def test_carrinho_vazio_impede_checkout(client):
    response = client.get("/finalizar")
    assert response.status_code == 302
    assert "/carrinho" in response.headers["Location"]


def test_validacoes_do_checkout(client, csrf):
    add(client, csrf)
    response = client.post("/finalizar", data={"csrf_token": csrf, "nome": "A", "telefone": "123",
                     "modalidade": "ENTREGA", "endereco": "Rua curta"}, follow_redirects=True)
    assert "Informe seu nome" in response.get_data(as_text=True)
    response = client.post("/finalizar", data={"csrf_token": csrf, "nome": "Maria Silva",
                       "telefone": "11999999999", "modalidade": "ENTREGA", "endereco": "Rua"}, follow_redirects=True)
    assert "endereço de entrega completo" in response.get_data(as_text=True)


def test_pedido_entrega_gravado_com_preco_do_servidor(app, client, csrf):
    add(client, csrf)
    response=client.post("/finalizar", data={"csrf_token": csrf, "nome": "Maria Silva",
                "telefone": "11999999999", "modalidade": "ENTREGA", "endereco": "Rua das Flores 10",
                "preco_centavos": "1"})
    assert response.status_code == 302
    assert "/pedido/" in response.headers["Location"]
    confirmed=client.get(response.headers["Location"])
    assert "R$ 17,00" in confirmed.get_data(as_text=True)
    with app.app_context():
        db=get_db()
        order=db.execute("SELECT * FROM pedidos").fetchone()
        item=db.execute("SELECT * FROM itens_pedido").fetchone()
        assert order["total_centavos"] == 1700
        assert item["preco_unitario_centavos"] == 1200
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    with client.session_transaction() as sess:
        assert sess.get("cart") == {}


def test_retirada_sem_taxa(client, csrf):
    add(client, csrf)
    r=client.post("/finalizar", data={"csrf_token": csrf, "nome": "Maria Silva",
                   "telefone": "11999999999", "modalidade": "RETIRADA"})
    assert "R$ 12,00" in client.get(r.headers["Location"]).get_data(as_text=True)


def test_pedido_inexistente_nao_exposto(client):
    assert client.get("/pedido/codigo-que-nao-existe").status_code == 404


def test_painel_bloqueado_sem_login(client):
    assert "/admin/login" in client.get("/admin").headers["Location"]


def test_login_incorreto(client, csrf):
    r=client.post("/admin/login", data={"csrf_token": csrf, "usuario": "ana", "senha": "incorreta"},
                  follow_redirects=True)
    assert "senha incorretos" in r.get_data(as_text=True)


def test_admin_cadastro_e_edicao(app, client, csrf):
    login(client, csrf)
    client.get("/admin")
    with client.session_transaction() as sess:
        token=sess["csrf_token"]
    r=client.post("/admin/produtos", data={"csrf_token":token,"nome":"Coco", "descricao":"Coco fresco",
               "preco":"16,50", "emoji":"🥥"}, follow_redirects=True)
    assert "Coco" in r.get_data(as_text=True)
    with app.app_context():
        row=get_db().execute("SELECT * FROM produtos WHERE nome='Coco'").fetchone()
        assert row["preco_centavos"]==1650
        product_id=row["id"]
    client.post(f"/admin/produtos/{product_id}/editar", data={"csrf_token":token,"nome":"Coco novo",
                "descricao":"Coco fresco", "preco":"17,00", "emoji":"🥥", "disponivel":"0"})
    with app.app_context():
        row=get_db().execute("SELECT * FROM produtos WHERE id=?", (product_id,)).fetchone()
        assert (row["nome"],row["disponivel"],row["preco_centavos"]) == ("Coco novo",0,1700)


def test_admin_pedido_status_valido_e_invalido(app, client, csrf):
    add(client,csrf)
    client.post("/finalizar",data={"csrf_token":csrf,"nome":"Maria Silva","telefone":"11999999999",
                                   "modalidade":"RETIRADA"})
    client.get("/admin/login")
    with client.session_transaction() as sess:
        token=sess["csrf_token"]
    login(client,token)
    client.get("/admin")
    with client.session_transaction() as sess:
        token=sess["csrf_token"]
    client.post("/admin/pedidos/1/status",data={"csrf_token":token,"status":"EM_PREPARACAO"})
    client.post("/admin/pedidos/1/status",data={"csrf_token":token,"status":"CONCLUIDO"})
    with app.app_context():
        assert get_db().execute("SELECT status FROM pedidos WHERE id=1").fetchone()["status"] == "EM_PREPARACAO"
