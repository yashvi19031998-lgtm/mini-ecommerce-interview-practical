"""
Festival & Digital Media Offers Engine for Sangeeta Infotech
Offers:
  - ₹500/- for 10 HD Festival creatives (custom logo & contact details)
  - ₹1,000/- for 3 Video Reels (viral audio & motion graphics)
  - ₹1,299/- for Combo Festive Booster (10 Images + 3 Reels)

Contact: +91 9106060400 | info@sangeetainfotech.co.in | Ahmedabad, Gujarat
"""

import os
import json
import uuid
import urllib.parse
from datetime import datetime, date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CLIENTS_FILE = os.path.join(DATA_DIR, "festival_clients.json")
SCHEDULE_FILE = os.path.join(DATA_DIR, "festival_schedules.json")

def _ensure_data_files():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CLIENTS_FILE):
        with open(CLIENTS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)
    if not os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

_ensure_data_files()

OFFERS = [
    {
        "id": "fest_10_pack",
        "name": "Business Post Pack",
        "tag": "MOST POPULAR",
        "price_inr": 500,
        "price_usd": 7,
        "deliverables": "10 Custom Images For Posts",
        "description": "10 high-converting custom images for business posts (product spotlights, offers, service promos, announcements) customized for your brand.",
        "features": [
            "10 High-Converting Business & Promo Images For Posts",
            "Custom company branding, typography & contact info",
            "1080x1080 HD Square (Perfect for WhatsApp Status, Facebook & Social Media)",
            "Engaging captions & call-to-actions included",
            "Delivered ready-to-post directly on your WhatsApp"
        ]
    },
    {
        "id": "reels_3_pack",
        "name": "Promotional Video Reels Pack",
        "tag": "HIGH ENGAGEMENT",
        "price_inr": 1000,
        "price_usd": 14,
        "deliverables": "3 High-Retention Promotional Video Reels",
        "description": "3 promotional short-form video reels for WhatsApp Status, Instagram & Facebook with engaging animations and call-to-actions.",
        "features": [
            "3 Custom Promotional Video Reels in 9:16 vertical format",
            "Trending background music & copyright-safe audio",
            "Dynamic text animations & company branding",
            "Story/Reel cover poster included",
            "High-bitrate MP4 download ready"
        ]
    },
    {
        "id": "combo_festive_booster",
        "name": "Festive Combo Booster",
        "tag": "BEST VALUE",
        "price_inr": 1299,
        "price_usd": 18,
        "deliverables": "10 Images + 3 Video Reels + 1 Free Banner",
        "description": "Complete social media festive dominance suite. Get all 10 festival posts plus 3 viral reels and a free festival header banner for Facebook/LinkedIn.",
        "features": [
            "Everything in Festival Brand Pack (10 Posts)",
            "Everything in Viral Reels Pack (3 Reels)",
            "1 FREE Festival Cover Banner (FB/LinkedIn/Website)",
            "Priority same-day delivery & revision support",
            "Full commercial rights & instant download"
        ]
    }
]

FESTIVAL_CALENDAR = [
    {
        "id": "maha_shivratri",
        "name": "Maha Shivratri",
        "gujarati_name": "મહાશિવરાત્રિ",
        "approx_date": "2026-02-15",
        "theme_color": "#1A237E",
        "accent_color": "#FFD700",
        "greeting_en": "Har Har Mahadev! Wishing you peace, prosperity, and divine blessings on Maha Shivratri.",
        "greeting_gu": "ૐ નમઃ શિવાય! મહાશિવરાત્રિના પાવન પર્વ પર તમને અને તમારા પરિવારને હાર્દિક શુભકામનાઓ.",
        "motif": "om_trishul"
    },
    {
        "id": "holi_dhuleti",
        "name": "Holi & Dhuleti",
        "gujarati_name": "હોળી અને ધૂળેટી",
        "approx_date": "2026-03-03",
        "theme_color": "#D81B60",
        "accent_color": "#FFEB3B",
        "greeting_en": "May your life be filled with vibrant colors of happiness, joy, and success! Happy Holi & Dhuleti.",
        "greeting_gu": "રંગો અને ઉલ્લાસના પર્વ હોળી-ધૂળેટીની આપ સર્વેને હાર્દિક શુભકામનાઓ!",
        "motif": "colors_gulal"
    },
    {
        "id": "ram_navami",
        "name": "Ram Navami",
        "gujarati_name": "શ્રી રામ નવમી",
        "approx_date": "2026-03-27",
        "theme_color": "#E65100",
        "accent_color": "#FFE082",
        "greeting_en": "May Lord Rama bless you with success, happiness, and righteous wisdom. Happy Ram Navami!",
        "greeting_gu": "મર્યાદા પુરુષોત્તમ પ્રભુ શ્રી રામના જન્મોત્સવ રામ નવમીની હાર્દિક શુભકામનાઓ! જય શ્રી રામ.",
        "motif": "bow_arrow"
    },
    {
        "id": "eid_ul_fitr",
        "name": "Eid-ul-Fitr",
        "gujarati_name": "રમઝાન ઈદ",
        "approx_date": "2026-03-20",
        "theme_color": "#004D40",
        "accent_color": "#FFD54F",
        "greeting_en": "Eid Mubarak! May this joyous day bring peace, happiness, and prosperity to you and your loved ones.",
        "greeting_gu": "ઈદ મુબારક! આપ સર્વેના જીવનમાં સુખ, શાંતિ અને સમૃદ્ધિ આવે તેવી દુઆ.",
        "motif": "crescent_star"
    },
    {
        "id": "raksha_bandhan",
        "name": "Raksha Bandhan",
        "gujarati_name": "રક્ષાબંધન",
        "approx_date": "2026-08-28",
        "theme_color": "#880E4F",
        "accent_color": "#FF80AB",
        "greeting_en": "Celebrating the eternal bond of love, care, and protection. Happy Raksha Bandhan!",
        "greeting_gu": "ભાઈ-બહેનના અતૂટ પ્રેમ અને સ્નેહના પવિત્ર પર્વ રક્ષાબંધનની હાર્દિક શુભકામનાઓ.",
        "motif": "rakhi"
    },
    {
        "id": "janmashtami",
        "name": "Krishna Janmashtami",
        "gujarati_name": "શ્રી કૃષ્ણ જન્માષ્ટમી",
        "approx_date": "2026-09-04",
        "theme_color": "#0D47A1",
        "accent_color": "#FFCA28",
        "greeting_en": "May Lord Krishna fill your life with love, health, and limitless prosperity. Happy Janmashtami!",
        "greeting_gu": "નંદ ઘેર આનંદ ભયો, જય કનૈયા લાલ કી! કૃષ્ણ જન્માષ્ટમીના પાવન પર્વની હાર્દિક શુભેચ્છાઓ.",
        "motif": "flute_peacock"
    },
    {
        "id": "ganesh_chaturthi",
        "name": "Ganesh Chaturthi",
        "gujarati_name": "ગણેશ ચતુર્થી",
        "approx_date": "2026-09-14",
        "theme_color": "#BF360C",
        "accent_color": "#FFF59D",
        "greeting_en": "May Lord Ganesha remove all obstacles and bestow you with wisdom and triumph. Ganpati Bappa Morya!",
        "greeting_gu": "વિઘ્નહર્તા દેવ શ્રી ગણેશજી આપના જીવનમાંથી તમામ વિઘ્નો દૂર કરે. ગણેશ ચતુર્થીની હાર્દિક શુભકામનાઓ!",
        "motif": "modak_lotus"
    },
    {
        "id": "navratri",
        "name": "Navratri Festival",
        "gujarati_name": "નવરાત્રિ મહોત્સવ",
        "approx_date": "2026-10-11",
        "theme_color": "#4A148C",
        "accent_color": "#FF4081",
        "greeting_en": "May Maa Durga bless you with strength, wisdom, and joy during these 9 auspicious nights. Happy Navratri!",
        "greeting_gu": "મા જગદંબાની કૃપાથી આપનું જીવન સુખ, શાંતિ અને સમૃદ્ધિથી ભરેલું રહે. નવરાત્રિની હાર્દિક શુભકામનાઓ!",
        "motif": "garba_diya"
    },
    {
        "id": "diwali_new_year",
        "name": "Diwali & Nutan Varsh",
        "gujarati_name": "દિવાળી અને નૂતન વર્ષ",
        "approx_date": "2026-11-08",
        "theme_color": "#B71C1C",
        "accent_color": "#FFD700",
        "greeting_en": "Wishing you and your family a glittering Diwali and a prosperous, joyful New Year!",
        "greeting_gu": "પ્રકાશના મહાપર્વ દીપાવલી અને નૂતન વર્ષાભિનંદન! નવું વર્ષ આપના માટે પ્રગતિશીલ નીવડે તેવી શુભકામના.",
        "motif": "diya_fireworks"
    },
    {
        "id": "independence_day",
        "name": "Independence Day",
        "gujarati_name": "સ્વાતંત્ર્ય દિન (૧૫મી ઓગસ્ટ)",
        "approx_date": "2026-08-15",
        "theme_color": "#FF6F00",
        "accent_color": "#2E7D32",
        "greeting_en": "Proud to be Indian! Saluting the spirit of freedom and unity. Happy Independence Day!",
        "greeting_gu": "૭૯મા સ્વાતંત્ર્ય પર્વની સમસ્ત ભારતવાસીઓને હાર્દિક શુભકામનાઓ. ભારત માતા કી જય!",
        "motif": "tricolor"
    }
]

# Client Storage Operations
def get_all_clients():
    _ensure_data_files()
    try:
        with open(CLIENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_client(client_data):
    _ensure_data_files()
    clients = get_all_clients()
    client_id = client_data.get("id") or f"fc_{uuid.uuid4().hex[:8]}"
    client_data["id"] = client_id
    client_data.setdefault("status", "PAID_ACTIVE")
    client_data.setdefault("enrolled_date", datetime.now().isoformat())
    client_data.setdefault("delivered_festivals", [])
    
    # Check if existing
    idx = next((i for i, c in enumerate(clients) if c.get("id") == client_id), -1)
    if idx >= 0:
        clients[idx] = {**clients[idx], **client_data}
    else:
        clients.append(client_data)

    with open(CLIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(clients, f, indent=2, ensure_ascii=False)
    return client_data

def get_client_by_id(client_id):
    clients = get_all_clients()
    return next((c for c in clients if c.get("id") == client_id), None)

# Pitch Generator
def generate_offer_pitch(lead):
    """
    Generate dynamic WhatsApp & Email pitches for a lead from all_leads_master.csv
    Featuring the '2 Free Samples with your logo' hook, ₹500 intro pack,
    and automated multi-day WhatsApp follow-up sequences.
    """
    biz_name = (
        lead.get("company_name") or
        lead.get("Company Name") or
        lead.get("Company") or
        lead.get("name") or
        "તમારા બિઝનેસ"
    ).strip()
    
    phone = (
        lead.get("phone") or
        lead.get("Phone") or
        lead.get("mobile") or
        ""
    ).strip().replace(" ", "").replace("-", "")
    
    email = (
        lead.get("email") or
        lead.get("Email") or
        ""
    ).strip()

    clean_phone = phone.lstrip("+")
    if clean_phone.startswith("91") and len(clean_phone) > 10:
        wa_target = clean_phone
    elif len(clean_phone) == 10:
        wa_target = f"91{clean_phone}"
    else:
        wa_target = clean_phone

    # 1. Primary WhatsApp Pitch (2 Free Samples Hook)
    wa_pitch = (
        f"નમસ્તે {biz_name}!\n\n"
        f"તમારા બિઝનેસના પ્રમોશન માટે સોશિયલ મીડિયા અને WhatsApp Status પર પોસ્ટ્સ મૂકવાનું પ્લાનિંગ કરો છો?\n\n"
        f"🎁 Sangeeta Infotech Special Offer:\n"
        f"અમે તમારા લોગો અને બિઝનેસ નામ સાથે ૨ સેમ્પલ પોસ્ટ્સ તદ્દન FREE બનાવી આપીશું.\n"
        f"જો તમને ગમે તો જ ૧૦ પોસ્ટ્સ નો પેક ફક્ત ₹500 (ઇન્ટ્રોડક્ટરી ઑફર).\n\n"
        f"તમારા ૨ ફ્રી સેમ્પલ્સ જોવા માટે ફક્ત 'YES' લખીને મોકલો.\n\n"
        f"Sangeeta Infotech | Ahmedabad"
    )

    wa_pitch_en = (
        f"Hello {biz_name} Team,\n\n"
        f"Planning your business promotions for WhatsApp & social media?\n\n"
        f"🎁 Sangeeta Infotech Intro Offer:\n"
        f"We will design 2 custom sample posts with your logo completely FREE.\n"
        f"If you like them, grab our 10-post business pack for just ₹500.\n\n"
        f"Want to see your 2 free samples? Simply reply 'YES'.\n\n"
        f"Sangeeta Infotech | Ahmedabad"
    )

    wa_pitch_gujlish = (
        f"Namaste {biz_name} ji,\n\n"
        f"{biz_name} na WhatsApp ane social media promotion mate ame tamara logo sathe "
        f"2 sample posts FREE banavi aapishu.\n"
        f"Game to j 10 posts no pack fakt ₹500 (introductory offer, aa mahine).\n\n"
        f"Sample joiye? Reply 'YES'.\n\n"
        f"Sangeeta Infotech | Ahmedabad"
    )

    wa_link = f"https://wa.me/{wa_target}?text={urllib.parse.quote(wa_pitch)}" if wa_target else ""
    wa_link_en = f"https://wa.me/{wa_target}?text={urllib.parse.quote(wa_pitch_en)}" if wa_target else ""
    wa_link_gujlish = f"https://wa.me/{wa_target}?text={urllib.parse.quote(wa_pitch_gujlish)}" if wa_target else ""

    # 2. Multi-Touch WhatsApp Follow-Up Cadence (Day 1, Day 3, Day 6)
    fu_day1_gu = f"નમસ્તે {biz_name}જી, તમારા બિઝનેસ માટે ૨ પોસ્ટ્સ તમારા લોગો સાથે ફ્રી બનાવી આપું? આજે જ મોકલી દઈશ 🙂"
    fu_day1_en = f"Hi {biz_name} Team, I reached out about 2 free sample posts with your logo. Shall I design them for you today?"
    fu_day1_gujlish = f"Namaste {biz_name} ji, {biz_name} mate 2 posts tamara logo sathe free banavi daun? Aaje j mokli dais 🙂"

    fu_day3_gu = f"નમસ્તે {biz_name}જી, આવી પોસ્ટ અમે અમદાવાદના બીજા એક જાણીતા બિઝનેસ માટે બનાવી. {biz_name} માટે પણ એક ફ્રી સેમ્પલ બનાવી દઉં?"
    fu_day3_en = f"Hi {biz_name} Team, this is what we designed for another business in Ahmedabad. Want one like this for {biz_name}, completely free?"
    fu_day3_gujlish = f"Namaste {biz_name} ji, aavi post ame Ahmedabad na bija business mate banavi. {biz_name} mate pan ek free banavi daun?"

    fu_day6_gu = f"છેલ્લો મેસેજ {biz_name}જી – અત્યારે પોસ્ટ્સની જરૂર ન હોય તો કોઈ વાંધો નહીં! આવતા મહિને યાદ કરાવું?"
    fu_day6_en = f"Last message from me, {biz_name} Team – if posts are not a priority right now, no problem at all! Should I check back next month?"
    fu_day6_gujlish = f"Chhello message {biz_name} ji – abhi jarur na hoy to koi vandho nahi. Aavta mahine yaad karavu?"

    followups = {
        "day1": {
            "gu": fu_day1_gu,
            "en": fu_day1_en,
            "gujlish": fu_day1_gujlish,
            "wa_url_gu": f"https://wa.me/{wa_target}?text={urllib.parse.quote(fu_day1_gu)}" if wa_target else "",
            "wa_url_en": f"https://wa.me/{wa_target}?text={urllib.parse.quote(fu_day1_en)}" if wa_target else ""
        },
        "day3": {
            "gu": fu_day3_gu,
            "en": fu_day3_en,
            "gujlish": fu_day3_gujlish,
            "wa_url_gu": f"https://wa.me/{wa_target}?text={urllib.parse.quote(fu_day3_gu)}" if wa_target else "",
            "wa_url_en": f"https://wa.me/{wa_target}?text={urllib.parse.quote(fu_day3_en)}" if wa_target else ""
        },
        "day6": {
            "gu": fu_day6_gu,
            "en": fu_day6_en,
            "gujlish": fu_day6_gujlish,
            "wa_url_gu": f"https://wa.me/{wa_target}?text={urllib.parse.quote(fu_day6_gu)}" if wa_target else "",
            "wa_url_en": f"https://wa.me/{wa_target}?text={urllib.parse.quote(fu_day6_en)}" if wa_target else ""
        }
    }

    # 3. High-Converting Email Pitch (~70 words, 2 Free Samples Hook)
    email_subject = f"2 Free Custom Sample Posts for {biz_name}?"
    email_body = (
        f"Namaste {biz_name} Team,\n\n"
        f"Looking to promote {biz_name} and attract more customers on WhatsApp & social media?\n\n"
        f"At **Sangeeta Infotech**, we will design 2 custom sample posts with your logo and business details completely FREE:\n\n"
        f"• 2 Custom Sample Posts: FREE\n"
        f"• 10 High-Quality Business Posts Pack: ₹500 (Introductory Offer)\n"
        f"• 3 Promotional Video Reels: ₹1,000\n\n"
        f"Delivered ready-to-post on WhatsApp — zero effort for you.\n\n"
        f"Want to see your 2 free samples? Simply reply 'YES' to this email or connect on WhatsApp below.\n\n"
        f"Warm regards,\n"
        f"**Sangeeta Infotech**\n"
        f"+91 9106060400\n"
        f"info@sangeetainfotech.co.in\n"
        f"https://sangeetainfotech.co.in\n"
        f"Ahmedabad, Gujarat"
    )

    mailto_link = f"mailto:{email}?subject={urllib.parse.quote(email_subject)}&body={urllib.parse.quote(email_body)}" if email else ""

    return {
        "lead_name": biz_name,
        "phone": phone,
        "email": email,
        "whatsapp_pitch_gu": wa_pitch,
        "whatsapp_pitch_en": wa_pitch_en,
        "whatsapp_pitch_gujlish": wa_pitch_gujlish,
        "whatsapp_url": wa_link,
        "whatsapp_url_en": wa_link_en,
        "whatsapp_url_gujlish": wa_link_gujlish,
        "followups": followups,
        "email_subject": email_subject,
        "email_body": email_body,
        "mailto_url": mailto_link
    }

# SVG / High-Resolution Creative Generator
def generate_festival_creative_svg(client, festival_id="diwali_new_year"):
    """
    Generates a publication-grade 1080x1080 SVG festive creative with client's branding.
    Can be rendered in browser, embedded in data URI, or converted to PNG on client canvas.
    """
    fest = next((f for f in FESTIVAL_CALENDAR if f["id"] == festival_id), FESTIVAL_CALENDAR[8])
    biz_name = client.get("business_name") or "Your Business Name"
    tagline = client.get("tagline") or "Quality Products & Dedicated Services"
    phone = client.get("phone") or "+91 9106060400"
    address = client.get("address") or "Ahmedabad, Gujarat"
    website = client.get("website") or "info@sangeetainfotech.co.in"
    logo_text = (client.get("logo_text") or biz_name[:2]).upper()

    theme = fest["theme_color"]
    accent = fest["accent_color"]
    fest_name = fest["name"]
    guj_name = fest["gujarati_name"]
    greeting = fest["greeting_gu"]
    greeting_en = fest["greeting_en"]

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1080" width="1080" height="1080">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{theme}" />
      <stop offset="60%" stop-color="#0a0a14" />
      <stop offset="100%" stop-color="#000000" />
    </linearGradient>
    <linearGradient id="goldGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{accent}" />
      <stop offset="50%" stop-color="#FFFFFF" />
      <stop offset="100%" stop-color="{accent}" />
    </linearGradient>
    <linearGradient id="cardGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="rgba(255,255,255,0.12)" />
      <stop offset="100%" stop-color="rgba(255,255,255,0.04)" />
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="12" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>
    <filter id="shadow">
      <feDropShadow dx="0" dy="10" stdDeviation="15" flood-color="#000000" flood-opacity="0.6"/>
    </filter>
  </defs>

  <!-- Background Base -->
  <rect width="1080" height="1080" fill="url(#bgGrad)" />

  <!-- Decorative Mandala & Festive Geometry -->
  <circle cx="540" cy="440" r="320" fill="none" stroke="{accent}" stroke-width="1.5" stroke-dasharray="8 6" opacity="0.35" />
  <circle cx="540" cy="440" r="260" fill="none" stroke="{accent}" stroke-width="1.2" opacity="0.4" />
  <circle cx="540" cy="440" r="180" fill="none" stroke="url(#goldGrad)" stroke-width="2" opacity="0.5" />

  <!-- Outer Border Frame -->
  <rect x="36" y="36" width="1008" height="1008" rx="28" fill="none" stroke="url(#goldGrad)" stroke-width="3" opacity="0.75" />
  <rect x="48" y="48" width="984" height="984" rx="20" fill="none" stroke="{accent}" stroke-width="1" opacity="0.3" />

  <!-- Corner Ornaments -->
  <g fill="{accent}" opacity="0.8">
    <circle cx="60" cy="60" r="6" />
    <circle cx="1020" cy="60" r="6" />
    <circle cx="60" cy="1020" r="6" />
    <circle cx="1020" cy="1020" r="6" />
  </g>

  <!-- Top Festive Header Tag -->
  <g transform="translate(540, 140)">
    <rect x="-180" y="-24" width="360" height="48" rx="24" fill="rgba(255,255,255,0.1)" stroke="{accent}" stroke-width="1.2" />
    <text text-anchor="middle" y="7" font-family="'Segoe UI', Roboto, sans-serif" font-size="19" font-weight="600" fill="{accent}" letter-spacing="3">✨ FESTIVE GREETINGS ✨</text>
  </g>

  <!-- Main Festival Title & Gujarati Callout -->
  <text x="540" y="270" text-anchor="middle" font-family="'Segoe UI', Roboto, sans-serif" font-size="62" font-weight="900" fill="url(#goldGrad)" filter="url(#glow)" letter-spacing="1">{fest_name}</text>
  <text x="540" y="340" text-anchor="middle" font-family="'Segoe UI', Roboto, sans-serif" font-size="38" font-weight="700" fill="#FFFFFF" opacity="0.95">{guj_name} ની હાર્દિક શુભકામનાઓ</text>

  <!-- Central Festival Icon / Emblem Glow -->
  <g transform="translate(540, 470)">
    <circle cx="0" cy="0" r="70" fill="rgba(255,215,0,0.15)" filter="url(#glow)" />
    <circle cx="0" cy="0" r="54" fill="url(#goldGrad)" filter="url(#shadow)" />
    <!-- Diya / Sparkle Icon Silhouette -->
    <path d="M -24 10 C -24 28, 24 28, 24 10 C 24 4, 14 -4, 0 -22 C -14 -4, -24 4, -24 10 Z" fill="#8B0000" />
    <circle cx="0" cy="-6" r="6" fill="#FFEE58" />
  </g>

  <!-- Festive Greetings Message Box -->
  <g transform="translate(540, 620)">
    <rect x="-420" y="-35" width="840" height="95" rx="18" fill="url(#cardGrad)" stroke="rgba(255,255,255,0.15)" stroke-width="1.5" />
    <text text-anchor="middle" y="2" font-family="'Segoe UI', Roboto, sans-serif" font-size="22" font-weight="600" fill="#FFFFFF" opacity="0.9">{greeting}</text>
    <text text-anchor="middle" y="36" font-family="'Segoe UI', Roboto, sans-serif" font-size="17" font-weight="400" fill="{accent}" opacity="0.85">{greeting_en}</text>
  </g>

  <!-- ==================== CLIENT BRANDING FOOTER (THE KEY DELIVERABLE) ==================== -->
  <g transform="translate(68, 770)" filter="url(#shadow)">
    <!-- White / Glassmorphic Card Container -->
    <rect width="944" height="230" rx="22" fill="#FFFFFF" opacity="0.97" />
    <rect width="944" height="230" rx="22" fill="none" stroke="{accent}" stroke-width="2" opacity="0.5" />

    <!-- Top Accent Stripe on Card -->
    <path d="M 0 22 C 0 10, 10 0, 22 0 L 922 0 C 934 0, 944 10, 944 22 L 944 28 L 0 28 Z" fill="{theme}" />

    <!-- Client Logo Emblem Circle -->
    <g transform="translate(85, 125)">
      <circle cx="0" cy="0" r="46" fill="{theme}" />
      <circle cx="0" cy="0" r="41" fill="none" stroke="{accent}" stroke-width="2" />
      <text text-anchor="middle" y="13" font-family="'Segoe UI', Roboto, sans-serif" font-size="32" font-weight="900" fill="#FFFFFF">{logo_text}</text>
    </g>

    <!-- Client Business Info -->
    <g transform="translate(160, 80)">
      <text x="0" y="0" font-family="'Segoe UI', Roboto, sans-serif" font-size="34" font-weight="900" fill="#1A1A24">{biz_name}</text>
      <text x="0" y="30" font-family="'Segoe UI', Roboto, sans-serif" font-size="18" font-weight="600" fill="#5A607F">{tagline}</text>
    </g>

    <!-- Divider Line -->
    <line x1="40" y1="150" x2="904" y2="150" stroke="#E2E8F0" stroke-width="1.5" />

    <!-- Contact Row: Phone, Address, Web -->
    <g transform="translate(50, 192)">
      <!-- Phone -->
      <g>
        <circle cx="12" cy="-6" r="14" fill="{theme}" opacity="0.1" />
        <text x="12" y="-1" text-anchor="middle" font-size="14" fill="{theme}">📞</text>
        <text x="36" y="0" font-family="'Segoe UI', Roboto, sans-serif" font-size="18" font-weight="700" fill="#1A202C">{phone}</text>
      </g>

      <!-- Address -->
      <g transform="translate(340, 0)">
        <circle cx="12" cy="-6" r="14" fill="{theme}" opacity="0.1" />
        <text x="12" y="-1" text-anchor="middle" font-size="14" fill="{theme}">📍</text>
        <text x="36" y="0" font-family="'Segoe UI', Roboto, sans-serif" font-size="17" font-weight="600" fill="#4A5568">{address}</text>
      </g>

      <!-- Web / Email -->
      <g transform="translate(640, 0)">
        <circle cx="12" cy="-6" r="14" fill="{theme}" opacity="0.1" />
        <text x="12" y="-1" text-anchor="middle" font-size="14" fill="{theme}">🌐</text>
        <text x="36" y="0" font-family="'Segoe UI', Roboto, sans-serif" font-size="16" font-weight="600" fill="{theme}">{website}</text>
      </g>
    </g>
  </g>
</svg>"""
    return svg_content

# Schedule Operations
def get_all_schedules():
    _ensure_data_files()
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def schedule_festival_dispatch(client_id, festival_id, dispatch_date=None):
    _ensure_data_files()
    schedules = get_all_schedules()
    client = get_client_by_id(client_id)
    if not client:
        return {"success": False, "error": f"Client {client_id} not found"}

    fest = next((f for f in FESTIVAL_CALENDAR if f["id"] == festival_id), None)
    if not fest:
        return {"success": False, "error": f"Festival {festival_id} not found"}

    sched_id = f"sch_{uuid.uuid4().hex[:8]}"
    item = {
        "id": sched_id,
        "client_id": client_id,
        "client_name": client.get("business_name"),
        "client_phone": client.get("phone"),
        "festival_id": festival_id,
        "festival_name": fest["name"],
        "gujarati_name": fest["gujarati_name"],
        "dispatch_date": dispatch_date or fest.get("approx_date"),
        "status": "SCHEDULED",  # SCHEDULED, DISPATCHED, FAILED
        "created_at": datetime.now().isoformat()
    }
    schedules.append(item)
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(schedules, f, indent=2, ensure_ascii=False)
    return {"success": True, "schedule": item}

def get_stats():
    clients = get_all_clients()
    schedules = get_all_schedules()
    active_clients = [c for c in clients if c.get("status") == "PAID_ACTIVE"]
    total_rev = sum(c.get("paid_amount", 500) for c in active_clients)
    return {
        "total_clients": len(clients),
        "active_clients": len(active_clients),
        "total_schedules": len(schedules),
        "total_revenue_inr": total_rev,
        "upcoming_festivals_count": len(FESTIVAL_CALENDAR)
    }

def get_bde_strategy():
    for dir_path in [DATA_DIR, os.path.join(BASE_DIR, "data")]:
        strategy_path = os.path.join(dir_path, "bde_outreach_strategy.json")
        if os.path.exists(strategy_path):
            try:
                with open(strategy_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}
