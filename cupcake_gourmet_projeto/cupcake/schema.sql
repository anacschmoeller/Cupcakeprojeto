PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS clientes (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 nome TEXT NOT NULL CHECK(length(trim(nome)) >= 2),
 telefone TEXT NOT NULL CHECK(length(trim(telefone)) >= 8)
);

CREATE TABLE IF NOT EXISTS produtos (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 nome TEXT NOT NULL CHECK(length(trim(nome)) >= 2),
 descricao TEXT NOT NULL,
 preco_centavos INTEGER NOT NULL CHECK(preco_centavos > 0),
 emoji TEXT NOT NULL DEFAULT '🧁',
 disponivel INTEGER NOT NULL DEFAULT 1 CHECK(disponivel IN (0,1))
);

CREATE TABLE IF NOT EXISTS administradores (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 usuario TEXT NOT NULL UNIQUE,
 senha_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pedidos (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 codigo_publico TEXT NOT NULL UNIQUE,
 cliente_id INTEGER NOT NULL REFERENCES clientes(id),
 criado_em TEXT NOT NULL DEFAULT (datetime('now')),
 modalidade TEXT NOT NULL CHECK(modalidade IN ('RETIRADA','ENTREGA')),
 endereco_entrega TEXT,
 taxa_entrega_centavos INTEGER NOT NULL DEFAULT 0 CHECK(taxa_entrega_centavos >= 0),
 total_centavos INTEGER NOT NULL CHECK(total_centavos >= 0),
 status TEXT NOT NULL DEFAULT 'RECEBIDO' CHECK(status IN ('RECEBIDO','EM_PREPARACAO','PRONTO','CONCLUIDO','CANCELADO')),
 CHECK((modalidade='RETIRADA' AND endereco_entrega IS NULL AND taxa_entrega_centavos=0) OR
       (modalidade='ENTREGA' AND length(trim(endereco_entrega)) >= 8))
);

CREATE TABLE IF NOT EXISTS itens_pedido (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 pedido_id INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
 produto_id INTEGER NOT NULL REFERENCES produtos(id),
 nome_produto_historico TEXT NOT NULL,
 quantidade INTEGER NOT NULL CHECK(quantidade > 0),
 preco_unitario_centavos INTEGER NOT NULL CHECK(preco_unitario_centavos > 0),
 UNIQUE(pedido_id,produto_id)
);

CREATE INDEX IF NOT EXISTS ix_pedidos_cliente ON pedidos(cliente_id);
CREATE INDEX IF NOT EXISTS ix_pedidos_data ON pedidos(criado_em);
CREATE INDEX IF NOT EXISTS ix_itens_pedido ON itens_pedido(pedido_id);
