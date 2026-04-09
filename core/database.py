import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'ofertas.db')

def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL, url TEXT NOT NULL, loja TEXT NOT NULL,
            preco_alvo REAL, desconto_minimo INTEGER DEFAULT 15, ativo INTEGER DEFAULT 1,
            criado_em TEXT DEFAULT (datetime('now'))
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            termo TEXT NOT NULL, loja TEXT NOT NULL, desconto_minimo INTEGER DEFAULT 20,
            preco_maximo REAL, ativo INTEGER DEFAULT 1,
            criado_em TEXT DEFAULT (datetime('now'))
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS historico_precos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER, keyword_id INTEGER, loja TEXT NOT NULL,
            titulo TEXT NOT NULL, url TEXT NOT NULL, url_afiliado TEXT,
            preco_atual REAL NOT NULL, preco_original REAL, desconto_pct INTEGER,
            imagem_url TEXT, coletado_em TEXT DEFAULT (datetime('now'))
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS ofertas_enviadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            historico_id INTEGER NOT NULL, canal TEXT NOT NULL, destino TEXT,
            enviado_em TEXT DEFAULT (datetime('now')),
            status TEXT DEFAULT 'enviado', erro_msg TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print(f"[DB] Banco inicializado em: {os.path.abspath(DB_PATH)}")

def salvar_preco(dados):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT INTO historico_precos
            (produto_id, keyword_id, loja, titulo, url, url_afiliado,
             preco_atual, preco_original, desconto_pct, imagem_url)
        VALUES
            (:produto_id, :keyword_id, :loja, :titulo, :url, :url_afiliado,
             :preco_atual, :preco_original, :desconto_pct, :imagem_url)
    ''', dados)
    id_ = c.lastrowid
    conn.commit()
    conn.close()
    return id_

def preco_minimo_historico(url, dias=30):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        SELECT MIN(preco_atual) FROM historico_precos
        WHERE url = ? AND coletado_em >= datetime('now', ? || ' days')
    ''', (url, f'-{dias}'))
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] else None

def ja_enviada_recentemente(url, horas=12):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        SELECT COUNT(*) FROM ofertas_enviadas oe
        JOIN historico_precos hp ON hp.id = oe.historico_id
        WHERE hp.url = ? AND oe.enviado_em >= datetime('now', ? || ' hours')
    ''', (url, f'-{horas}'))
    count = c.fetchone()[0]
    conn.close()
    return count > 0

def registrar_envio(historico_id, canal, destino, status='enviado', erro=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT INTO ofertas_enviadas (historico_id, canal, destino, status, erro_msg)
        VALUES (?, ?, ?, ?, ?)
    ''', (historico_id, canal, destino, status, erro))
    conn.commit()
    conn.close()

def listar_keywords_ativas():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM keywords WHERE ativo = 1")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def listar_produtos_ativos():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM produtos WHERE ativo = 1")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

if __name__ == '__main__':
    init_db()

def init_cupons(conn):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS cupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loja TEXT NOT NULL,
            codigo TEXT NOT NULL,
            descricao TEXT,
            desconto_tipo TEXT DEFAULT 'percentual',  -- percentual | fixo | frete
            desconto_valor REAL,
            preco_minimo REAL,
            valido_ate TEXT,
            url_produto TEXT,        -- NULL = cupom geral da loja
            aplicar_no_link INTEGER DEFAULT 0,  -- 1 = embutir na URL, 0 = só na mensagem
            ativo INTEGER DEFAULT 1,
            criado_em TEXT DEFAULT (datetime('now'))
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS ofertas_manuais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loja TEXT NOT NULL,
            titulo TEXT NOT NULL,
            url TEXT NOT NULL,
            url_afiliado TEXT,
            preco_atual REAL,
            preco_original REAL,
            desconto_pct INTEGER,
            cupom_id INTEGER,
            imagem_url TEXT,
            criado_em TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (cupom_id) REFERENCES cupons(id)
        )
    ''')
    conn.commit()

def salvar_cupom(dados: dict) -> int:
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT INTO cupons
            (loja, codigo, descricao, desconto_tipo, desconto_valor,
             preco_minimo, valido_ate, url_produto, aplicar_no_link)
        VALUES
            (:loja, :codigo, :descricao, :desconto_tipo, :desconto_valor,
             :preco_minimo, :valido_ate, :url_produto, :aplicar_no_link)
    ''', dados)
    id_ = c.lastrowid
    conn.commit()
    conn.close()
    return id_

def listar_cupons_ativos(loja: str = None):
    conn = get_conn()
    c = conn.cursor()
    if loja:
        c.execute("SELECT * FROM cupons WHERE ativo=1 AND loja=? ORDER BY criado_em DESC", (loja,))
    else:
        c.execute("SELECT * FROM cupons WHERE ativo=1 ORDER BY loja, criado_em DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def salvar_oferta_manual(dados: dict) -> int:
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT INTO ofertas_manuais
            (loja, titulo, url, url_afiliado, preco_atual, preco_original,
             desconto_pct, cupom_id, imagem_url)
        VALUES
            (:loja, :titulo, :url, :url_afiliado, :preco_atual, :preco_original,
             :desconto_pct, :cupom_id, :imagem_url)
    ''', dados)
    id_ = c.lastrowid
    conn.commit()
    conn.close()
    return id_
