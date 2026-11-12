"""Tests for File Uploads (file_uploads.py), no network. Sample files are built in memory (fictional data).

python -m unittest test_file_uploads -v
"""
import base64
import csv
import io
import os
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
from unittest import mock

import file_uploads as fu
import html_cache_manager as hcm
import lead_normalizer as ln


def b64(data):
    return base64.b64encode(data if isinstance(data, bytes) else data.encode("utf-8")).decode()


def office(parts):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for k, v in parts.items():
            z.writestr(k, v)
    return buf.getvalue()


S = ('xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
     'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def xlsx(rows_xml, sheets=(("Members", "rId1", "worksheets/sheet1.xml"),), strings=()):
    wb = f'<workbook {S}><sheets>' + "".join(f'<sheet name="{n}" sheetId="{i}" r:id="{rid}"/>' for i, (n, rid, _) in enumerate(sheets, 1)) + "</sheets></workbook>"
    rels = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + \
        "".join(f'<Relationship Id="{rid}" Target="{t}"/>' for _, rid, t in sheets) + "</Relationships>"
    parts = {"xl/workbook.xml": wb, "xl/_rels/workbook.xml.rels": rels,
             "xl/sharedStrings.xml": f'<sst {S}>' + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>"}
    for (_, _, t), rx in zip(sheets, rows_xml):
        parts[f"xl/{t}"] = f'<worksheet {S}><sheetData>{rx}</sheetData></worksheet>'
    return office(parts)


def docx(body):
    return office({"word/document.xml": f'<?xml version="1.0"?><w:document {W}><w:body>{body}</w:body></w:document>'})


def p(t):
    return f"<w:p><w:r><w:t>{t}</w:t></w:r></w:p>"


def pdf_with_text(lines):
    content = "BT /F1 12 Tf 50 750 Td 14 TL " + " ".join(f"({l}) Tj T*" for l in lines) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(content)} >>\nstream\n{content}\nendstream", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = "%PDF-1.4\n", []
    for i, o in enumerate(objs, start=1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("latin-1")


def parse(name, data, master=""):
    return fu.parse_upload(name, b64(data), master_path=master)


class Input(unittest.TestCase):
    def test_rejections(self):
        for name, data, msg in (("a.exe", "x", "unsupported"), ("a.xls", "x", "unsupported"), ("a.vcf", "", "empty"),
                                ("a.docx", "not a zip", "not a valid office file")):
            with self.assertRaises(ValueError) as cm:
                fu.parse_upload(name, b64(data) if data else "")
            self.assertIn(msg, str(cm.exception).lower(), name)
        with self.assertRaises(ValueError):
            fu.parse_upload("a.vcf", "%%% not base64 %%%")
        with self.assertRaises(ValueError) as cm:
            fu.parse_upload("a.pdf", "A" * (fu.MAX_FILE_BYTES * 2))
        self.assertIn("10 mb", str(cm.exception).lower())

    def test_data_url_prefix_accepted(self):
        r = fu.parse_upload("c.vcf", "data:text/vcard;base64," + b64("BEGIN:VCARD\nFN:A B\nEMAIL:a@acme.in\nEND:VCARD"))
        self.assertEqual(r["results"][0]["email"], "a@acme.in")


class Excel(unittest.TestCase):
    def test_sheet_to_csv(self):
        strings = ["Company", "Email", "Mobile", "QA Epsilon", "info@qa-epsilon.co.in"]
        c = lambda ref, i: f'<c r="{ref}" t="s"><v>{i}</v></c>'  # noqa: E731
        rows = (f'<row r="1">{c("A1", 0)}{c("B1", 1)}{c("C1", 2)}</row>'
                f'<row r="3">{c("A3", 3)}{c("B3", 4)}<c r="C3"><v>9825044444.0</v></c></row>'
                f'<row r="4"><c r="C4" t="inlineStr"><is><t>inline</t></is></c></row>')
        r = parse("m.xlsx", xlsx([rows], strings=strings))
        self.assertEqual(r["mode"], "table")
        sheet = r["sheets"][0]
        self.assertEqual((sheet["name"], sheet["rows"]), ("Members", 2))
        got = list(csv.reader(io.StringIO(sheet["csv"])))
        self.assertEqual(got[1], ["QA Epsilon", "info@qa-epsilon.co.in", "9825044444"])     # 9825044444.0 -> digits
        self.assertEqual(got[2], ["", "", "inline"])                                        # gaps kept as columns

    def test_two_sheets_and_empty(self):
        sheets = (("A", "rId1", "worksheets/sheet1.xml"), ("B", "rId2", "worksheets/sheet2.xml"))
        one = '<row r="1"><c r="A1" t="inlineStr"><is><t>Email</t></is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>x@y.in</t></is></c></row>'
        r = parse("m.xlsx", xlsx([one, one], sheets=sheets))
        self.assertEqual([s["name"] for s in r["sheets"]], ["A", "B"])
        with self.assertRaises(ValueError):
            parse("m.xlsx", xlsx(['<row r="1"><c r="A1" t="inlineStr"><is><t>only header</t></is></c></row>']))

    def test_unsafe_office_files(self):
        evil = office({"word/document.xml": '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><w:document ' + W + '/>'})
        with self.assertRaises(ValueError) as cm:
            parse("e.docx", evil)
        self.assertIn("doctype", str(cm.exception).lower())
        with mock.patch.object(zipfile.ZipFile, "getinfo", return_value=SimpleNamespace(file_size=fu.MAX_PART_BYTES + 1)):
            with self.assertRaises(ValueError) as cm:                                       # zip bomb: refused unread
                parse("b.docx", docx(p("x")))
        self.assertIn("30 mb", str(cm.exception).lower())


class Word(unittest.TestCase):
    def test_blocks_and_table(self):
        body = (p("Exhibitors") + p("") + p("QA Gamma Industries") + p("Amit Joshi") + p("Mob: 98250 33333") +
                p("Email: amit@qa-gamma.co.in") + p("") +
                f'<w:tbl><w:tr><w:tc>{p("QA Delta Exports LLP")}</w:tc><w:tc>{p("sales@qa-delta.in")}</w:tc>'
                f'<w:tc>{p("079-2654 3210")}</w:tc></w:tr></w:tbl>')
        r = parse("expo.docx", docx(body))
        got = {x["company_name"]: x for x in r["results"]}
        g = got["QA Gamma Industries"]
        self.assertEqual((g["full_name"], g["email"], g["mobile_number"], g["status"]),
                         ("Amit Joshi", "amit@qa-gamma.co.in", "+91 98250 33333", "new"))       # .co.in kept
        d = got["QA Delta Exports LLP"]
        self.assertEqual((d["email"], d["mobile_number"], d["website"]), ("sales@qa-delta.in", "079-26543210", "https://qa-delta.in"))


class VCard(unittest.TestCase):
    def test_cards(self):
        text = ("BEGIN:VCARD\r\nVERSION:3.0\r\nFN:Ravi Patel\r\nORG:QA Acme Foods Pvt Ltd;Sales\r\nTITLE:Director\r\n"
                "TEL;TYPE=CELL:+91 98250 11111\r\nEMAIL:ravi@qa-acme.in\r\nURL:https://qa-acme.in\r\n"
                "ADR:;;12 Ring\r\n  Road;Ahmedabad;Gujarat;380015;India\r\nEND:VCARD\r\n"
                "BEGIN:VCARD\r\nVERSION:2.1\r\nN:Shah;Neha;;;\r\nFN;ENCODING=QUOTED-PRINTABLE:Neha=20=\r\nShah\r\n"
                "item1.TEL:09825022222\r\nEND:VCARD\r\nBEGIN:VCARD\r\nFN:Ravi Again\r\nEMAIL:RAVI@qa-acme.in\r\nEND:VCARD\r\n")
        r = parse("c.vcf", text)
        a, b, c = r["results"]
        self.assertEqual((a["full_name"], a["company_name"], a["mobile_number"], a["website"], a["description"]),
                         ("Ravi Patel", "QA Acme Foods Pvt Ltd Sales", "+91 98250 11111", "https://qa-acme.in", "Director"))
        self.assertIn("12 Ring Road, Ahmedabad", a["location"])                              # folded line joined
        self.assertEqual((b["full_name"], b["mobile_number"]), ("Neha Shah", "+91 98250 22222"))
        self.assertEqual(c["status"], "duplicate")
        with self.assertRaises(ValueError):
            parse("e.vcf", "nothing here")


EML = """From: "Kiran Mehta" <kiran@qa-theta.in>
Subject: Quotation for website
Content-Type: text/plain; charset=utf-8

Hello.

Regards,
Kiran Mehta
QA Theta Technologies Pvt Ltd
+91 98250 66666
www.qa-theta.in
"""


class Mail(unittest.TestCase):
    def test_eml(self):
        x = parse("q.eml", EML)["results"][0]
        self.assertEqual((x["full_name"], x["email"], x["company_name"], x["mobile_number"], x["website"]),
                         ("Kiran Mehta", "kiran@qa-theta.in", "QA Theta Technologies Pvt Ltd", "+91 98250 66666", "www.qa-theta.in"))
        self.assertIn("Quotation", x["description"])

    def test_mbox_skips_noreply(self):
        mbox = ("From a@b Thu Nov 12 10:00:00 2026\n" + EML + "\nFrom n@b Thu Nov 12 10:00:00 2026\nFrom: noreply@qa-shop.in\n"
                "Subject: Order\n\nThanks\n\nFrom c@d Thu Nov 12 10:00:00 2026\nFrom: Priya Rao <priya@qa-iota.in>\nSubject: Hi\n\n"
                "Priya Rao\nQA Iota Studio\n98250 77777\n")
        r = parse("in.mbox", mbox)
        self.assertEqual([x["email"] for x in r["results"]], ["kiran@qa-theta.in", "priya@qa-iota.in"])
        with self.assertRaises(ValueError):
            parse("n.eml", "From: noreply@qa-shop.in\nSubject: x\n\nhi\n")


class Pdf(unittest.TestCase):
    def test_text_pdf(self):
        r = parse("b.pdf", pdf_with_text(["QA Lambda Packaging Pvt Ltd", "Contact: 98250 99999", "lambda@qa-lambda.in"]))
        x = r["results"][0]
        self.assertEqual((x["line"], x["company_name"], x["email"], x["mobile_number"]),
                         ("page 1 · 1", "QA Lambda Packaging Pvt Ltd", "lambda@qa-lambda.in", "+91 98250 99999"))

    def test_scanned_and_broken(self):
        with self.assertRaises(ValueError) as cm:
            parse("s.pdf", pdf_with_text([]))
        self.assertIn("no text layer", str(cm.exception).lower())
        with self.assertRaises(ValueError):
            parse("x.pdf", b"%PDF-1.4 garbage")


class TextAndImages(unittest.TestCase):
    def test_txt_and_html(self):
        r = parse("n.txt", "Met at expo:\n\nQA Kappa Traders\nVikas Shah\n98250 88888\nvikas@qa-kappa.in\n\nno contact here\n")
        self.assertEqual([(x["company_name"], x["full_name"]) for x in r["results"]], [("QA Kappa Traders", "Vikas Shah")])
        with self.assertRaises(ValueError):
            parse("e.txt", "nothing useful")

    def test_image_without_ocr(self):
        with mock.patch.object(fu, "ocr_status", return_value={"available": False, "reason": "Tesseract is not installed"}):
            with self.assertRaises(ValueError) as cm:
                parse("card.jpg", b"\xff\xd8\xff")
        self.assertIn("tesseract", str(cm.exception).lower())

    def test_image_with_ocr(self):
        with mock.patch.object(fu, "image_text", return_value="Neha Shah\nQA Beta Studio\n98250 22222\nneha@qa-beta.in"):
            x = parse("card.png", b"png")["results"][0]
        self.assertEqual((x["line"], x["company_name"], x["full_name"]), ("card 1", "QA Beta Studio", "Neha Shah"))


class Normaliser(unittest.TestCase):
    def test_multi_level_email_domains(self):
        self.assertEqual(ln.normalize_email("Amit@QA-Gamma.co.in"), "amit@qa-gamma.co.in")
        self.assertEqual(ln.normalize_email("hr@mail.acme.org.in"), "hr@mail.acme.org.in")
        self.assertEqual(ln.normalize_email("user@acme..in"), "")


class Api(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.app = app_module
        self.client = app_module.app.test_client()
        ok = SimpleNamespace(status_code=200, json=lambda: {"email": "owner@example.com"})
        self.tmp = tempfile.TemporaryDirectory()
        self.p = [mock.patch("api_auth.requests.get", return_value=ok), mock.patch("api_auth.ALLOWED_EMAILS", set()),
                  mock.patch.object(hcm, "CACHE_DIR", self.tmp.name),
                  mock.patch.object(self.app, "MASTER_PATH", os.path.join(self.tmp.name, "m.csv"))]
        for x in self.p:
            x.start()
        self.h = {"Authorization": "Bearer t"}

    def tearDown(self):
        for x in self.p:
            x.stop()
        self.tmp.cleanup()

    def test_endpoints(self):
        self.assertEqual(self.client.get("/api/file-uploads").status_code, 401)
        self.assertEqual(self.client.post("/api/file-uploads/parse", json={}).status_code, 401)
        cat = self.client.get("/api/file-uploads", headers=self.h).get_json()
        self.assertIn(".pdf", cat["types"])
        self.assertNotIn("exe", cat["ocr"])
        self.assertEqual(self.client.post("/api/file-uploads/parse", headers=self.h, json={"name": "a.exe", "data": "eA=="}).status_code, 400)
        r = self.client.post("/api/file-uploads/parse", headers=self.h, json={"name": "q.eml", "data": b64(EML)}).get_json()
        self.assertEqual(r["counts"]["new"], 1)
        sv = self.client.post("/api/bulk-contacts/save", headers=self.h, json={"kind": "import", "rows": r["results"]}).get_json()
        self.assertEqual(sv["added"], 1)
        again = self.client.post("/api/file-uploads/parse", headers=self.h, json={"name": "q.eml", "data": b64(EML)}).get_json()
        self.assertEqual(again["counts"]["in_leads"], 1)
        big = self.client.post("/api/file-uploads/parse", headers=self.h, data="x" * (16 * 1024 * 1024), content_type="application/json")
        self.assertEqual(big.status_code, 400)


if __name__ == "__main__":
    unittest.main()
