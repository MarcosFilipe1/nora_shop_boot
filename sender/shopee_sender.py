"""
Envia sessoes tematicas Shopee: 5 produtos por categoria nos grupos WhatsApp
"""
import os, sys, json
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from core.database import get_conn

ROOT    = os.path.join(os.path.dirname(__file__), '..')
QUEUE_F = os.path.join(ROOT, 'data', 'wa_queue.json')
LOG_F   = os.path.join(ROOT, 'logs', 'bot.log')

# Configuracao de horarios
SESSOES_HORARIO = {
    'manha': {
        'inicio': 8, 'fim': 12,
        'categorias': ['Roupas Femininas'],
    },
    'tarde': {
        'inicio': 12, 'fim': 18,
        'categorias': [],
    },
    'noite': {
        'inicio': 18, 'fim': 22,
        'categorias': ['Casa e Construção', 'Celulares e Dispositivos', 'Bolsas Femininas', 'Eletrodomésticos'],
    },
}

PRODUTOS_POR_SESSAO = 5

EMOJI_CATEGORIA = {
    'Roupas Femininas':           '👗',
    'Casa e Construção':          '🏠',
    'Celulares e Dispositivos':   '📱',
    'Bolsas Femininas':           '👜',
    'Eletrodomésticos':           '🔌',
}

def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'{ts} [SHOPEE_SENDER] {msg}\n'
    print(line, end='')
    with open(LOG_F, 'a') as f:
        f.write(line)

def grupos_ativos():
    try:
        conn = get_conn()
        rows = conn.execute('SELECT group_id FROM grupos_whatsapp WHERE ativo=1').fetchall()
        conn.close()
        return [r[0] for r in rows]
    except:
        return []

def proxima_categoria(periodo):
    """Pega proxima categoria do periodo (rotaciona)"""
    cats = SESSOES_HORARIO[periodo]['categorias']
    if not cats: return None
    # Conta quantas sessoes ja foram enviadas hoje por categoria
    hoje = datetime.now().strftime('%Y-%m-%d')
    conn = get_conn()
    conn.execute('''CREATE TABLE IF NOT EXISTS shopee_sessoes_enviadas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        categoria TEXT, data TEXT, periodo TEXT,
        enviada_em DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    # Pega a que foi menos enviada hoje
    menos_enviada = None
    menor_count = 99999
    for cat in cats:
        c = conn.execute('SELECT COUNT(*) FROM shopee_sessoes_enviadas WHERE categoria=? AND data=?', (cat, hoje)).fetchone()[0]
        if c < menor_count:
            menor_count = c
            menos_enviada = cat
    conn.close()
    return menos_enviada

def selecionar_produtos(categoria, qtd=5):
    """Pega N produtos da categoria que ainda nao foram enviados"""
    conn = get_conn()
    rows = conn.execute('''
        SELECT id, titulo, preco, vendas, comissao_pct, offer_link 
        FROM shopee_produtos 
        WHERE categoria=? AND enviado=0 
        ORDER BY RANDOM() LIMIT ?
    ''', (categoria, qtd)).fetchall()
    
    if len(rows) < qtd:
        # Reseta produtos ja enviados dessa categoria
        conn.execute('UPDATE shopee_produtos SET enviado=0 WHERE categoria=?', (categoria,))
        conn.commit()
        rows = conn.execute('''
            SELECT id, titulo, preco, vendas, comissao_pct, offer_link 
            FROM shopee_produtos 
            WHERE categoria=? 
            ORDER BY RANDOM() LIMIT ?
        ''', (categoria, qtd)).fetchall()
    
    conn.close()
    return rows

def montar_mensagens(categoria, produtos):
    """Monta lista de mensagens: 1 abertura + N produtos individuais"""
    emoji = EMOJI_CATEGORIA.get(categoria, '🛍️')
    mensagens = []
    
    
    # Uma mensagem por produto - SUPER ENXUTA para gerar preview
    for i, p in enumerate(produtos, 1):
        titulo = p[1][:60]
        preco = f"R$ {p[2]:.2f}".replace('.', ',')
        link = p[5]
        
        # Link primeiro, texto depois (formato que melhor gera preview)
        msg = f"{link}\n\n"
        msg += f"💰 *{preco}*\n"
        msg += f"📦 {titulo}"
        mensagens.append(msg)
    
    return mensagens

def marcar_enviados(produtos_ids, categoria, periodo):
    conn = get_conn()
    hoje = datetime.now().strftime('%Y-%m-%d')
    for pid in produtos_ids:
        conn.execute('UPDATE shopee_produtos SET enviado=1 WHERE id=?', (pid,))
    conn.execute('INSERT INTO shopee_sessoes_enviadas (categoria, data, periodo) VALUES (?,?,?)', 
                 (categoria, hoje, periodo))
    conn.commit()
    conn.close()

def enfileirar(texto, grupos):
    fila = []
    try:
        with open(QUEUE_F) as f:
            fila = json.load(f)
    except:
        pass
    fila.append({
        'id': f'shopee_sessao_{datetime.now().strftime("%Y%m%d%H%M%S")}',
        'texto': texto,
        'grupos': grupos,
    })
    with open(QUEUE_F, 'w') as f:
        json.dump(fila, f)

def enviar_sessao(periodo):
    cat = proxima_categoria(periodo)
    if not cat:
        log(f'Periodo {periodo}: nenhuma categoria configurada')
        return False
    
    produtos = selecionar_produtos(cat, PRODUTOS_POR_SESSAO)
    if not produtos:
        log(f'Sem produtos para {cat}')
        return False
    
    grupos = grupos_ativos()
    if not grupos:
        log('Nenhum grupo WhatsApp ativo')
        return False
    
    mensagens = montar_mensagens(cat, produtos)
    for msg in mensagens:
        enfileirar(msg, grupos)
    marcar_enviados([p[0] for p in produtos], cat, periodo)
    
    log(f'Sessao {cat}: {len(mensagens)} mensagens enfileiradas para {len(grupos)} grupos')
    return True

if __name__ == '__main__':
    # Teste: envia sessao do periodo atual
    hora = datetime.now().hour
    if 8 <= hora < 12:    periodo = 'manha'
    elif 12 <= hora < 18: periodo = 'tarde'
    elif 18 <= hora < 22: periodo = 'noite'
    else:                 periodo = None
    
    if periodo:
        enviar_sessao(periodo)
    else:
        log(f'Fora do horario (atual: {hora}h)')
