# Chatbots

Two chatbots, both free to run. With a `GEMINI_API_KEY` they phrase unknown answers with Gemini (free tier); without it they use built-in rules.

## English

### 1. In-app assistant ("Ask LeadsGen")

- **Where:** the round blue button at the bottom right of every page in the app (only after login).
- **What it answers:**
  - new leads, hot leads, e-mails sent, replies and bounces, for today / yesterday / this week / this month / in total
  - follow-ups needing attention
  - best scrapers and best sources
  - lead lists with filters: city, "without a website", "with e-mail", "with phone", "hot"
  - a company search
- **Languages:** English, Gujarati script, and Gujarati written in English letters ("Aaje ketla hot leads?").
- **Read-only:** it never changes a lead or sends anything.
- **With Gemini:** for questions the rules don't know, it sends only summary numbers (no names or e-mail addresses) to Gemini.
- **Code:** `chat_assistant.py`, route `POST /api/chat` (login required), `frontend/components/ChatAssistant.js`.

### 2. Website chatbot

- **What it does:** a chat widget for the company website. It answers questions about services, price, timeline, contact and location.
- **Where the answers come from:** only the company profile in Settings. It never promises prices or dates.
- **New leads:** when a visitor gives a requirement plus an e-mail or phone number, it saves them as a new lead with source **Website Chatbot**. It asks for their name, and e-mails the owner (the Settings e-mail) about the enquiry.
- **Security (the endpoint is public):**
  - only the sites in `WIDGET_ALLOWED_ORIGINS` can use it (default: `https://sangeetainfotech.co.in` and `https://www.sangeetainfotech.co.in`)
  - at most 30 messages per 10 minutes and 3 saved enquiries per hour per visitor IP
  - size limits on every field, HTML removed, a hidden spam trap
  - e-mail addresses are checked
- **Code:** `website_chatbot.py`, `widget/chatbot.js`, routes `POST /public/chat`, `GET /widget/chatbot.js`, `GET /widget/demo` (test page, only when the backend runs on this computer).

**Putting it on the website** needs the backend reachable on the internet. Today it runs only on this computer; hosting is still to be decided. Once it is hosted at, say, `https://api.example.in`:
1. Set `WIDGET_ALLOWED_ORIGINS` to the website address(es) in the server's `.env`.
2. Add one line before `</body>` on the website: `<script src="https://api.example.in/widget/chatbot.js" defer></script>`

**Test locally:** start the backend and open `http://127.0.0.1:5000/widget/demo`.

## ગુજરાતી

- **App નો chatbot:** app માં નીચે જમણી બાજુ વાદળી બટન. "આજે કેટલા hot leads?", "Ahmedabad ના website વગરના leads" જેવા સવાલોના જવાબ આપે છે. એ કંઈ બદલતો નથી કે મોકલતો નથી.
- **Website નો chatbot:**
  - Website પર મૂકવાનું chat બટન. Services, કિંમત અને સંપર્ક વિશે જવાબ આપે છે.
  - Visitor કામ અને e-mail કે phone આપે તો નવી lead તરીકે save કરે છે, અને તમને mail કરે છે.
  - Website પર ચાલુ કરવા backend internet પર મૂકવું પડશે (hosting હજી નક્કી કરવાનું બાકી છે).
  - અત્યારે `http://127.0.0.1:5000/widget/demo` પર test કરી શકાય છે.
