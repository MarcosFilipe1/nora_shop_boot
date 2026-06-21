"""
Gerador de links de afiliado do Mercado Livre via API interna
Usa cookies de sessao do navegador logado em /afiliados
"""
import requests, re, json, os

ML_COOKIES_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'ml_cookies.txt')
ML_TAG = 'norashop'

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/149.0.0.0 Safari/537.36'

def carregar_cookies():
    try:
        with open(ML_COOKIES_FILE) as f:
            return f.read().strip()
    except:
        return None

def salvar_cookies(cookies_str):
    os.makedirs(os.path.dirname(ML_COOKIES_FILE), exist_ok=True)
    with open(ML_COOKIES_FILE, 'w') as f:
        f.write(cookies_str.strip())

def gerar_link_afiliado_ml(url_produto, tag=ML_TAG):
    """
    Gera link de afiliado do ML usando a API interna do linkbuilder.
    Retorna dict com short_url, long_url, id, ou None se falhar.
    """
    cookies = carregar_cookies()
    if not cookies:
        print("[ML_API] Cookies nao configurados")
        return None

    try:
        s = requests.Session()
        headers_base = {
            'User-Agent': USER_AGENT,
            'Accept-Language': 'pt-BR,pt;q=0.9',
            'Cookie': cookies,
        }
        
        # 1. GET na pagina do linkbuilder para pegar CSRF token
        r = s.get(
            'https://www.mercadolivre.com.br/afiliados/linkbuilder',
            headers=headers_base, timeout=15
        )
        if r.status_code != 200:
            print(f"[ML_API] GET linkbuilder falhou: {r.status_code}")
            return None

        csrf = None
        for pat in [r'"csrfToken"\s*:\s*"([^"]+)"', r'csrf[_-]token["\s:]+["\']([^"\']+)']:
            m = re.search(pat, r.text, re.I)
            if m:
                csrf = m.group(1)
                break

        if not csrf:
            print("[ML_API] CSRF nao encontrado - cookies expirados?")
            return None

        # 2. POST na API
        cookies_session = '; '.join([f'{c.name}={c.value}' for c in s.cookies])
        cookie_final = cookies + ('; ' + cookies_session if cookies_session else '')

        headers_api = {
            'User-Agent': USER_AGENT,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'pt-BR,pt;q=0.9',
            'Content-Type': 'application/json',
            'Origin': 'https://www.mercadolivre.com.br',
            'Referer': 'https://www.mercadolivre.com.br/afiliados/linkbuilder',
            'Cookie': cookie_final,
            'x-csrf-token': csrf,
        }
        payload = {'urls': [url_produto], 'tag': tag}

        resp = s.post(
            'https://www.mercadolivre.com.br/affiliate-program/api/v2/affiliates/createLink',
            json=payload, headers=headers_api, timeout=15
        )

        if resp.status_code != 200:
            return None

        data = resp.json()
        if data.get('urls') and data['urls'][0].get('created'):
            return {
                'short_url': data['urls'][0]['short_url'],
                'long_url': data['urls'][0]['long_url'],
                'id': data['urls'][0]['id'],
                'tag': tag,
            }
        else:
            erro = data['urls'][0].get('message', 'desconhecido') if data.get('urls') else 'sem resposta'
            print(f"[ML_API] URL nao habilitada: {erro}")
            return None

    except Exception as e:
        print(f"[ML_API] Erro: {e}")
        return None

if __name__ == '__main__':
    # Teste
    url = 'https://produto.mercadolivre.com.br/MLB-3950434672-colcho-casal-luuna-blue-espuma-21-cm-com-bloqueio-de-movimento-10-anos-de-garantia-_JM'
    r = gerar_link_afiliado_ml(url)
    print(json.dumps(r, indent=2) if r else "Falhou")
