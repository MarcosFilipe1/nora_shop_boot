import os, sys, json
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from core.database import registrar_envio, ja_enviada_recentemente, get_conn
from core.cupons import processar_cupom
from core.formatter import formatar_whatsapp

ROOT    = os.path.join(os.path.dirname(__file__), '..')
QUEUE_F = os.path.join(ROOT, 'data', 'wa_queue.json')

def grupos_ativos():
    try:
        conn = get_conn()
        rows = conn.execute('SELECT group_id FROM grupos_whatsapp WHERE ativo=1').fetchall()
        conn.close()
        return [r[0] for r in rows]
    except:
        return []

def enfileirar(texto, grupos, imagem=None):
    fila = []
    try:
        with open(QUEUE_F) as f:
            fila = json.load(f)
    except:
        pass
    item = {
        'id': f"oferta_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        'texto': texto,
        'grupos': grupos,
    }
    if imagem:
        item['imagem'] = imagem
    fila.append(item)
    with open(QUEUE_F, 'w') as f:
        json.dump(fila, f)
    return True

def enviar_oferta(oferta, cupom=None):
    if ja_enviada_recentemente(oferta.get('url', ''), horas=12, canal='whatsapp'):
        print(f'[WA] Ja enviada: {oferta.get("titulo","")[:40]}')
        return False
    url_final, texto_cupom = processar_cupom(
        oferta.get('url_afiliado') or oferta.get('url', ''),
        oferta.get('loja', ''), cupom
    )
    oferta['url_afiliado'] = url_final
    texto = formatar_whatsapp(oferta, texto_cupom)
    imagem = oferta.get('imagem_url')
    destinos = grupos_ativos()
    if not destinos:
        print('[WA] Nenhum grupo ativo')
        return False
    ok = enfileirar(texto, destinos, imagem)
    if ok:
        print(f'[WA] Enfileirado: {oferta.get("titulo","")[:50]}')
        hid = oferta.get('historico_id')
        if hid:
            for gid in destinos:
                registrar_envio(hid, 'whatsapp', gid)
    return ok
