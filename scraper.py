#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
from datetime import datetime
from curl_cffi import requests

# ==================== CONFIGURACOES ====================
MIN_DISCOUNT = 40          
MIN_DIFFERENCE = 300       
STATE_FILE = "deals.json"

# ==================== MAPA DE CATEGORIAS ====================
CATEGORY_MAP = {
    "SPIRITS": "🥃 Bebidas",
    "CONDITIONER": "🧴 Cuidado Pessoal",
    "NOTEBOOK_COMPUTER": "💻 Eletrônicos",
    "PA_SYSTEM": "🔊 Eletrônicos",
    "AIR_CONDITIONER": "❄️ Eletrodomésticos",
    "TELEVISION": "📺 Eletrodomésticos",
    "PERSONAL_FRAGRANCE": "💧 Cuidado Pessoal",
    "CELLULAR_PHONE": "📱 Smartphones e Tablets",
    "HAIR_STYLING_AGENT": "✂️ Autocuidado"
}

def map_category(raw_type):
    if not raw_type:
        return "[DESCONHECIDO]"
        
    clean_raw = str(raw_type).replace('gl_', '').upper()
    # Limpa prefixos do Mercado Livre para manter padrao (ex: MLB-MUGS -> MUGS)
    if clean_raw.startswith('MLB-'):
        clean_raw = clean_raw[4:]
        
    exact_match = CATEGORY_MAP.get(clean_raw)
    if exact_match:
        return exact_match
        
    has_hair = "HAIR" in clean_raw
    has_cleaner = "CLEANER" in clean_raw
    has_cond = "CONDITIONER" in clean_raw
    has_care = "CARE" in clean_raw
    
    if (has_hair and has_cleaner) or (has_cond and has_cleaner) or (has_hair and has_care):
        return "🧴 Cuidado Pessoal"
        
    return f"[{clean_raw}]"

# ==================== SCRAPER AMAZON ====================
def fetch_amazon():
    URL = "https://www.amazon.com.br/gp/goldbox"
    PARAMS = {'ref': "nav_td_gb_ios_ham"}
    HEADERS = {
        'User-Agent': "Mozilla/5.0 (iPhone; CPU iPhone OS 16_7_12 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
        'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        'Cookie': 'rxc=ABG6mE/L+7rbLXHYj7E; csm-hit=9DEA5H38KHPD1AJ3MCPJ; i18n-prefs=BRL; session-id=141-6631010-4280534'
    }
    try:
        resp = requests.get(URL, params=PARAMS, headers=HEADERS, impersonate="safari15_3", timeout=20)
        if resp.status_code != 200: return None
        return resp.text
    except: return None

def build_amazon_deal(product):
    asin = product.get('asin', '')
    link = product.get('link', '')
    if link and not link.startswith('http'): link = f"https://www.amazon.com.br{link}"
    
    img_obj = product.get('image', {})
    physical_id = img_obj.get('physicalId')
    if not physical_id:
        for key in ['physical', 'highRes', 'lowRes', 'thumb']:
            if isinstance(img_obj.get(key), dict) and 'physicalId' in img_obj[key]:
                physical_id = img_obj[key]['physicalId']
                break

    if physical_id: image = f"https://images-na.ssl-images-amazon.com/images/I/{physical_id}._AC_UL210_SR210,210_.jpg"
    else:
        image = ''
        for key in ['highRes', 'lowRes', 'physical']:
            if img_obj.get(key, {}).get('baseUrl'):
                image = img_obj[key]['baseUrl']
                break
        if image and not image.startswith('http'): image = f"https://m.media-amazon.com/images/I/{image}"

    # Precos e descontos
    price_data = product.get('price', {})
    current_str = price_data.get('priceToPay', {}).get('price', '0')
    basis_str = price_data.get('basisPrice', {}).get('price', '0')
    
    current_price, original_price, discount, difference = 0, 0, 0, 0
    try:
        if current_str and basis_str:
            current_price = float(str(current_str).replace(',', '.'))
            original_price = float(str(basis_str).replace(',', '.'))
            if original_price > 0:
                discount = round((1 - current_price / original_price) * 100, 1)
                difference = round(original_price - current_price, 2)
    except: pass
    
    criteria = []
    if discount >= MIN_DISCOUNT: criteria.append(f"{discount}% OFF")
    if difference >= MIN_DIFFERENCE: criteria.append(f"R$ {difference} desc.")

    cat_info = product.get('productCategory', {})
    raw_type = cat_info.get('productType') or cat_info.get('symbol', '')

    return {
        'asin': asin,
        'title': product.get('title', 'N/A'),
        'link': link,
        'current_price': current_price,
        'original_price': original_price if original_price else 'N/A',
        'discount': discount,
        'difference': difference,
        'criteria': criteria,
        'badge': product.get('dealBadge', {}).get('label', {}).get('content', {}).get('fragments', [{}])[0].get('text', 'Oferta Amazon'),
        'image': image,
        'category': map_category(raw_type)
    }

def get_amazon_deals():
    html = fetch_amazon()
    if not html: return []
    
    match = re.search(r'assets\.mountWidget\([\'"]slot-14[\'"],\s*(\{[\s\S]*?\})\s*\);', html)
    if not match: return []
    
    start = match.start(1)
    brace_count, in_string, escape, i = 0, False, False, start
    while i < len(html):
        c = html[i]
        if escape: escape = False
        elif c == '\\': escape = True
        elif c == '"': in_string = not in_string
        elif not in_string:
            if c == '{': brace_count += 1
            elif c == '}':
                brace_count -= 1
                if brace_count == 0: break
        i += 1

    try: products = json.loads(html[start:i+1]).get('productSearchResponse', {}).get('products', [])
    except: products = []

    deals = []
    for p in products:
        deal = build_amazon_deal(p)
        if deal['discount'] >= MIN_DISCOUNT or deal['difference'] >= MIN_DIFFERENCE:
            deals.append(deal)
    return deals

# ==================== SCRAPER MERCADO LIVRE ====================
def build_ml_deal(item):
    metadata = item.get('metadata', {})
    ml_id = metadata.get('id', '')
    if not ml_id: return None
    
    # Pega o link exato da API ou monta manualmente se falhar
    link = metadata.get('permalink', '')
    if not link:
        link = f"https://produto.mercadolivre.com.br/{ml_id}"
    
    # --- NOVO SISTEMA DE FOTOS DO ML ---
    image = ""
    pics = item.get('pictures', {})
    pic_list = pics.get('pictures', [])
    
    if pic_list:
        pic_id = pic_list[0].get('id', '')
        square = pics.get('square', 'Q') 
        if pic_id:
            # Monta a URL de alta qualidade (.webp) igual o app do iOS faz internamente
            image = f"https://http2.mlstatic.com/D_{square}_NP_2X_{pic_id}-AB.webp"
            
    # Fallback caso a máscara principal falhe
    if not image:
        image = metadata.get('picture') or metadata.get('thumbnail', '')
        
    # Força HTTPS para o GitHub Pages não dar block (Mixed Content)
    if image and image.startswith("http://"):
        image = image.replace("http://", "https://")
    # -----------------------------------
    
    current_price, original_price = 0, 0
    title = "N/A"
    
    cart_status = item.get('add_to_cart_capability', {}).get('item_status', {}).get('price', {})
    if cart_status:
        current_price = cart_status.get('current', 0)
        original_price = cart_status.get('original', 0)
        
    for comp in item.get('components', []):
        if comp.get('type') == 'title':
            title = comp.get('title', {}).get('text', title)

    discount, difference = 0, 0
    if original_price and current_price:
        discount = round((1 - current_price / original_price) * 100, 1)
        difference = round(original_price - current_price, 2)
        
    criteria = []
    if discount >= MIN_DISCOUNT: criteria.append(f"{discount}% OFF")
    if difference >= MIN_DIFFERENCE: criteria.append(f"R$ {difference} desc.")

    domain_id = ""
    try:
        cart_config = item.get('add_to_cart_capability', {}).get('cart_config', {})
        event_data = cart_config.get('track', {}).get('data', {}).get('event_data', {})
        domain_id = event_data.get('item', {}).get('domain_id', '')
    except: pass

    scarcity = item.get('lightning_stocks', {}).get('label', '')
    badge = f"🟡 ML | {scarcity}" if scarcity else "🟡 Mercado Livre"

    return {
        'asin': ml_id,
        'title': title,
        'link': link,
        'current_price': current_price,
        'original_price': original_price if original_price else 'N/A',
        'discount': discount,
        'difference': difference,
        'criteria': criteria,
        'badge': badge,
        'image': image,
        'category': map_category(domain_id)
    }
    
def get_ml_deals():
    deals = []
    url = "https://www.mercadolivre.com.br/ofertas/api/items/"
    headers = {
        'User-Agent': "MercadoLibre-iOS/10.557.1 (iPhone 8; iOS 16.7.12)",
        'Accept': "application/json, text/plain, */*",
        'referer': "https://www.mercadolivre.com.br/ofertas?active_selector=LIGHTNING",
        'x-csrf-token': "tyas7fqV-4JrUd-u5ePHBqVTQnsCyLZ4BldA",
        'Cookie': "_mldataSessionId=c57d212b-1b22-48bc-90e1-c17a9d5154d4; _d2id=D3AB1A58-718C-48D7-A65B-FA39615E0BE2; nni-ctx=e%3Dv2%2Cv%3D1%2E107%2E3%2Cs%3D2%2Cd%3D0%2Ccb%3D1%2Cftc%3D0%2Csrc%3Dwk; ttcsid=1785206297684::PSKKDqSU_wqg6YaPoEUE.1.1785206333234.0::1.-1498.0::35472.2.209.59::0.0.0; ttcsid_CFVSC2JC77U0ARCJTCJ0=1785206297683::DaAxDMJwxVtDsodHoM1P.1.1785206333235.0; _pin_unauth=dWlkPU9EazNOamt3TWpNdE5qQXpNQzAwT0RZeExXSm1NVGN0T1RrM1pEQXhNMlk0TnpZMQ; _fbp=fb.2.1785206297108.947068035436086721; _gcl_au=1.1.763882899.1785206297; _tt_enable_cookie=1; _ttp=01KYK9CN2E7GG8FN2YF3S8096A_.tt.2; _twpid=tw.1785206297388.830193900583380106; hide-cookie-banner=0-WEBVIEW_NOT_SUPPORTED; x-nni-dc=os%3DiOS%2Cosv%3D16.7.12; _csrf=8KzginlCvrjlsvzswh6QLipG"
    }

    offset = 0
    limit = 20
    max_items = 150 # Paginação do Mercado Livre bate em até 150 itens varridos pra não tomar block rapido
    
    while offset < max_items:
        params = {
            'promo_channel': "true",
            'promo_resource': "items",
            'offset': str(offset),
            'limit': str(limit),
            'container_id': "MLB1648364-1",
            'uid': "D3AB1A58-718C-48D7-A65B-FA39615E0BE2",
            'd2id': "D3AB1A58-718C-48D7-A65B-FA39615E0BE2",
            'platform': "/mobile/android",
            'deal_print_id': "86afccf9-04f9-446b-8f95-fc2673a9ea0b",
            'origin': "bricker",
            'promotion_type': "lightning",
            'scheduled': "false",
            'slot_id': "13"
        }
        try:
            resp = requests.get(url, params=params, headers=headers, impersonate="safari15_3", timeout=20)
            if resp.status_code != 200: break
            
            data = resp.json()
            items = data.get('items', [])
            if not items: break
            
            for item in items:
                deal = build_ml_deal(item)
                if deal and (deal['discount'] >= MIN_DISCOUNT or deal['difference'] >= MIN_DIFFERENCE):
                    deals.append(deal)
            
            next_offset = data.get('paging', {}).get('nextOffset')
            if not next_offset: break
            offset = next_offset
        except Exception as e:
            print(f"Erro ML: {e}")
            break
            
    return deals


# ==================== CORE DO MOTOR ====================
# ==================== CORE DO MOTOR ====================
def run_scraper():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
        except: state = {'history': {}, 'data': []}
    else:
        state = {'history': {}, 'data': []}
        
    history = state.get('history', {})
    
    print("Varrendo Amazon...")
    amz_deals = get_amazon_deals()
    print(f"Encontradas {len(amz_deals)} na Amazon.")
    
    print("Varrendo Mercado Livre...")
    ml_deals = get_ml_deals()
    print(f"Encontradas {len(ml_deals)} no Mercado Livre.")

    all_deals = amz_deals + ml_deals
    now_iso = datetime.now().isoformat()
    
    final_deals = []
    seen_asins = set() # <-- SISTEMA ANTI-DUPLICATA
    
    for deal in all_deals:
        asin = deal['asin']
        
        # Se o ID já foi processado nesta execução, ignora a duplicata
        if asin in seen_asins:
            continue
        seen_asins.add(asin)
        
        current_price = deal['current_price']
        
        if asin not in history:
            history[asin] = {
                'discovery_date': now_iso,
                'price_history': [{'price': current_price, 'date': now_iso}]
            }
        else:
            last_price = history[asin]['price_history'][-1]['price']
            if current_price != last_price and current_price != 'N/A':
                history[asin]['price_history'].append({'price': current_price, 'date': now_iso})
        
        disc_date = datetime.fromisoformat(history[asin]['discovery_date'])
        is_new = (datetime.now() - disc_date).total_seconds() < 7200
        
        deal['is_new'] = is_new
        deal['discovery_ts'] = disc_date.timestamp()
        final_deals.append(deal)
            
    final_deals.sort(key=lambda x: (x.get('is_new', False), x['difference']), reverse=True)
    
    state['history'] = history
    state['data'] = final_deals
    state['last_check'] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        
    print(f"Sucesso Total! {len(final_deals)} ofertas salvas (sem duplicatas).")
    
if __name__ == "__main__":
    run_scraper()
