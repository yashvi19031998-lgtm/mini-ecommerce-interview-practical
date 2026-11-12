# Settings → API Keys & Integrations

**Status:** QA passed (6/6 browser checks, 9 unit tests) · **Updated:** 2026-11-12

## English
- **Where:** Sidebar → **Settings & SMTP**, at the bottom of the page.
- **What it shows:** every API key the app can use, grouped by Core, Email, Alerts, Lead sources, Job Portal Scraper and CRM Sources. Each row lists:
  - the variable names, with ✓ on the ones that are set
  - what the key is for, and which module uses it
  - the cost: Free, Free (limited) or Paid
  - a **Get key** link
  - a status: Configured, Using SMTP login (IMAP only), Incomplete, or Not set
- **Filters:** All / Not set / Free only.
- **How to add a key:**
  1. Write it in `test-demo/.env`. `.env.example` lists every variable.
  2. Restart the Python backend.
  3. Click **Refresh**.
- **Security:**
  - The API (`GET /api/settings/api-keys`, login required) returns only set / not set, **never the values**. Tests check this.
  - Keys cannot be typed into the browser, so they never leave the server machine.

## ગુજરાતી
- **ક્યાં:** Sidebar → **Settings & SMTP**, page ના નીચેના ભાગમાં.
- **શું દેખાય:** app જે પણ API keys વાપરે છે તે બધી, group પ્રમાણે. દરેક key માટે આ દેખાય છે:
  - key નું નામ
  - તે શા માટે છે
  - Free છે કે Paid
  - **Get key** link
  - status: set છે કે નહીં
- **Key કેવી રીતે ઉમેરવી:**
  1. `test-demo/.env` માં લખો.
  2. Python backend restart કરો.
  3. **Refresh** દબાવો.
- **સુરક્ષા:** key ની value ક્યારેય browser માં મોકલાતી નથી, ફક્ત "set છે કે નહીં" એટલું જ દેખાય છે.
