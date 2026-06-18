"""
sender/painel.py — Painel web premium do Bot Nora Shop
Acesse em: http://localhost:5001

Rodar: python sender/painel.py
       python main.py --painel
"""

import sys, os, json, platform, sqlite3
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, render_template, request, jsonify, redirect, url_for, Response
from core.database import (
    get_conn, init_db, salvar_cupom, listar_cupons_ativos,
    salvar_oferta_manual, listar_keywords_ativas, listar_produtos_ativos
)
from core.afiliados import gerar_link_afiliado
from core.cupons import processar_cupom
from core.formatter import formatar_whatsapp

_HERE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
    template_folder=os.path.join(_HERE, 'templates'),
    static_folder=os.path.join(_HERE, 'static'))

# ── Configuração padrão (editável pelo painel) ──────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'config.json')

DEFAULT_CONFIG = {
    'intervalo_scraping': 30,
    'max_envios_hora':    10,
    'desconto_minimo':    15,
    'cooldown_horas':     12,
    'ig_token':           '',
    'ig_user_id':         '',
    'ig_auto':            0,
    'afiliados': {
        'mercadolivre': '',
        'amazon':       '',
        'shopee':       '',
        'aliexpress':   '',
        'magazineluiza':'',
    }
}

LOJAS = [
    {'id': 'mercadolivre', 'nome': 'Mercado Livre', 'icon': '🟡', 'badge': 'badge-amber',
     'placeholder': 'ID numérico do painel ML'},
    {'id': 'amazon',       'nome': 'Amazon',        'icon': '📦', 'badge': 'badge-amber',
     'placeholder': 'Ex: seutag-20'},
    {'id': 'shopee',       'nome': 'Shopee',        'icon': '🧡', 'badge': 'badge-amber',
     'placeholder': 'af_siteid value'},
    {'id': 'aliexpress',   'nome': 'AliExpress',    'icon': '🔴', 'badge': 'badge-red',
     'placeholder': 'aff_fcid value'},
    {'id': 'magazineluiza','nome': 'Magalu',        'icon': '💙', 'badge': 'badge-blue',
     'placeholder': 'ID Parceiros Magalu'},
]


def load_config():
    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
            # merge com defaults para campos novos
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
    except Exception:
        return DEFAULT_CONFIG.copy()

def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def get_status():
    """Status de conexão dos canais."""
    wa_online = False
    wa_numero = None
    try:
        # Tenta ler arquivo de status gerado pelo Node.js
        status_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'wa_status.json')
        with open(status_path) as f:
            d = json.load(f)
            wa_online = d.get('online', False)
            wa_numero = d.get('numero')
    except Exception:
        pass

    cfg = load_config()
    ig_ok = bool(cfg.get('ig_token') and cfg.get('ig_user_id'))

    conn = get_conn()
    grupos_ativos = conn.execute(
        "SELECT COUNT(*) FROM grupos_whatsapp WHERE ativo=1"
    ).fetchone()[0] if table_exists(conn, 'grupos_whatsapp') else 0
    wa_hoje = conn.execute(
        "SELECT COUNT(*) FROM ofertas_enviadas WHERE canal='whatsapp' AND date(enviado_em)=date('now')"
    ).fetchone()[0] if table_exists(conn, 'ofertas_enviadas') else 0
    ig_hoje = conn.execute(
        "SELECT COUNT(*) FROM ofertas_enviadas WHERE canal='instagram' AND date(enviado_em)=date('now')"
    ).fetchone()[0] if table_exists(conn, 'ofertas_enviadas') else 0
    conn.close()

    return {
        'whatsapp':        wa_online,
        'wa_numero':       wa_numero,
        'grupos_ativos':   grupos_ativos,
        'wa_enviados_hoje':wa_hoje,
        'instagram':       ig_ok,
        'ig_username':     '@noraShop' if ig_ok else None,
        'ig_token_ok':     ig_ok,
        'ig_posts_hoje':   ig_hoje,
    }

def table_exists(conn, name):
    return conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()[0] > 0

def get_stats():
    conn = get_conn()
    hoje = datetime.now().strftime('%Y-%m-%d')
    semana = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

    enviadas_hoje  = conn.execute("SELECT COUNT(*) FROM ofertas_enviadas WHERE date(enviado_em)=?", (hoje,)).fetchone()[0] if table_exists(conn,'ofertas_enviadas') else 0
    enviadas_semana= conn.execute("SELECT COUNT(*) FROM ofertas_enviadas WHERE date(enviado_em)>=?", (semana,)).fetchone()[0] if table_exists(conn,'ofertas_enviadas') else 0
    total_ofertas  = conn.execute("SELECT COUNT(*) FROM historico_precos").fetchone()[0] if table_exists(conn,'historico_precos') else 0
    total_keywords = conn.execute("SELECT COUNT(*) FROM keywords WHERE ativo=1").fetchone()[0] if table_exists(conn,'keywords') else 0
    grupos_ativos  = conn.execute("SELECT COUNT(*) FROM grupos_whatsapp WHERE ativo=1").fetchone()[0] if table_exists(conn,'grupos_whatsapp') else 0
    total_grupos   = conn.execute("SELECT COUNT(*) FROM grupos_whatsapp").fetchone()[0] if table_exists(conn,'grupos_whatsapp') else 0
    cupons_ativos  = conn.execute("SELECT COUNT(*) FROM cupons WHERE ativo=1").fetchone()[0] if table_exists(conn,'cupons') else 0

    validade_limite = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
    cupons_expirando = conn.execute(
        "SELECT COUNT(*) FROM cupons WHERE ativo=1 AND valido_ate IS NOT NULL AND valido_ate<=?",
        (validade_limite,)
    ).fetchone()[0] if table_exists(conn,'cupons') else 0
    conn.close()

    return dict(enviadas_hoje=enviadas_hoje, enviadas_semana=enviadas_semana,
                total_ofertas=total_ofertas, total_keywords=total_keywords,
                grupos_ativos=grupos_ativos, total_grupos=total_grupos,
                cupons_ativos=cupons_ativos, cupons_expirando=cupons_expirando)

def get_chart_data():
    conn = get_conn()
    dias = []
    maximo = 1
    for i in range(6, -1, -1):
        d = (datetime.now() - timedelta(days=i))
        label = d.strftime('%a')[:3]
        data  = d.strftime('%Y-%m-%d')
        total = conn.execute(
            "SELECT COUNT(*) FROM ofertas_enviadas WHERE date(enviado_em)=?", (data,)
        ).fetchone()[0] if table_exists(conn, 'ofertas_enviadas') else 0
        dias.append({'dia': label, 'total': total})
        if total > maximo:
            maximo = total
    conn.close()
    for d in dias:
        d['pct'] = round(d['total'] / maximo * 100)
    return dias

def get_atividade_recente():
    conn = get_conn()
    if not table_exists(conn, 'ofertas_enviadas'):
        conn.close()
        return []
    rows = conn.execute("""
        SELECT oe.canal, hp.titulo, hp.loja, oe.status, oe.enviado_em
        FROM ofertas_enviadas oe
        JOIN historico_precos hp ON hp.id = oe.historico_id
        ORDER BY oe.enviado_em DESC LIMIT 8
    """).fetchall() if table_exists(conn, 'historico_precos') else []
    conn.close()
    result = []
    icons = {'whatsapp':'💬','instagram':'📸'}
    for r in rows:
        ts = r[4][:16] if r[4] else ''
        result.append({'icon': icons.get(r[0],'📤'), 'titulo': r[1][:50],
                       'loja': r[2], 'tempo': ts})
    return result


# ── ROTAS PRINCIPAIS ──────────────────────────────────────────────────────────

@app.route('/')
def dashboard():
    init_db(); _ensure_tables()
    return render_template('dashboard.html',
        status=get_status(),
        stats=get_stats(),
        chart_data=get_chart_data(),
        atividade=get_atividade_recente(),
        lojas_status=[
            {'nome':'Mercado Livre','icon':'🟡','status':'Ativo','badge':'badge-green','ultima':'agora'},
            {'nome':'Magalu',       'icon':'💙','status':'Ativo','badge':'badge-green','ultima':'agora'},
            {'nome':'Amazon',       'icon':'📦','status':'Em breve','badge':'badge-gray','ultima':'—'},
            {'nome':'Shopee',       'icon':'🧡','status':'Em breve','badge':'badge-gray','ultima':'—'},
            {'nome':'AliExpress',   'icon':'🔴','status':'Em breve','badge':'badge-gray','ultima':'—'},
        ]
    )

@app.route('/cupons')
def cupons():
    _ensure_tables()
    conn = get_conn()
    rows = conn.execute("SELECT * FROM cupons WHERE ativo=1 ORDER BY criado_em DESC").fetchall() if table_exists(conn,'cupons') else []
    conn.close()

    badges = {'mercadolivre':'badge-amber','amazon':'badge-amber','shopee':'badge-amber',
              'aliexpress':'badge-red','magazineluiza':'badge-blue'}
    icons  = {'mercadolivre':'🟡','amazon':'📦','shopee':'🧡','aliexpress':'🔴','magazineluiza':'💙'}
    hoje = datetime.now().strftime('%Y-%m-%d')
    limite = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')

    cupons_fmt = []
    for r in rows:
        d = dict(r)
        d['badge']     = badges.get(d['loja'], 'badge-gray')
        d['icon']      = icons.get(d['loja'], '🏷️')
        d['expirado']  = bool(d.get('valido_ate') and d['valido_ate'] < hoje)
        d['expirando'] = bool(d.get('valido_ate') and hoje <= d['valido_ate'] <= limite)
        cupons_fmt.append(d)

    return render_template('cupons.html', status=get_status(), cupons=cupons_fmt, lojas=LOJAS)

@app.route('/grupos')
def grupos():
    _ensure_tables()
    conn = get_conn()
    rows = conn.execute("SELECT * FROM grupos_whatsapp ORDER BY nome").fetchall() if table_exists(conn,'grupos_whatsapp') else []
    conn.close()
    grupos_list = [dict(r) for r in rows]
    return render_template('grupos.html', status=get_status(), grupos=grupos_list)

@app.route('/redes-sociais')
def redes_sociais():
    _ensure_tables()
    conn = get_conn()
    envios = []
    if table_exists(conn,'ofertas_enviadas') and table_exists(conn,'historico_precos'):
        rows = conn.execute("""
            SELECT oe.canal, oe.destino, hp.titulo, oe.status, oe.enviado_em
            FROM ofertas_enviadas oe
            JOIN historico_precos hp ON hp.id=oe.historico_id
            ORDER BY oe.enviado_em DESC LIMIT 20
        """).fetchall()
        envios = [dict(zip(['canal','destino','titulo','status','enviado_em'],r)) for r in rows]
    conn.close()
    return render_template('redes_sociais.html', status=get_status(), ultimos_envios=envios)

@app.route('/logs')
def logs():
    _ensure_tables()
    log_file = os.path.join(os.path.dirname(__file__), '..', 'logs', 'bot.log')
    entries = []
    try:
        with open(log_file) as f:
            for line in f.readlines()[-200:]:
                line = line.strip()
                if not line: continue
                nivel = 'INFO'
                for n in ['ERROR','WARNING','SUCCESS','INFO']:
                    if n in line: nivel = n; break
                parts = line.split(' ', 2)
                entries.append({'time': ' '.join(parts[:2]) if len(parts)>1 else '',
                                'nivel': nivel, 'msg': parts[-1]})
    except Exception:
        entries = [{'time': datetime.now().strftime('%H:%M:%S'), 'nivel':'INFO',
                    'msg':'Arquivo de log não encontrado. Rode o bot para gerar logs.'}]
    return render_template('logs.html', status=get_status(), logs=list(reversed(entries)))

@app.route('/configuracoes')
def configuracoes():
    cfg = load_config()
    db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'ofertas.db')
    try:
        cfg['db_size'] = f"{os.path.getsize(db_path)/1024:.0f} KB"
    except Exception:
        cfg['db_size'] = '—'
    cfg['uptime'] = '—'
    cfg['python_version'] = platform.python_version()
    return render_template('configuracoes.html', status=get_status(), cfg=cfg, lojas=LOJAS)


# ── ROTAS API ─────────────────────────────────────────────────────────────────

@app.route('/api/cupom', methods=['POST'])
def api_cupom():
    try:
        dados = request.get_json()
        dados.setdefault('descricao', '')
        dados.setdefault('desconto_tipo', 'percentual')
        dados.setdefault('desconto_valor', None)
        dados.setdefault('preco_minimo', None)
        dados.setdefault('valido_ate', None)
        dados.setdefault('url_produto', None)
        dados.setdefault('aplicar_no_link', 0)
        id_ = salvar_cupom(dados)
        return jsonify({'ok': True, 'id': id_})
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)}), 400

@app.route('/api/cupom/<int:id>/desativar', methods=['POST'])
def api_cupom_desativar(id):
    try:
        conn = get_conn()
        conn.execute("UPDATE cupons SET ativo=0 WHERE id=?", (id,))
        conn.commit(); conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)}), 400

@app.route('/grupos/toggle', methods=['POST'])
def grupos_toggle():
    try:
        d = request.get_json()
        conn = get_conn()
        conn.execute("UPDATE grupos_whatsapp SET ativo=? WHERE group_id=?",
                     (1 if d.get('ativo') else 0, d['group_id']))
        conn.commit(); conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)}), 400

@app.route('/grupos/refresh', methods=['POST'])
def grupos_refresh():
    # Lê arquivo gerado pelo Node.js com lista de grupos
    try:
        grupos_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'wa_groups.json')
        with open(grupos_path) as f:
            grupos = json.load(f)
        conn = get_conn()
        for g in grupos:
            conn.execute("""
                INSERT INTO grupos_whatsapp (group_id, nome, participantes, ultima_atualizacao)
                VALUES (?,?,?,datetime('now'))
                ON CONFLICT(group_id) DO UPDATE SET
                    nome=excluded.nome,
                    participantes=excluded.participantes,
                    ultima_atualizacao=datetime('now')
            """, (g['id'], g['name'], g.get('participants', 0)))
        conn.commit(); conn.close()
        return jsonify({'ok': True, 'total': len(grupos)})
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)}), 400

@app.route('/api/stats')
def api_stats():
    return jsonify(get_stats())

@app.route('/api/logs')
def api_logs():
    limit = int(request.args.get('limit', 50))
    log_file = os.path.join(os.path.dirname(__file__), '..', 'logs', 'bot.log')
    entries = []
    try:
        with open(log_file) as f:
            for line in f.readlines()[-limit:]:
                line = line.strip()
                if not line: continue
                nivel = 'INFO'
                for n in ['ERROR','WARNING','SUCCESS','INFO']:
                    if n in line: nivel = n; break
                parts = line.split(' ', 2)
                entries.append({'time': ' '.join(parts[:2]) if len(parts)>1 else '',
                                'nivel': nivel, 'msg': parts[-1]})
    except Exception:
        pass
    return jsonify({'logs': entries})

@app.route('/api/wa-status')
def api_wa_status():
    try:
        with open(os.path.join(os.path.dirname(__file__), '..', 'data', 'wa_status.json')) as f:
            return jsonify(json.load(f))
    except Exception:
        return jsonify({'online': False})

@app.route('/api/rodar-bot', methods=['POST'])
def api_rodar_bot():
    try:
        import subprocess
        main_path = os.path.join(os.path.dirname(__file__), '..', 'main.py')
        subprocess.Popen([sys.executable, main_path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return jsonify({'ok': True, 'encontradas': '?'})
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)})

@app.route('/api/teste-whatsapp', methods=['POST'])
def api_teste_wa():
    return jsonify({'ok': False, 'erro': 'whatsapp-web.js não configurado ainda'})

@app.route('/api/teste-instagram', methods=['POST'])
def api_teste_ig():
    return jsonify({'ok': False, 'erro': 'Instagram não configurado ainda'})

@app.route('/api/limpar-historico', methods=['POST'])
def api_limpar():
    try:
        conn = get_conn()
        limite = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        r = conn.execute("DELETE FROM historico_precos WHERE date(coletado_em)<?", (limite,))
        conn.commit(); conn.close()
        return jsonify({'ok': True, 'removidos': r.rowcount})
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)})

@app.route('/configuracoes/salvar', methods=['POST'])
def configuracoes_salvar():
    try:
        d = request.get_json()
        cfg = load_config()
        cfg.update(d)
        # Atualizar afiliados no arquivo Python
        _atualizar_afiliados(d.get('afiliados', {}))
        save_config(cfg)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)})

def _atualizar_afiliados(afiliados: dict):
    """Reescreve os IDs de afiliado no afiliados.py automaticamente."""
    aff_path = os.path.join(os.path.dirname(__file__), '..', 'core', 'afiliados.py')
    try:
        with open(aff_path) as f:
            content = f.read()
        mapa = {
            'mercadolivre': 'ML_ID',
            'amazon':        'AMAZON_TAG',
            'shopee':        'SHOPEE_ID',
            'aliexpress':    'ALIEXPRESS_ID',
            'magazineluiza': 'MAGALU_ID',
        }
        import re
        for loja, var in mapa.items():
            valor = afiliados.get(loja, '')
            content = re.sub(
                rf"({var}\s*=\s*)'[^']*'",
                rf"\1'{valor}'",
                content
            )
        with open(aff_path, 'w') as f:
            f.write(content)
    except Exception:
        pass  # Falha silenciosa — salva só no JSON


def _ensure_tables():
    """Garante que todas as tabelas existam."""
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
    conn.commit(); conn.close()
    os.makedirs(os.path.join(os.path.dirname(__file__), '..', 'logs'), exist_ok=True)


if __name__ == '__main__':
    init_db()
    _ensure_tables()
    print("\n🛍️  Nora Shop — Painel iniciado")
    print("   Acesse: http://localhost:5001\n")
    app.run(host='0.0.0.0', port=5001, debug=False)

@app.route('/ofertas')
def ofertas():
    _ensure_tables()
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM historico_precos
        ORDER BY coletado_em DESC LIMIT 100
    """).fetchall() if table_exists(conn,'historico_precos') else []
    conn.close()
    ofertas = [dict(r) for r in rows]
    return render_template('ofertas.html', status=get_status(), ofertas=ofertas)

@app.route('/keywords')
def keywords():
    _ensure_tables()
    conn = get_conn()
    rows = conn.execute("SELECT * FROM keywords ORDER BY loja, termo").fetchall() if table_exists(conn,'keywords') else []
    conn.close()
    kws = [dict(r) for r in rows]
    return render_template('keywords.html', status=get_status(), keywords=kws, lojas=LOJAS)

@app.route('/produtos')
def produtos():
    _ensure_tables()
    conn = get_conn()
    rows = conn.execute("SELECT * FROM produtos ORDER BY loja, nome").fetchall() if table_exists(conn,'produtos') else []
    conn.close()
    prods = [dict(r) for r in rows]
    return render_template('produtos.html', status=get_status(), produtos=prods, lojas=LOJAS)

@app.route('/api/keyword', methods=['POST'])
def api_keyword():
    try:
        d = request.get_json()
        conn = get_conn()
        conn.execute("""INSERT INTO keywords (termo, loja, desconto_minimo, preco_maximo)
            VALUES (?,?,?,?)""", (d['termo'], d['loja'], d.get('desconto_minimo',15), d.get('preco_maximo')))
        conn.commit(); conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)}), 400

@app.route('/api/keyword/<int:id>/desativar', methods=['POST'])
def api_keyword_desativar(id):
    try:
        conn = get_conn()
        conn.execute("UPDATE keywords SET ativo=0 WHERE id=?", (id,))
        conn.commit(); conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)}), 400

@app.route('/api/produto', methods=['POST'])
def api_produto():
    try:
        d = request.get_json()
        conn = get_conn()
        conn.execute("""INSERT INTO produtos (nome, url, loja, preco_alvo, desconto_minimo)
            VALUES (?,?,?,?,?)""", (d['nome'], d['url'], d['loja'], d.get('preco_alvo'), d.get('desconto_minimo',15)))
        conn.commit(); conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)}), 400

TEMPLATE_PADRAO = """🔥 *OFERTA {loja}*

📦 {titulo}

{preco_original}💰 *Por: {preco}*
🏷️ {desconto} OFF
{cupom}

👉 {link}

_⚡ Oferta por tempo limitado!_"""

def _template_path():
    return os.path.join(os.path.dirname(__file__), '..', 'data', 'template.txt')

def _carregar_template():
    try:
        with open(_template_path()) as f:
            return f.read()
    except:
        return TEMPLATE_PADRAO

@app.route('/template')
def template_editor():
    _ensure_tables()
    return render_template('template_editor.html', status=get_status(), template=_carregar_template())

@app.route('/api/template/salvar', methods=['POST'])
def api_template_salvar():
    try:
        d = request.get_json()
        with open(_template_path(), 'w') as f:
            f.write(d['template'])
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)}), 400

@app.route('/api/template/reset', methods=['POST'])
def api_template_reset():
    try:
        with open(_template_path(), 'w') as f:
            f.write(TEMPLATE_PADRAO)
        return jsonify({'ok': True, 'template': TEMPLATE_PADRAO})
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)}), 400
