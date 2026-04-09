"""
main.py — Orquestrador principal do Bot Nora Shop

Uso:
    python main.py              # roda scraping + envia ofertas
    python main.py --setup      # inicializa banco e keywords de exemplo
    python main.py --painel     # sobe o painel web (porta 5001)
    python main.py --sync-wa    # sincroniza grupos do WhatsApp no banco
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from core.database import (
    init_db, listar_keywords_ativas, listar_produtos_ativos,
    get_conn, ja_enviada_recentemente
)
from scrapers import mercadolivre, magazineluiza, amazon, shopee


async def coletar_todas() -> list[dict]:
    keywords = listar_keywords_ativas()
    produtos  = listar_produtos_ativos()
    print(f"[BOT] Keywords ativas: {len(keywords)} | Produtos monitorados: {len(produtos)}")

    todas = []
    todas += await mercadolivre.executar(keywords=keywords, produtos=produtos)
    todas += await magazineluiza.executar(keywords=keywords, produtos=produtos)
    todas += await amazon.executar(keywords=keywords, produtos=produtos)
    todas += await shopee.executar(keywords=keywords, produtos=produtos)
    # TODO: aliexpress

    print(f"[BOT] Total coletado: {len(todas)} ofertas")
    return todas


def enviar_ofertas(ofertas: list[dict]):
    """Envia as ofertas coletadas para os grupos do WhatsApp."""
    try:
        from sender.whatsapp_sender import enfileirar_oferta, esta_online
    except ImportError:
        print("[BOT] sender/whatsapp_sender.py não encontrado — pulando envio WA")
        return

    if not esta_online():
        print("[BOT] WhatsApp offline — rode: node sender/whatsapp.js")
        return

    enviadas = 0
    for oferta in ofertas:
        # Busca cupom ativo para a loja, se houver
        cupom = _buscar_cupom_ativo(oferta.get('loja'))
        ok = enfileirar_oferta(oferta, cupom=cupom)
        if ok:
            enviadas += 1

    print(f"[BOT] {enviadas}/{len(ofertas)} ofertas enfileiradas para WA")


def _buscar_cupom_ativo(loja: str) -> dict | None:
    """Busca o cupom mais recente ativo para uma loja."""
    if not loja:
        return None
    try:
        conn = get_conn()
        row = conn.execute("""
            SELECT * FROM cupons
            WHERE loja=? AND ativo=1
            ORDER BY criado_em DESC LIMIT 1
        """, (loja,)).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None


def setup_inicial():
    init_db()
    _ensure_all_tables()
    conn = get_conn()
    c = conn.cursor()

    exemplos = [
        ('fone bluetooth',    'todas',          20, 300.0),
        ('smartwatch',        'todas',          25, 500.0),
        ('carregador wireless','mercadolivre',  15, 150.0),
        ('mouse sem fio',     'magazineluiza',  20, 200.0),
        ('fritadeira airfryer','todas',         20, 600.0),
    ]
    for (termo, loja, desc, pmax) in exemplos:
        c.execute('''
            INSERT OR IGNORE INTO keywords (termo, loja, desconto_minimo, preco_maximo)
            VALUES (?, ?, ?, ?)
        ''', (termo, loja, desc, pmax))
    conn.commit()
    conn.close()

    print("[SETUP] Banco criado com keywords de exemplo.")
    print("\nPróximos passos:")
    print("  1. Preencha os IDs em core/afiliados.py")
    print("  2. Inicie o WhatsApp: node sender/whatsapp.js")
    print("  3. Escaneie o QR code com o celular")
    print("  4. Suba o painel: python main.py --painel")
    print("  5. No painel, ative os grupos em /grupos")
    print("  6. Rode: python main.py")
    print("  7. Cron: */30 * * * * cd /home/pi/nora-shop-bot && python main.py >> logs/bot.log 2>&1")


def _ensure_all_tables():
    conn = get_conn()
    conn.execute('''CREATE TABLE IF NOT EXISTS grupos_whatsapp (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id TEXT UNIQUE NOT NULL,
        nome TEXT NOT NULL,
        participantes INTEGER DEFAULT 0,
        ativo INTEGER DEFAULT 1,
        ultima_atualizacao TEXT DEFAULT (datetime('now'))
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS cupons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        loja TEXT NOT NULL, codigo TEXT NOT NULL,
        descricao TEXT, desconto_tipo TEXT DEFAULT 'percentual',
        desconto_valor REAL, preco_minimo REAL, valido_ate TEXT,
        url_produto TEXT, aplicar_no_link INTEGER DEFAULT 0,
        ativo INTEGER DEFAULT 1, criado_em TEXT DEFAULT (datetime('now'))
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS ofertas_manuais (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        loja TEXT NOT NULL, titulo TEXT NOT NULL, url TEXT NOT NULL,
        url_afiliado TEXT, preco_atual REAL, preco_original REAL,
        desconto_pct INTEGER, cupom_id INTEGER, imagem_url TEXT,
        criado_em TEXT DEFAULT (datetime('now'))
    )''')
    conn.commit()
    conn.close()
    os.makedirs(os.path.join(os.path.dirname(__file__), 'logs'), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), 'data'), exist_ok=True)


async def main():
    if '--setup' in sys.argv:
        setup_inicial()
        return

    if '--painel' in sys.argv:
        init_db()
        _ensure_all_tables()
        from sender.painel import app
        print("\n🛍️  Nora Shop — Painel iniciado")
        print("   Acesse: http://localhost:5001\n")
        app.run(host='0.0.0.0', port=5001, debug=False)
        return

    if '--sync-wa' in sys.argv:
        init_db()
        _ensure_all_tables()
        from sender.whatsapp_sender import sincronizar_grupos
        sincronizar_grupos()
        return

    # ── Ciclo normal ──────────────────────────────────────────────────
    init_db()
    _ensure_all_tables()

    ofertas = await coletar_todas()

    if not ofertas:
        print("[BOT] Nenhuma oferta encontrada nesta rodada.")
        return

    # Envia para WhatsApp
    enviar_ofertas(ofertas)

    # TODO: enviar para Instagram
    # from sender.instagram_sender import postar_oferta
    # for o in ofertas[:3]: postar_oferta(o)


if __name__ == '__main__':
    asyncio.run(main())
