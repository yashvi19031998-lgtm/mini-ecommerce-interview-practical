"""File Uploads: contacts from files the user uploads.

  .xlsx         Excel sheets -> CSV text -> the Contact Import screen (column mapping, duplicates, save)
  .vcf          vCard contacts (phone / Outlook export): name, organisation, title, phones, e-mails, website, address
  .docx         Word text (paragraphs + tables) -> contact blocks
  .eml / .mbox  e-mails: the sender (name + address) and the phone / website / company in the signature
  .pdf          brochures, expo catalogues: text of each page -> contact blocks (pypdf)
  .txt / .html  text -> contact blocks
  .jpg / .png   visiting-card photos -> OCR (only when Tesseract is installed) -> contact blocks

Everything is read in memory with the Python standard library (plus pypdf). Safety limits: 10 MB per file;
Office files are ZIPs - only the needed parts are read, each at most 30 MB unpacked, and XML with a DOCTYPE
(entity tricks) is refused; at most 100 PDF pages, 2,000 e-mails and 2,000 contacts per file.
The contacts then go through bulk_contacts.check_leads (normalise, duplicates, "already in Leads").
"""
import base64
import binascii
import csv
import email
import email.policy
import io
import mailbox
import os
import re
import shutil
import tempfile
import zipfile
from email.utils import getaddresses
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

import bulk_contacts as bc
import deep_search
import search_engine as se

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_PART_BYTES = 30 * 1024 * 1024
MAX_PDF_PAGES = 100
MAX_MESSAGES = 2000
MAX_CONTACTS = 2000
MAX_SHEETS = 10
TYPES = {
    ".xlsx": "Excel", ".vcf": "vCard", ".docx": "Word", ".eml": "E-mail", ".mbox": "Mailbox", ".pdf": "PDF",
    ".txt": "Text", ".html": "Web page", ".htm": "Web page", ".jpg": "Image", ".jpeg": "Image", ".png": "Image",
    ".webp": "Image",
}
EMAIL_FIND = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
WEB_FIND = re.compile(r"\b(?:https?://|www\.)[^\s<>()\"',;]+", re.I)
COMPANY_WORDS = re.compile(r"\b(pvt|private|ltd|limited|llp|inc|industries|industry|enterprises?|traders?|trading|"
                           r"solutions?|technologies|technology|tech|infotech|corporation|corp|company|co\.|group|"
                           r"associates|exports?|imports?|agency|agencies|studio|foods|pharma|labs?|systems|services|"
                           r"consultants?|consultancy|manufacturers?|builders|developers|motors|textiles?|hospital|"
                           r"clinic|academy|institute|school)\b", re.I)
TITLE_WORDS = re.compile(r"\b(director|manager|ceo|cto|cfo|founder|co-founder|owner|proprietor|partner|president|"
                         r"head|executive|engineer|officer|consultant|sales|marketing|hr|md|gm)\b", re.I)
NS_SHEET = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class FileError(ValueError):
    """A file the module cannot read; the message is shown to the user."""


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

def decode_upload(name: Any, data_b64: Any) -> Tuple[str, str, bytes]:
    name = os.path.basename(str(name or "")).strip()[:120]
    ext = os.path.splitext(name)[1].lower()
    if ext not in TYPES:
        raise FileError(f"Unsupported file type '{ext or '?'}' - use {', '.join(sorted(TYPES))}")
    if not isinstance(data_b64, str) or not data_b64:
        raise FileError("The file is empty")
    if "," in data_b64[:100] and data_b64.startswith("data:"):
        data_b64 = data_b64.split(",", 1)[1]
    if len(data_b64) > MAX_FILE_BYTES * 4 // 3 + 16:
        raise FileError("The file is larger than 10 MB")
    try:
        data = base64.b64decode(data_b64, validate=True)
    except (binascii.Error, ValueError):
        raise FileError("The upload is damaged - choose the file again")
    if not data:
        raise FileError("The file is empty")
    return name, ext, data


def _text(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    from charset_normalizer import from_bytes
    best = from_bytes(data).best()
    return str(best) if best else data.decode("latin-1", "replace")


# ---------------------------------------------------------------------------
# Office files (ZIP + XML), read safely
# ---------------------------------------------------------------------------

def _zip(data: bytes) -> zipfile.ZipFile:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise FileError("Not a valid Office file (it may be an old .xls / .doc - save it as .xlsx / .docx)")
    if len(z.infolist()) > 5000:
        raise FileError("The file has too many parts")
    return z


def _part(z: zipfile.ZipFile, name: str) -> Optional[bytes]:
    try:
        info = z.getinfo(name)
    except KeyError:
        return None
    if info.file_size > MAX_PART_BYTES:
        raise FileError("The file unpacks to more than 30 MB - split it")
    raw = z.read(info)
    if b"<!DOCTYPE" in raw[:4096].upper() or b"<!ENTITY" in raw[:4096].upper():
        raise FileError("The file contains an XML DOCTYPE, which is not allowed")
    return raw


def _xml(raw: bytes) -> ET.Element:
    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        raise FileError("The file is damaged (XML could not be read)")


def _col(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref or "A").group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def xlsx_sheets(data: bytes) -> List[Dict[str, Any]]:
    z = _zip(data)
    wb = _part(z, "xl/workbook.xml")
    if wb is None:
        raise FileError("Not an Excel workbook")
    shared: List[str] = []
    sst = _part(z, "xl/sharedStrings.xml")
    if sst is not None:
        for si in _xml(sst).iter(f"{NS_SHEET}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{NS_SHEET}t")))
    rels = {}
    rel_raw = _part(z, "xl/_rels/workbook.xml.rels")
    if rel_raw is not None:
        for r in _xml(rel_raw):
            rels[r.get("Id")] = r.get("Target", "")
    out = []
    for sh in _xml(wb).iter(f"{NS_SHEET}sheet"):
        if len(out) >= MAX_SHEETS:
            break
        target = rels.get(sh.get(f"{NS_REL}id"), "")
        path = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
        raw = _part(z, path.replace("xl/xl/", "xl/"))
        if raw is None:
            continue
        rows: List[List[str]] = []
        for row in _xml(raw).iter(f"{NS_SHEET}row"):
            cells: Dict[int, str] = {}
            for c in row.iter(f"{NS_SHEET}c"):
                t, v = c.get("t"), c.find(f"{NS_SHEET}v")
                if t == "s" and v is not None and (v.text or "").isdigit() and int(v.text) < len(shared):
                    val = shared[int(v.text)]
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(f"{NS_SHEET}t"))
                else:
                    val = v.text if v is not None and v.text else ""
                    if re.fullmatch(r"\d+\.0", val):
                        val = val[:-2]                       # 9825012345.0 -> 9825012345
                cells[_col(c.get("r", ""))] = val.strip()
            if cells and any(cells.values()):
                rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
            if len(rows) > bc.MAX_CSV_ROWS + 1:
                break
        if len(rows) < 2:
            continue
        width = max(len(r) for r in rows)
        buf = io.StringIO()
        csv.writer(buf).writerows([r + [""] * (width - len(r)) for r in rows])
        out.append({"name": sh.get("name", f"Sheet {len(out) + 1}")[:60], "rows": len(rows) - 1, "csv": buf.getvalue()})
    if not out:
        raise FileError("No sheet with a header row and data was found")
    return out


def docx_text(data: bytes) -> str:
    z = _zip(data)
    raw = _part(z, "word/document.xml")
    if raw is None:
        raise FileError("Not a Word document")
    lines = []
    body = _xml(raw).find(f"{NS_W}body")
    for el in (body if body is not None else []):
        if el.tag == f"{NS_W}p":
            lines.append("".join(t.text or "" for t in el.iter(f"{NS_W}t")))
        elif el.tag == f"{NS_W}tbl":
            for tr in el.iter(f"{NS_W}tr"):
                cells = [" ".join("".join(t.text or "" for t in p.iter(f"{NS_W}t")) for p in tc.iter(f"{NS_W}p")).strip()
                         for tc in tr.iter(f"{NS_W}tc")]
                lines.append("\n".join(c for c in cells if c))
                lines.append("")                               # each table row is its own block
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# vCard
# ---------------------------------------------------------------------------

def _qp(value: str, params: str) -> str:
    if "QUOTED-PRINTABLE" in params.upper():
        import quopri
        charset = re.search(r"CHARSET=([\w-]+)", params, re.I)
        try:
            return quopri.decodestring(value.encode()).decode(charset.group(1) if charset else "utf-8", "replace")
        except LookupError:
            return quopri.decodestring(value.encode()).decode("utf-8", "replace")
    return value


def parse_vcards(text: str) -> List[Tuple[str, Dict[str, str]]]:
    text = re.sub(r"\r?\n[ \t]", "", text)                    # unfold continuation lines
    text = re.sub(r"=\r?\n", "", text)                        # quoted-printable soft breaks
    items = []
    for i, card in enumerate(re.findall(r"BEGIN:VCARD(.*?)END:VCARD", text, re.S | re.I), start=1):
        f: Dict[str, List[str]] = {}
        for line in card.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            name, _, params = key.partition(";")
            name = name.split(".")[-1].upper()               # item1.EMAIL -> EMAIL
            value = _qp(value.strip(), params).replace("\\,", ",").replace("\\;", ";").replace("\\n", " ")
            if value:
                f.setdefault(name, []).append(value)
        full = (f.get("FN") or [" ".join(p for p in reversed((f.get("N") or [""])[0].split(";")[:2]) if p)])[0]
        org = (f.get("ORG") or [""])[0].replace(";", " ").strip()
        adr = (f.get("ADR") or [""])[0]
        loc = ", ".join(p for p in adr.split(";") if p.strip())
        desc = "; ".join(x for x in ((f.get("TITLE") or [""])[0], (f.get("NOTE") or [""])[0][:200]) if x)
        items.append((f"card {i}", {"full_name": full.strip(), "company_name": org, "email": ", ".join(f.get("EMAIL", [])[:3]),
                                    "mobile_number": ", ".join(f.get("TEL", [])[:3]), "website": (f.get("URL") or [""])[0],
                                    "location": loc, "description": desc}))
        if len(items) >= MAX_CONTACTS:
            break
    if not items:
        raise FileError("No contacts found in this vCard file")
    return items


# ---------------------------------------------------------------------------
# Free text -> contact blocks
# ---------------------------------------------------------------------------

def _phones(text: str) -> List[str]:
    out = []
    for cand in bc.PHONE_CANDIDATE.findall(text):
        r = bc.classify_phone(cand)
        if r["status"] == "valid" and r["type"] in ("Mobile", "Landline"):
            # landlines as 0 + STD + number, so the leads normaliser keeps them as landlines (079-26543210)
            value = r["e164"] if r["type"] == "Mobile" else "0" + r["e164"][3:]
            if value not in out:
                out.append(value)
    return out


def _person(line: str) -> bool:
    words = line.split()
    return 2 <= len(words) <= 4 and all(w[:1].isupper() and w.replace(".", "").isalpha() for w in words) \
        and not COMPANY_WORDS.search(line) and not TITLE_WORDS.search(line)


def block_contact(block: str) -> Optional[Dict[str, str]]:
    emails = list(dict.fromkeys(e.lower().rstrip(".") for e in EMAIL_FIND.findall(block)))
    phones = _phones(block)
    if not emails and not phones:
        return None
    webs = [w.rstrip(".") for w in WEB_FIND.findall(block)]
    lines = [" ".join(l.split()) for l in block.splitlines() if l.strip()]
    plain = [l for l in lines if not EMAIL_FIND.search(l) and not WEB_FIND.search(l) and len(re.sub(r"\D", "", l)) < 6
             and 2 < len(l) <= 80]
    company = next((l for l in plain if COMPANY_WORDS.search(l)), "")
    person = next((l for l in plain if _person(l)), "")
    title = next((l for l in plain if TITLE_WORDS.search(l) and l not in (company, person)), "")
    if not webs:
        doms = [e.split("@")[1] for e in emails if e.split("@")[1] not in bc.FREE_PROVIDERS]
        webs = [f"https://{doms[0]}"] if doms else []
    if not company and webs:
        company = se.domain_of(webs[0] if webs[0].startswith("http") else "https://" + webs[0])
    loc_line = next((l for l in plain if re.search(r"\b\d{6}\b", l) or re.search(r"(road|nagar|street|lane|floor|"
                                                                                  r"sector|plot|near|opp\.?)", l, re.I)), "")
    return {"company_name": company, "full_name": person, "email": ", ".join(emails[:3]),
            "mobile_number": ", ".join(phones[:3]), "website": webs[0] if webs else "", "location": loc_line[:200],
            "description": title}


def text_contacts(text: str, label: str) -> List[Tuple[str, Dict[str, str]]]:
    blocks = [b for b in re.split(r"\n\s*\n", text.replace("\r", "")) if b.strip()]
    if len(blocks) == 1 and len(blocks[0].splitlines()) > 40:   # one huge block: fall back to windows of lines
        ls = blocks[0].splitlines()
        blocks = ["\n".join(ls[i:i + 8]) for i in range(0, len(ls), 8)]
    out = []
    for i, b in enumerate(blocks, start=1):
        c = block_contact(b)
        if c:
            out.append((f"{label} {i}", c))
        if len(out) >= MAX_CONTACTS:
            break
    return out


# ---------------------------------------------------------------------------
# E-mail, PDF, images
# ---------------------------------------------------------------------------

def _message_contact(msg, n: int) -> Optional[Tuple[str, Dict[str, str]]]:
    senders = getaddresses([str(msg.get("from", "") or "")])
    if not senders or "@" not in senders[0][1]:
        return None
    name, addr = senders[0]
    body = ""
    try:
        part = msg.get_body(preferencelist=("plain", "html")) if hasattr(msg, "get_body") else None
        if part is not None:
            body = part.get_content()
            if part.get_content_type() == "text/html":
                body = deep_search.visible_text(BeautifulSoup(body, "html.parser"))
    except (KeyError, LookupError, AttributeError, UnicodeError):
        body = ""
    signature = "\n".join(body.strip().splitlines()[-15:])
    sig = block_contact(signature + f"\n{addr}") or {}
    local = addr.split("@")[0].lower()
    if local in bc.NO_REPLY or local.startswith(("noreply", "no-reply", "mailer-daemon", "notifications")):
        return None
    return (f"e-mail {n}", {"full_name": name.strip().strip('"')[:100], "email": addr.lower(),
                            "company_name": sig.get("company_name", ""), "mobile_number": sig.get("mobile_number", ""),
                            "website": sig.get("website", ""), "location": sig.get("location", ""),
                            "description": f"E-mail: {str(msg.get('subject', '') or '')[:150]}"})


def eml_contacts(data: bytes) -> List[Tuple[str, Dict[str, str]]]:
    msg = email.message_from_bytes(data, policy=email.policy.default)
    c = _message_contact(msg, 1)
    if not c:
        raise FileError("No sender found in this e-mail (or it is a no-reply message)")
    return [c]


def mbox_contacts(data: bytes) -> List[Tuple[str, Dict[str, str]]]:
    d = tempfile.mkdtemp(prefix="mbox_")
    try:
        path = os.path.join(d, "upload.mbox")
        with open(path, "wb") as fh:
            fh.write(data)
        box = mailbox.mbox(path, factory=lambda f: email.message_from_binary_file(f, policy=email.policy.default),
                           create=False)
        out = []
        for n, msg in enumerate(box, start=1):
            if n > MAX_MESSAGES:
                break
            c = _message_contact(msg, n)
            if c:
                out.append(c)
        box.close()
    finally:
        shutil.rmtree(d, ignore_errors=True)
    if not out:
        raise FileError("No e-mail senders found in this mailbox")
    return out


def pdf_text_pages(data: bytes) -> List[str]:
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError:
        raise FileError("PDF support needs the pypdf library (pip install -r requirements.txt)")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise FileError("The PDF is password-protected - open it, print / save it without a password, and upload again")
        pages = []
        for i, page in enumerate(reader.pages):
            if i >= MAX_PDF_PAGES:
                break
            pages.append(page.extract_text() or "")
    except FileError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, RecursionError) as e:
        raise FileError(f"The PDF could not be read ({e.__class__.__name__})")
    if not any(p.strip() for p in pages):
        raise FileError("This PDF has no text layer (it is a scanned image) - text could not be read")
    return pages


def ocr_status() -> Dict[str, Any]:
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        return {"available": False, "reason": "Visiting-card OCR needs Tesseract OCR and the pytesseract + Pillow "
                                                 "libraries - not installed yet"}
    exe = shutil.which("tesseract") or next((p for p in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                                                          r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe")
                                             if os.path.exists(p)), None)
    if not exe:
        return {"available": False, "reason": "The Tesseract OCR program is not installed on this computer"}
    return {"available": True, "reason": "", "exe": exe}


def image_text(data: bytes) -> str:
    st = ocr_status()
    if not st["available"]:
        raise FileError(st["reason"])
    import pytesseract
    from PIL import Image
    pytesseract.pytesseract.tesseract_cmd = st["exe"]
    try:
        img = Image.open(io.BytesIO(data))
        img.thumbnail((2400, 2400))
        return pytesseract.image_to_string(img.convert("L"), timeout=30)
    except Exception as e:  # noqa: BLE001 - damaged image / OCR timeout
        raise FileError(f"The image could not be read ({e.__class__.__name__})")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_upload(name: Any, data_b64: Any, master_path: str = "") -> Dict[str, Any]:
    fname, ext, data = decode_upload(name, data_b64)
    kind = TYPES[ext]
    if ext == ".xlsx":
        return {"file": fname, "type": kind, "mode": "table", "sheets": xlsx_sheets(data)}
    if ext == ".vcf":
        items = parse_vcards(_text(data))
    elif ext == ".docx":
        items = text_contacts(docx_text(data), "block")
    elif ext == ".eml":
        items = eml_contacts(data)
    elif ext == ".mbox":
        items = mbox_contacts(data)
    elif ext == ".pdf":
        items = []
        for i, page in enumerate(pdf_text_pages(data), start=1):
            items += text_contacts(page, f"page {i} ·")
    elif ext in (".html", ".htm"):
        items = text_contacts(deep_search.visible_text(BeautifulSoup(_text(data), "html.parser")).replace("  ", "\n"), "block")
    elif ext == ".txt":
        items = text_contacts(_text(data), "block")
    else:
        items = text_contacts(image_text(data), "card")
    if not items:
        raise FileError("No e-mail address or phone number was found in this file")
    checked = bc.check_leads(items[:MAX_CONTACTS], os.path.splitext(fname)[0], master_path, where="item")
    return {"file": fname, "type": kind, "mode": "contacts", **checked}
