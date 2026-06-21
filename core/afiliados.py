import re

ML_ID          = '71631488'
AMAZON_TAG     = 'norashop06-20'
SHOPEE_ID      = '18357991071'
ALIEXPRESS_ID  = ''
MAGALU_ID      = 'norashop'

def gerar_link_mercadolivre(url):
    # Tenta API oficial do linkbuilder (gera meli.la com tag norashop)
    try:
        from core.ml_api import gerar_link_afiliado_ml
        r = gerar_link_afiliado_ml(url)
        if r and r.get('short_url'):
            return r['short_url']
    except Exception as e:
        print(f'[ML] API falhou, usando fallback: {e}')
    # Fallback: parametros manuais
    if not ML_ID: return url
    sep = '&' if '?' in url else '?'
    return f"{url}{sep}matt_tool=affiliates&matt_word={ML_ID}"

def gerar_link_amazon(url):
    if not AMAZON_TAG: return url
    asin = re.search(r'/dp/([A-Z0-9]{10})', url)
    if asin: return f"https://www.amazon.com.br/dp/{asin.group(1)}?tag={AMAZON_TAG}"
    sep = '&' if '?' in url else '?'
    return f"{url}{sep}tag={AMAZON_TAG}"

def gerar_link_shopee(url):
    if not SHOPEE_ID: return url
    sep = '&' if '?' in url else '?'
    return f"{url}{sep}af_siteid={SHOPEE_ID}"

def gerar_link_aliexpress(url):
    if not ALIEXPRESS_ID: return url
    sep = '&' if '?' in url else '?'
    return f"{url}{sep}aff_fcid={ALIEXPRESS_ID}&aff_platform=portals-tool"

def gerar_link_magazineluiza(url):
    if not MAGALU_ID: return url
    match = re.search(r'magazineluiza\.com\.br(.+)', url)
    if match: return f"https://www.magazinevoce.com.br/magazine{MAGALU_ID}{match.group(1)}"
    return url

_GERADORES = {
    'mercadolivre': gerar_link_mercadolivre,
    'amazon':       gerar_link_amazon,
    'shopee':       gerar_link_shopee,
    'aliexpress':   gerar_link_aliexpress,
    'magazineluiza':gerar_link_magazineluiza,
}

def gerar_link_afiliado(url, loja):
    fn = _GERADORES.get(loja)
    return fn(url) if fn else url
