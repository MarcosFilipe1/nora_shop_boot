# 🛍️ Nora Shop — Bot de Ofertas

Bot que roda no Raspberry Pi 4, coleta ofertas automaticamente em 5 lojas e envia para grupos do WhatsApp e perfil do Instagram, com links de afiliado e cupons de desconto.

## Lojas monitoradas
- Mercado Livre
- Magazine Luiza
- Amazon *(em breve)*
- Shopee *(em breve)*
- AliExpress *(em breve)*

## Estrutura

```
nora-shop-bot/
├── main.py                  # Orquestrador principal
├── requirements.txt
├── core/
│   ├── database.py          # Banco SQLite
│   ├── afiliados.py         # Links de afiliado ← preencha seus IDs aqui
│   ├── cupons.py            # Lógica de cupons por loja
│   └── formatter.py         # Templates de mensagem WhatsApp/Instagram
├── scrapers/
│   ├── mercadolivre.py      # Scraper ML
│   └── magazineluiza.py     # Scraper Magalu
├── sender/
│   ├── painel.py            # Painel web Flask (porta 5001)
│   ├── static/style.css
│   └── templates/           # Dashboard, cupons, grupos, logs, config
├── data/                    # Banco SQLite e configs (gerado automaticamente)
└── logs/                    # Logs do bot (gerado automaticamente)
```

## Instalação no Raspberry Pi

```bash
# 1. Clonar o repositório
git clone https://github.com/SEU_USUARIO/nora-shop-bot.git
cd nora-shop-bot

# 2. Instalar dependências Python
pip install -r requirements.txt --break-system-packages

# 3. Instalar Chromium para o Playwright
python -m playwright install chromium --with-deps

# 4. Setup inicial (cria banco + keywords de exemplo)
python main.py --setup

# 5. Preencher IDs de afiliado
nano core/afiliados.py

# 6. Subir o painel web
python sender/painel.py
# Acesse: http://IP-DO-RASPI:5001
```

## Agendar scraping automático (cron)

```bash
crontab -e
# Adicionar (roda a cada 30 minutos):
*/30 * * * * cd /home/pi/nora-shop-bot && python main.py >> logs/bot.log 2>&1
```

## Configurar IDs de afiliado

Edite `core/afiliados.py` e preencha:

```python
ML_ID          = ''   # ID numérico — painel ML > Conta > Perfil
AMAZON_TAG     = ''   # Ex: seutag-20 — associados.amazon.com.br
SHOPEE_ID      = ''   # af_siteid — affiliate.shopee.com.br
ALIEXPRESS_ID  = ''   # aff_fcid — portals.aliexpress.com
MAGALU_ID      = ''   # ID — parceiros.magazineluiza.com.br
```

## Painel Web

Acesse `http://IP-DO-RASPI:5001` para:
- Ver métricas e gráfico de envios
- Cadastrar cupons e ofertas manuais
- Gerenciar grupos do WhatsApp
- Configurar credenciais de afiliado
- Monitorar logs em tempo real

## Próximos módulos

- [ ] `sender/whatsapp.js` — envio para grupos via whatsapp-web.js
- [ ] `sender/instagram.py` — post automático via Graph API
- [ ] `scrapers/amazon.py`
- [ ] `scrapers/shopee.py`
- [ ] `scrapers/aliexpress.py`
