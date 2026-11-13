"""API robustness sweep against the SANDBOX backend (port 5055). Never point this at port 5000."""
import json, re, sys, time
import requests

BASE = "http://127.0.0.1:5055"
H = {"X-Demo-User": "true"}
APP = sys.argv[1]

SKIP = {"/api/scraper/start", "/api/scheduler/trigger", "/api/sync-supabase", "/api/scraper/stop"}
routes = []
src = open(APP, encoding="utf-8").read()
for m in re.finditer(r'@app\.route\("([^"]+)"(?:,\s*methods=\[([^\]]+)\])?\)', src):
    path, methods = m.group(1), m.group(2)
    methods = [x.strip().strip('"') for x in methods.split(",")] if methods else ["GET"]
    routes.append((path, methods))

def fill(path):
    return (path.replace("<lead_id>", "LEAD-99999999").replace("<activity_id>", "nope")
                .replace("<tool>", "nope"))

BAD = [
    ("empty-json", dict(json={})),
    ("no-body", dict()),
    ("not-json", dict(data="this is not json", headers={"Content-Type": "application/json"})),
    ("json-array", dict(json=[1, 2, 3])),
    ("json-null", dict(data="null", headers={"Content-Type": "application/json"})),
    ("wrong-types", dict(json={k: 12345 for k in (
        "keywords keyword query q titles state portals sources url urls domain domains text leads jobs items "
        "results changes lead_ids lead_id emails phones rows file name city location status to subject message "
        "limit pages depth type summary due_at action templates missing category platform country").split()})),
    ("nested-junk", dict(json={k: {"a": [None, {"b": "<script>alert(1)</script>"}]} for k in (
        "keywords keyword query titles state portals sources url urls domain domains text leads jobs items "
        "results changes lead_ids emails phones rows").split()})),
    ("form-encoded", dict(data={"x": "1"})),
]

out = []
def rec(**k):
    out.append(k)
    flag = "  <<<" if k.get("problem") else ""
    print(f'{k["method"]:6} {k["path"]:48} {k["case"]:14} {k["status"]} {k["ms"]:>6}ms {k.get("problem","")}{flag}', flush=True)

def call(method, path, case, **kw):
    hdr = dict(H); hdr.update(kw.pop("headers", {}) or {})
    t = time.time()
    try:
        r = requests.request(method, BASE + path, headers=hdr, timeout=45, **kw)
    except Exception as e:
        rec(method=method, path=path, case=case, status="ERR", ms=int((time.time() - t) * 1000), problem=type(e).__name__)
        return None
    ms = int((time.time() - t) * 1000)
    problem = ""
    ctype = r.headers.get("Content-Type", "")
    if r.status_code >= 500:
        problem = f"HTTP {r.status_code}: {r.text[:160]!r}"
    elif r.status_code in (400, 404, 405, 409, 413, 415, 422) and "json" not in ctype and path.startswith("/api/") and path != "/api/export-csv":
        problem = f"non-JSON error body ({ctype.split(';')[0]}): {r.text[:80]!r}"
    elif r.status_code == 200 and case not in ("ok",) and method != "GET":
        try:
            j = r.json()
            if isinstance(j, dict) and j.get("success") is True:
                problem = f"accepted bad input: {json.dumps(j)[:140]}"
        except Exception:
            pass
    rec(method=method, path=path, case=case, status=r.status_code, ms=ms, problem=problem)
    return r

# 1. auth: every /api route must 401 without credentials
for path, methods in routes:
    if not path.startswith("/api/"):
        continue
    for m in methods:
        t = time.time()
        r = requests.request(m, BASE + fill(path), timeout=20)
        rec(method=m, path=path, case="no-auth", status=r.status_code, ms=int((time.time() - t) * 1000),
            problem="" if r.status_code == 401 else f"expected 401, got {r.status_code}")
r = requests.get(BASE + "/api/leads", headers={"Authorization": "Bearer forged.token.value"}, timeout=20)
rec(method="GET", path="/api/leads", case="forged-token", status=r.status_code, ms=0,
    problem="" if r.status_code == 401 else "forged token accepted")

# 2. GETs with auth
for path, methods in routes:
    if "GET" in methods and path.startswith("/api/"):
        call("GET", fill(path), "ok")

# 3. bad input on every write route
for path, methods in routes:
    if path in SKIP or path == "/api/settings":
        continue
    for m in methods:
        if m in ("POST", "PATCH", "PUT"):
            for case, kw in BAD:
                call(m, fill(path), case, **{k: (dict(v) if isinstance(v, dict) else v) for k, v in kw.items()})

json.dump(out, open(sys.argv[2], "w"), indent=1)
bad = [o for o in out if o.get("problem")]
print(f"\nTOTAL {len(out)} calls, {len(bad)} flagged")
