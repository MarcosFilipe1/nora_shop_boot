"""
Gerador de links curtos de afiliado da Amazon via SiteStripe API
Usa cookies de sessao do navegador logado em amazon.com.br
"""
import requests, re, os, urllib.parse

AMZ_COOKIES_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'amazon_cookies.txt')
AMZ_TAG = 'norashop06-20'
AMZ_MARKETPLACE = '526970'  # Amazon Brasil

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/149.0.0.0 Safari/537.36'

def carregar_cookies():
    try:
        with open(AMZ_COOKIES_FILE) as f:
            return f.read().strip()
    except:
        return None

def gerar_link_afiliado_amazon(url_produto):
    """
    Gera link curto Amazon (amzn.to/xxx) via SiteStripe API.
    Recebe URL completa do produto, retorna URL curta ou None.
    """
    cookies = carregar_cookies()
    if not cookies:
        print('[AMZ_API] Cookies nao configurados')
        return None

    try:
        # Adiciona parametros de afiliado na URL longa antes de chamar a API
        if 'tag=' not in url_produto:
            sep = '&' if '?' in url_produto else '?'
            url_produto = f'{url_produto}{sep}linkCode=ll2&tag={AMZ_TAG}&linkId=&ref_=as_li_ss_tl'

        # URL-encode para passar como parametro
        long_url_encoded = urllib.parse.quote(url_produto, safe='')

        api_url = (
            f'https://www.amazon.com.br/associates/sitestripe/getShortUrl'
            f'?longUrl={long_url_encoded}'
            f'&marketplaceId={AMZ_MARKETPLACE}'
            f'&storeId={AMZ_TAG}'
        )

        headers = {
            'User-Agent': USER_AGENT,
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'pt-BR,pt;q=0.9',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': url_produto,
            'Cookie': cookies,
        }

        r = requests.get(api_url, headers=headers, timeout=15)
        if r.status_code != 200:
            print(f'[AMZ_API] Status {r.status_code}: {r.text[:200]}')
            return None

        data = r.json()
        # Resposta pode ter campos como 'shortUrl' ou similar
        short_url = data.get('shortUrl') or data.get('short_url') or data.get('url')

        if short_url:
            return {'short_url': short_url, 'long_url': url_produto, 'tag': AMZ_TAG}

        print(f'[AMZ_API] Resposta inesperada: {data}')
        return None

    except Exception as e:
        print(f'[AMZ_API] Erro: {e}')
        return None

if __name__ == '__main__':
    # Teste
    url = 'https://www.amazon.com.br/Headphone-Ouvido-HV-H2002d-Microfone-Falante/dp/B07Y2G7VX5'
    r = gerar_link_afiliado_amazon(url)
    import json
    print(json.dumps(r, indent=2) if r else 'Falhou')
