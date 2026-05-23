import re

ML_ID          = ''
AMAZON_TAG     = 'norashop0d-20'
SHOPEE_ID      = ''
ALIEXPRESS_ID  = ''
MAGALU_ID      = ''

def gerar_link_mercadolivre(url):
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
