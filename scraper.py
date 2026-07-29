#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
from datetime import datetime
from curl_cffi import requests
from urllib.parse import unquote

# ==================== CONFIGURACOES ====================
MIN_DISCOUNT = 40          
MIN_DIFFERENCE = 300       
STATE_FILE = "deals.json"

# ==================== MAPA DE CATEGORIAS ====================
CATEGORY_MAP = {
    # 💻 Eletrônicos & Informática
    "COMPUTER": "💻 Eletrônicos & Informática",
    "PERSONAL_COMPUTER": "💻 Eletrônicos & Informática",
    "NOTEBOOK_COMPUTER": "💻 Eletrônicos & Informática",
    "PA_SYSTEM": "💻 Eletrônicos & Informática",
    "TELEVISION": "💻 Eletrônicos & Informática",
    "CELLULAR_PHONE": "💻 Eletrônicos & Informática",
    "PROJECTORS": "💻 Eletrônicos & Informática",
    "MICROPHONES": "💻 Eletrônicos & Informática",
    "CAMERA_TRIPODS": "💻 Eletrônicos & Informática",
    "SMARTWATCH_AND_WRISTWATCH_SCREEN_PROTECTORS": "💻 Eletrônicos & Informática",

    # ❄️ Eletrodomésticos & Casa
    "AIR_CONDITIONER": "❄️ Eletrodomésticos & Casa",
    "FOOD_BLENDER": "❄️ Eletrodomésticos & Casa",
    "ROBOTIC_VACUUM_CLEANER": "❄️ Eletrodomésticos & Casa",
    "REFRIGERATOR": "❄️ Eletrodomésticos & Casa",
    "KITCHEN_COOKWARE_KITS": "❄️ Eletrodomésticos & Casa",
    "VACUUM_CLEANER": "❄️ Eletrodomésticos & Casa",
    "DRINKING_CUP": "❄️ Eletrodomésticos & Casa",
    "MANUAL_INDOOR_CURTAINS_AND_BLINDS": "❄️ Eletrodomésticos & Casa",
    "GARMENT_STEAMER": "❄️ Eletrodomésticos & Casa",
    "QUILTS_AND_COVERLETS": "❄️ Eletrodomésticos & Casa",
    "PORTABLE_FANS": "❄️ Eletrodomésticos & Casa",
    "BATHROOM_FAUCETS_AND_MIXERS": "❄️ Eletrodomésticos & Casa",

    # 👕 Moda & Acessórios
    "WATCH": "👕 Moda & Acessórios",
    "BLOUSES": "👕 Moda & Acessórios",
    "SNEAKERS": "👕 Moda & Acessórios",
    "WEDDING_BANDS": "👕 Moda & Acessórios",
    "SUNGLASSES": "👕 Moda & Acessórios",
    "CLOTHING_LOTS": "👕 Moda & Acessórios",
    "DRESSES": "👕 Moda & Acessórios",
    "T_SHIRTS": "👕 Moda & Acessórios",
    "SOCKS": "👕 Moda & Acessórios",
    "HANDBAGS": "👕 Moda & Acessórios",

    # 🧴 Beleza & Cuidado Pessoal
    "CONDITIONER": "🧴 Beleza & Cuidado Pessoal",
    "PERSONAL_FRAGRANCE": "🧴 Beleza & Cuidado Pessoal",
    "HAIR_STYLING_AGENT": "🧴 Beleza & Cuidado Pessoal",
    "HAIR_DRYER": "🧴 Beleza & Cuidado Pessoal",
    "TOOTHBRUSH": "🧴 Beleza & Cuidado Pessoal",
    "PERFUMES": "🧴 Beleza & Cuidado Pessoal",
    "TEETH_WHITENING_STRIPS": "🧴 Beleza & Cuidado Pessoal",
    "BODY_DEODORANT": "🧴 Beleza & Cuidado Pessoal",

    # 🎮 Games & Lazer
    "VIDEO_GAME_CONTROLLER": "🎮 Games & Lazer",

    # 🛠️ Ferramentas & Construção
    # nao achei nenhum ainda kkkkkk

    # 🛒 Supermercado & Bebidas
    "SPIRITS": "🛒 Supermercado & Bebidas",

    # 🐾 Pet Shop
    # ainda nao apareceu

    # ⚽ Esportes & Saúde
    "SPORT_SHORTS": "⚽ Esportes & Saúde",
    "SUPPLEMENTS": "⚽ Esportes & Saúde",
    "DIVING_MASKS": "⚽ Esportes & Saúde",
    "SPORT_BRAS": "⚽ Esportes & Saúde",

    # 🧸 Bebês & Brinquedos
    "SKIN_CLEANING_WIPE": "🧸 Bebês & Brinquedos" # MamyPoko (fraldas/lenços)
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
    
    # --- SISTEMA DE EXTRAÇÃO DE LINK (URL DECODING + REGEX) ---
    link = metadata.get('permalink', '')
    url_params = metadata.get('url_params', '')
    
    # 1. Regex para pescar o permalink dentro da string suja dos parâmetros
    match = re.search(r'permalink=([^&#]+)', url_params)
    if match:
        # "Arrumador": Desfaz o URL Encoding (%3A vira :, %2F vira /, etc.)
        link = unquote(match.group(1))
        
    # 2. Fallback extremo: Regex varrendo o objeto inteiro convertido em texto
    if not link or not link.startswith('http'):
        item_str = json.dumps(item)
        match_str = re.search(r'permalink=([^&"\']+)', item_str)
        if match_str:
            link = unquote(match_str.group(1))
            
    # 3. Fallback final: Monta na unha só com o ID caso tudo falhe
    if not link or not link.startswith('http'):
        link = f"https://produto.mercadolivre.com.br/{ml_id}"
    # ----------------------------------------------------------
    
    # --- NOVO SISTEMA DE FOTOS DO ML ---
    image = ""
    pics = item.get('pictures', {})
    pic_list = pics.get('pictures', [])
    
    if pic_list:
        pic_id = pic_list[0].get('id', '')
        square = pics.get('square', 'Q') 
        if pic_id:
            image = f"https://http2.mlstatic.com/D_{square}_NP_2X_{pic_id}-AB.webp"
            
    if not image:
        image = metadata.get('picture') or metadata.get('thumbnail', '')
        
    if image and image.startswith("http://"):
        image = image.replace("http://", "https://")

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


# ==================== tendão de aquiles do site ====================

def verify_amazon_price(asin):
    url = f"https://www.amazon.com.br/dp/{asin}"
    headers = {
        'User-Agent': "Mozilla/5.0 (iPhone; CPU iPhone OS 16_7_12 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
        'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, impersonate="safari15_3", timeout=10)
        if resp.status_code != 200: return None
        
        prices = re.findall(r'class="a-offscreen">\s*R\$\s*([\d.,]+)\s*<', resp.text)
        if not prices: return None
        
        return float(prices[0].replace('.', '').replace(',', '.'))
    except:
        return None

def verify_ml_price(ml_id):
    url = f"https://api.mercadolibre.com/items/{ml_id}"
    try:
        import requests as req_padrao
        resp = req_padrao.get(url, timeout=10)
        if resp.status_code != 200: return None
        
        data = resp.json()
        if data.get('status') != 'active': return None # Oferta pausada ou esgotada
        
        return float(data.get('price', 0))
    except:
        return None

def run_scraper():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
        except: state = {'history': {}, 'data': []}
    else:
        state = {'history': {}, 'data': []}
        
    history = state.get('history', {})
    old_deals = state.get('data', [])
    
    print("Varrendo Amazon...")
    amz_deals = get_amazon_deals()
    print(f"Encontradas {len(amz_deals)} na Amazon.")
    
    print("Varrendo Mercado Livre...")
    ml_deals = get_ml_deals()
    print(f"Encontradas {len(ml_deals)} no Mercado Livre.")

    new_scraped_deals = amz_deals + ml_deals
    
    final_deals = []
    seen_asins = set() 
    
    for deal in new_scraped_deals:
        asin = deal['asin']
        if asin in seen_asins: continue
        seen_asins.add(asin)
        final_deals.append(deal)
        
    print("Auditando sobrevivência de ofertas antigas...")
    for old_deal in old_deals:
        asin = old_deal['asin']
        
        # Se a oferta já foi confirmada na raspagem acima, pula
        if asin in seen_asins: 
            continue
            
        old_price = old_deal['current_price']
        is_amazon = not asin.startswith('MLB')
        
        current_live_price = verify_amazon_price(asin) if is_amazon else verify_ml_price(asin)
            
        # Se achou um preço e ele for MENOR ou IGUAL ao preço que tínhamos gravado
        if current_live_price is not None and current_live_price <= old_price:
            old_deal['current_price'] = current_live_price
            
            # Se o preço caiu mais ainda, atualiza a matemática do card
            if current_live_price < old_price:
                original = old_deal['original_price']
                if original != 'N/A':
                    old_deal['discount'] = round((1 - current_live_price / original) * 100, 1)
                    old_deal['difference'] = round(original - current_live_price, 2)
                    
                    crit = []
                    if old_deal['discount'] >= MIN_DISCOUNT: crit.append(f"{old_deal['discount']}% OFF")
                    if old_deal['difference'] >= MIN_DIFFERENCE: crit.append(f"R$ {old_deal['difference']} desc.")
                    old_deal['criteria'] = crit

            final_deals.append(old_deal)
            seen_asins.add(asin)
            print(f"✔️ Retido no Pagameno$: {asin} (R$ {current_live_price})")
        else:
            print(f"❌ Descartado: {asin} (Expirou ou preço subiu)")

    # 3. Atualiza os históricos de flutuação e carimbos de data
    now_iso = datetime.now().isoformat()
    
    for deal in final_deals:
        asin = deal['asin']
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
        # Continua marcando como "NOVO" por 2 horinhas
        is_new = (datetime.now() - disc_date).total_seconds() < 7200 
        
        deal['is_new'] = is_new
        deal['discovery_ts'] = disc_date.timestamp()
            
    # Ordena para a tela do Pagameno$
    final_deals.sort(key=lambda x: (x.get('is_new', False), x['difference']), reverse=True)
    
    state['history'] = history
    state['data'] = final_deals
    state['last_check'] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        
    print(f"Sucesso! {len(final_deals)} ofertas confirmadas ativas no Pagameno$.")
    
