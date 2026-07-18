#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
from curl_cffi import requests
from datetime import datetime

URL = "https://www.amazon.com.br/gp/goldbox"
PARAMS = {'ref': "nav_td_gb_ios_ham"}
HEADERS = {
    'User-Agent': "Mozilla/5.0 (iPhone; CPU iPhone OS 16_7_12 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    'Cookie': 'rxc=ABG6mE/L+7rbLXHYj7E; csm-hit=9DEA5H38KHPD1AJ3MCPJ; i18n-prefs=BRL; session-id=141-6631010-4280534'
}

MIN_DISCOUNT = 40          
MIN_DIFFERENCE = 300       
STATE_FILE = "deals.json"

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

def parse_category(product):
    cat_info = product.get('productCategory', {})
    raw_type = cat_info.get('productType') or cat_info.get('symbol', 'DESCONHECIDO')
    clean_raw = str(raw_type).replace('gl_', '').upper()
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


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {'last_check': 'Nunca atualizado', 'history': {}, 'data': []}

def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def fetch_page():
    try:
        resp = requests.get(URL, params=PARAMS, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"Erro no fetch: {e}")
        return None

def extract_products(html):
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

    try:
        return json.loads(html[start:i+1]).get('productSearchResponse', {}).get('products', [])
    except:
        return []

def parse_discount(product):
    price_data = product.get('price', {})
    price_to_pay = price_data.get('priceToPay', {}).get('price', '0')
    basis_price = price_data.get('basisPrice', {}).get('price', '0')
    try:
        if basis_price and price_to_pay:
            basis = float(str(basis_price).replace(',', '.'))
            current = float(str(price_to_pay).replace(',', '.'))
            if basis > 0: return round((1 - current / basis) * 100, 1)
    except: pass
    return 0

def parse_difference(product):
    price_data = product.get('price', {})
    price_to_pay = price_data.get('priceToPay', {}).get('price', '0')
    basis_price = price_data.get('basisPrice', {}).get('price', '0')
    try:
        if basis_price and price_to_pay:
            return round(float(str(basis_price).replace(',', '.')) - float(str(price_to_pay).replace(',', '.')), 2)
    except: pass
    return 0

def build_deal(product):
    link = product.get('link', '')
    if link and not link.startswith('http'): link = f"https://www.amazon.com.br{link}"
    
    img_obj = product.get('image', {})
    physical_id = img_obj.get('physicalId')
    
    if not physical_id:
        for key in ['physical', 'highRes', 'lowRes', 'thumb']:
            if isinstance(img_obj.get(key), dict) and 'physicalId' in img_obj[key]:
                physical_id = img_obj[key]['physicalId']
                break

    if physical_id:
        image = f"https://images-na.ssl-images-amazon.com/images/I/{physical_id}._AC_UL210_SR210,210_.jpg"
    else:
        image = ''
        for key in ['highRes', 'lowRes', 'physical']:
            if img_obj.get(key, {}).get('baseUrl'):
                image = img_obj[key]['baseUrl']
                break
        if not image and img_obj:
            urls = re.findall(r'https?://[^\s"\']+\.(?:jpg|jpeg|png|webp)', json.dumps(img_obj))
            if urls: image = urls[0]
        if image and not image.startswith('http'): 
            image = f"https://m.media-amazon.com/images/I/{image}"

    discount = parse_discount(product)
    difference = parse_difference(product)
    
    criteria = []
    if discount >= MIN_DISCOUNT: criteria.append(f"{discount}% OFF")
    if difference >= MIN_DIFFERENCE: criteria.append(f"R$ {difference} desc.")

    return {
        'asin': product.get('asin', ''),
        'title': product.get('title', 'N/A'),
        'link': link,
        'current_price': product.get('price', {}).get('priceToPay', {}).get('price', 'N/A'),
        'original_price': product.get('price', {}).get('basisPrice', {}).get('price', 'N/A'),
        'discount': discount,
        'difference': difference,
        'criteria': criteria,
        'badge': product.get('dealBadge', {}).get('label', {}).get('content', {}).get('fragments', [{}])[0].get('text', ''),
        'image': image,
        'category': parse_category(product)
    }

def run_scraper():
    state = load_state()
    history = state.get('history', {})
    html = fetch_page()
    
    if not html:
        print("HTML nao carregado.")
        return

    products = extract_products(html)
    deals = []
    now_iso = datetime.now().isoformat()
    
    for p in products:
        discount = parse_discount(p)
        diff = parse_difference(p)
        if discount >= MIN_DISCOUNT or diff >= MIN_DIFFERENCE:
            deal_data = build_deal(p)
            asin = deal_data['asin']
            current_price = deal_data['current_price']
            
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
            
            deal_data['is_new'] = is_new
            deal_data['discovery_ts'] = disc_date.timestamp()
            deals.append(deal_data)
            
    deals.sort(key=lambda x: (x.get('is_new', False), x['difference']), reverse=True)
    
    state['history'] = history
    state['data'] = deals
    state['last_check'] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    
    save_state(state)
    print(f"Sucesso! {len(deals)} ofertas salvas.")

if __name__ == "__main__":
    run_scraper()
