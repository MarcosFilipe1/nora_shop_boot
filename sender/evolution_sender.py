import os, sys, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from core.database import registrar_envio, ja_enviada_recentemente, get_conn
from core.cupons import processar_cupom
from core.formatter import formatar_whatsapp

EVOLUTION_URL     = 'http://localhost:8080'
EVOLUTION_API_KEY = '6A2E90B2-F9A8-46DD-B37F-E9A4EE239023'
INSTANCE_NAME     = 'nora2'

def grupos_ativos():
    try:
        conn = get_conn()
        rows = conn.execute('SELECT group_id FROM grupos_whatsapp WHERE ativo=1').fetchall()
        conn.close()
        return [r[0] for r in rows]
    except:
        return []

def enviar_texto(destino, texto):
    try:
        r = requests.post(
            f'{EVOLUTION_URL}/message/sendText/{INSTANCE_NAME}',
            headers={'apikey': EVOLUTION_API_KEY, 'Content-Type': 'application/json'},
            json={'number': destino, 'textMessage': {'text': texto}},
            timeout=15
        )
        data = r.json()
        if data.get('key'):
            print(f'[EVO] Enviado para {destino} ✅')
            return True
        print(f'[EVO] Erro: {data}')
        return False
    except Exception as e:
        print(f'[EVO] Erro: {e}')
        return False

def enviar_imagem(destino, imagem_url, legenda):
    try:
        r = requests.post(
            f'{EVOLUTION_URL}/message/sendMedia/{INSTANCE_NAME}',
            headers={'apikey': EVOLUTION_API_KEY, 'Content-Type': 'application/json'},
            json={'number': destino, 'mediaMessage': {
                'mediatype': 'image',
                'media': imagem_url,
                'caption': legenda,
            }},
            timeout=20
        )
        data = r.json()
        if data.get('key'):
            print(f'[EVO] Imagem enviada para {destino} ✅')
            return True
        print(f'[EVO] Erro imagem: {data}')
        return False
    except Exception as e:
        print(f'[EVO] Erro: {e}')
        return False

def enviar_oferta(oferta, cupom=None):
    if ja_enviada_recentemente(oferta.get('url', ''), horas=12):
        print(f'[EVO] Ja enviada: {oferta.get("titulo","")[:40]}')
        return False
    url_final, texto_cupom = processar_cupom(
        oferta.get('url_afiliado') or oferta.get('url', ''),
        oferta.get('loja', ''), cupom
    )
    oferta['url_afiliado'] = url_final
    texto  = formatar_whatsapp(oferta, texto_cupom)
    imagem = oferta.get('imagem_url')
    destinos = grupos_ativos()
    if not destinos:
        print('[EVO] Nenhum grupo ativo')
        return False
    enviadas = 0
    for destino in destinos:
        ok = enviar_imagem(destino, imagem, texto) if imagem else False
        if not ok:
            ok = enviar_texto(destino, texto)
        if ok:
            enviadas += 1
            hid = oferta.get('historico_id')
            if hid:
                registrar_envio(hid, 'whatsapp', destino)
    return enviadas > 0

def testar_conexao():
    destinos = grupos_ativos()
    if not destinos:
        print('[EVO] Nenhum grupo ativo')
        return False
    ok = True
    for destino in destinos:
        r = enviar_texto(destino, 'Nora Shop Bot - Teste de conexao OK!')
        if not r:
            ok = False
    return ok
