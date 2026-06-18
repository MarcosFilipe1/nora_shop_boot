import asyncio, re, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from playwright.async_api import async_playwright
from core.database import salvar_preco
from core.afiliados import gerar_link_afiliado

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

def _preco(t):
    if not t: return None
    m = re.search(r'R\$\s*([\d.,]+)', t)
    if not m: return None
    n = m.group(1).replace('.','').replace(',','.')
    try: return float(n)
    except: return None

def detectar_loja(url):
    url = url.lower()
    if 'amazon' in url: return 'amazon'
    if 'mercadolivre' in url or 'mercadolibre' in url: return 'mercadolivre'
    if 'shopee' in url: return 'shopee'
    if 'magazineluiza' in url or 'magazinevoce' in url: return 'magazineluiza'
    if 'aliexpress' in url: return 'aliexpress'
    return None

def limpar_tag_promobit(url):
    # Remove tags de afiliado do promobit
    url = re.sub(r'[?&]tag=promobit[^&]*', '', url)
    url = re.sub(r'[?&]af_siteid=[^&]*', '', url)
    return url

async def coletar(max_ofertas=30, desconto_minimo=10):
    resultados = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=UA, locale="pt-BR")
        page = await context.new_page()

        print("[PROMOBIT] Coletando ofertas...")
        try:
            await page.goto("https://www.promobit.com.br/", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            links = await page.query_selector_all('a[href*="/oferta/"]')
            ofertas_raw = []
            for link in links[:max_ofertas]:
                try:
                    href = await link.get_attribute("href")
                    texto = await link.inner_text()
                    linhas = [l.strip() for l in texto.strip().split("\n") if l.strip()]
                    loja_txt = linhas[0] if linhas else ""
                    # Titulo = linha mais longa que nao seja selo/preco
                    selos = ['frete gratis', 'frete grátis', 'parcelado', 'cupom', 'oferta', 'menor preço', 'em até']
                    candidatos = [l for l in linhas[1:] if len(l) > 20 and not any(s in l.lower() for s in selos) and 'R$' not in l]
                    titulo = max(candidatos, key=len) if candidatos else (linhas[1] if len(linhas) > 1 else "")
                    preco = _preco(texto)
                    img = await link.query_selector("img")
                    imagem = await img.get_attribute("src") if img else None
                    # Extrai ID da oferta da URL
                    id_match = re.search(r'-(\d+)/?$', href)
                    oferta_id = id_match.group(1) if id_match else None
                    if titulo and oferta_id:
                        ofertas_raw.append({
                            'titulo': titulo, 'preco': preco, 'imagem': imagem,
                            'oferta_id': oferta_id, 'loja_txt': loja_txt,
                        })
                except: continue

            print(f"[PROMOBIT] {len(ofertas_raw)} ofertas encontradas, buscando links reais...")

            # Para cada oferta, segue o redirect para pegar URL real
            for o in ofertas_raw:
                try:
                    redirect_url = f"https://www.promobit.com.br/Redirect/to/{o['oferta_id']}/"
                    await page.goto(redirect_url, wait_until="domcontentloaded", timeout=20000)
                    await page.wait_for_timeout(2500)
                    url_real = page.url

                    if 'promobit.com.br' in url_real:
                        continue  # Nao redirecionou

                    loja = detectar_loja(url_real)
                    if not loja:
                        continue

                    # Magalu: so aceita produto individual (/p/), nao selecao/campanha
                    if loja == 'magazineluiza' and '/p/' not in url_real:
                        continue
                    # Descarta paginas que nao sao produto individual
                    lixo_url = ['/selecao/', '/promocoes-do-ano/', '/social/', '/lists', '/m/cupom', '/cupom-de-desconto', '/loja/', '/promocoes/']
                    if any(x in url_real for x in lixo_url):
                        continue
                    # ML so aceita produto (/MLB ou /p/)
                    if loja == 'mercadolivre' and not re.search(r'(MLB-?\d|/p/)', url_real):
                        continue
                    # Shopee so aceita produto (-i.)
                    if loja == 'shopee' and '-i.' not in url_real:
                        continue

                    url_limpa = limpar_tag_promobit(url_real)
                    url_afiliado = gerar_link_afiliado(url_limpa, loja)

                    oferta = {
                        'produto_id': None, 'keyword_id': None, 'loja': loja,
                        'titulo': o['titulo'], 'url': url_limpa, 'url_afiliado': url_afiliado,
                        'preco_atual': o['preco'], 'preco_original': None,
                        'desconto_pct': None, 'imagem_url': o['imagem'],
                    }
                    resultados.append(oferta)
                    print(f"  [{loja}] {o['titulo'][:45]} — R$ {o['preco']}")
                except Exception as e:
                    continue

        except Exception as e:
            print(f"[PROMOBIT] Erro: {e}")
        finally:
            await browser.close()

    return resultados

async def executar(keywords=None, produtos=None):
    ofertas = await coletar(max_ofertas=30)
    for o in ofertas:
        hid = salvar_preco(o)
        o['historico_id'] = hid
    return ofertas
