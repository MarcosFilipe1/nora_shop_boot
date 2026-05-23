
import asyncio, re, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from playwright.async_api import async_playwright
from core.database import salvar_preco
from core.afiliados import gerar_link_afiliado

UA = "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36"

def _preco(t):
    if not t: return None
    n = re.sub(r"[^\d,]", "", t.strip()).replace(",", ".")
    try: return float(n)
    except: return None

async def buscar_por_keyword(keyword, keyword_id=None, desconto_minimo=15, preco_maximo=None, max_resultados=8):
    resultados = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=UA, locale="pt-BR")
        page = await context.new_page()
        url = f"https://shopee.com.br/search?keyword={keyword.replace(' ','%20')}&sortBy=sales"
        print(f"[SHP] Buscando: {keyword}")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=40000)
            await page.wait_for_timeout(5000)
            items = await page.query_selector_all("div[data-sqe=\"item\"], li.shopee-search-item-result__item")
            if not items:
                items = await page.query_selector_all("[class*=\"col-\"]:has(a[href*=\"/product/\"])")
            for item in items[:max_resultados]:
                try:
                    titulo_el = await item.query_selector("div[class*=\"name\"], span[class*=\"name\"]")
                    titulo = (await titulo_el.inner_text()).strip() if titulo_el else None
                    if not titulo: continue
                    link_el = await item.query_selector("a")
                    href = await link_el.get_attribute("href") if link_el else None
                    if not href: continue
                    url_prod = ("https://shopee.com.br" + href if href.startswith("/") else href).split("?")[0]
                    preco_els = await item.query_selector_all("span[class*=\"price\"]")
                    preco_atual = None
                    for el in preco_els:
                        v = _preco(await el.inner_text())
                        if v and v > 0:
                            preco_atual = v
                            break
                    if not preco_atual: continue
                    if preco_maximo and preco_atual > preco_maximo: continue
                    img_el = await item.query_selector("img")
                    imagem = await img_el.get_attribute("src") if img_el else None
                    url_afiliado = gerar_link_afiliado(url_prod, "shopee")
                    oferta = {"produto_id": None, "keyword_id": keyword_id, "loja": "shopee",
                              "titulo": titulo, "url": url_prod, "url_afiliado": url_afiliado,
                              "preco_atual": preco_atual, "preco_original": None,
                              "desconto_pct": None, "imagem_url": imagem}
                    resultados.append(oferta)
                    print(f"  [+] {titulo[:55]} — R$ {preco_atual}")
                except: continue
        except Exception as e:
            print(f"[SHP] Erro: {e}")
        finally:
            await browser.close()
    return resultados

async def buscar_flash_deals(keyword_id=None, desconto_minimo=20, max_resultados=10):
    return []

async def executar(keywords=None, produtos=None):
    todas = []
    if keywords:
        for kw in keywords:
            if kw["loja"] not in ("shopee", "todas"): continue
            ofertas = await buscar_por_keyword(kw["termo"], kw["id"], kw.get("desconto_minimo",15), kw.get("preco_maximo"))
            for o in ofertas:
                hid = salvar_preco(o)
                o["historico_id"] = hid
            todas.extend(ofertas)
            await asyncio.sleep(4)
    return todas
