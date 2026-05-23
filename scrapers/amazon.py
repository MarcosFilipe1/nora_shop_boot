
import asyncio, re, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from playwright.async_api import async_playwright
from core.database import salvar_preco
from core.afiliados import gerar_link_afiliado

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

def _preco(t):
    if not t: return None
    n = re.sub(r"[^\d,]", "", t.strip()).replace(",", ".")
    try: return float(n)
    except: return None

def _asin(url):
    m = re.search(r"/dp/([A-Z0-9]{10})", url)
    return m.group(1) if m else None

async def buscar_por_keyword(keyword, keyword_id=None, desconto_minimo=15, preco_maximo=None, max_resultados=8):
    resultados = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=UA, locale="pt-BR",
            extra_http_headers={"Accept-Language": "pt-BR,pt;q=0.9"})
        page = await context.new_page()
        url = f"https://www.amazon.com.br/s?k={keyword.replace(' ','+')}&deals-widget=1"
        print(f"[AMZ] Buscando: {keyword}")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=40000)
            await page.wait_for_timeout(3000)
            items = await page.query_selector_all("div[data-component-type=\"s-search-result\"]")
            for item in items[:max_resultados]:
                try:
                    titulo_el = await item.query_selector("h2 span")
                    titulo = (await titulo_el.inner_text()).strip() if titulo_el else None
                    if not titulo: continue
                    link_el = await item.query_selector("h2 a")
                    href = await link_el.get_attribute("href") if link_el else None
                    if not href: continue
                    href = "https://www.amazon.com.br" + href if href.startswith("/") else href
                    asin = _asin(href)
                    if not asin: continue
                    url_prod = f"https://www.amazon.com.br/dp/{asin}"
                    preco_int = await item.query_selector("span.a-price-whole")
                    preco_frac = await item.query_selector("span.a-price-fraction")
                    if not preco_int: continue
                    pi = (await preco_int.inner_text()).strip().replace(".", "").replace(",", "")
                    pf = (await preco_frac.inner_text()).strip() if preco_frac else "00"
                    try: preco_atual = float(f"{pi}.{pf}")
                    except: continue
                    original_el = await item.query_selector("span.a-text-price span.a-offscreen")
                    preco_original = _preco(await original_el.inner_text()) if original_el else None
                    desconto_pct = None
                    if preco_original and preco_original > preco_atual:
                        desconto_pct = int((1 - preco_atual / preco_original) * 100)
                    if desconto_pct and desconto_pct < desconto_minimo: continue
                    if preco_maximo and preco_atual > preco_maximo: continue
                    img_el = await item.query_selector("img.s-image")
                    imagem = await img_el.get_attribute("src") if img_el else None
                    url_afiliado = gerar_link_afiliado(url_prod, "amazon")
                    oferta = {"produto_id": None, "keyword_id": keyword_id, "loja": "amazon",
                              "titulo": titulo, "url": url_prod, "url_afiliado": url_afiliado,
                              "preco_atual": preco_atual, "preco_original": preco_original,
                              "desconto_pct": desconto_pct, "imagem_url": imagem}
                    resultados.append(oferta)
                    print(f"  [+] {titulo[:55]} — R$ {preco_atual} ({desconto_pct}% off)")
                except: continue
        except Exception as e:
            print(f"[AMZ] Erro: {e}")
        finally:
            await browser.close()
    return resultados

async def executar(keywords=None, produtos=None):
    todas = []
    if keywords:
        for kw in keywords:
            if kw["loja"] not in ("amazon", "todas"): continue
            ofertas = await buscar_por_keyword(kw["termo"], kw["id"], kw.get("desconto_minimo",15), kw.get("preco_maximo"))
            for o in ofertas:
                hid = salvar_preco(o)
                o["historico_id"] = hid
            todas.extend(ofertas)
            await asyncio.sleep(5)
    return todas
