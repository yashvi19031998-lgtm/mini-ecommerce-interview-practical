"""Tests for the Job Portal Scraper (job_portals.py + /api/job-portals endpoints). No network.

    python -m unittest test_job_portals -v
"""
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import job_portals as jp
import lead_normalizer as ln


def _resp(status=200, text="", data=None):
    return SimpleNamespace(status_code=status, text=text, json=lambda: data,
                           raise_for_status=lambda: None)


class FakeSession:
    """Returns queued responses for session.get/post and records the calls."""
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)

    post = get


# ---------------------------------------------------------------- helpers
class Helpers(unittest.TestCase):
    def test_location_in_state(self):
        self.assertTrue(jp.location_in_state("Ahmedabad, Gujarat, India", "Gujarat"))
        self.assertTrue(jp.location_in_state("Vadodara, Noida", "Gujarat"))
        self.assertFalse(jp.location_in_state("Hyderabad, Chennai", "Gujarat"))
        self.assertTrue(jp.location_in_state("Hyderabad", jp.ALL_INDIA))
        self.assertFalse(jp.location_in_state("Suratgarh", "Gujarat"))  # word boundary: not "Surat"

    def test_relevance(self):
        self.assertTrue(jp.is_relevant({"title": "Senior ReactJS developer"}, "React Developer"))
        self.assertTrue(jp.is_relevant({"title": "Frontend Developer", "skills": "react, redux"}, "React Developer"))
        self.assertFalse(jp.is_relevant({"title": ".NET Developer", "skills": "c#, azure"}, "React Developer"))
        self.assertFalse(jp.is_relevant({"title": "Inside Sales Contractor"}, "React Developer"))
        self.assertTrue(jp.is_relevant({"title": "Anything"}, "Senior Developer"))  # only generic words
        self.assertTrue(jp.is_relevant({"title": "Node.js Engineer"}, "Node.js Developer"))

    def test_rsc_payload_joins_chunks(self):
        page = ('<script>self.__next_f.push([1,"a:{\\"jobs\\":[{\\"title\\":\\"React Dev\\""])</script>'
                '<script>self.__next_f.push([1,"}]}"])</script>')
        self.assertEqual(jp._next_rsc_payload(page), 'a:{"jobs":[{"title":"React Dev"}]}')


# ---------------------------------------------------------------- validation
class Validation(unittest.TestCase):
    def test_valid_request_is_cleaned(self):
        req = jp.validate_request(["  React Developer ", "react developer", "React Developer", "Python Developer"],
                                  "Gujarat", ["foundit", "shine", "foundit"])
        self.assertEqual(req["titles"], ["React Developer", "react developer", "Python Developer"])
        self.assertEqual(req["portal_ids"], ["foundit", "shine"])

    def test_invalid_requests(self):
        cases = [
            ([], "Gujarat", ["foundit"], "at least one job title"),
            (["  "], "Gujarat", ["foundit"], "at least one job title"),
            ("React", "Gujarat", ["foundit"], "list"),
            ([f"T{i}" for i in range(11)], "Gujarat", ["foundit"], "at most"),
            (["x" * 81], "Gujarat", ["foundit"], "80 characters"),
            (["React"], "Atlantis", ["foundit"], "valid state"),
            (["React"], None, ["foundit"], "valid state"),
            (["React"], "Gujarat", [], "at least one job portal"),
            (["React"], "Gujarat", ["myspace"], "Unknown job portal"),
        ]
        for titles, state, portals, msg in cases:
            with self.subTest(msg=msg, titles=str(titles)[:30]):
                with self.assertRaises(ValueError) as ctx:
                    jp.validate_request(titles, state, portals)
                self.assertIn(msg, str(ctx.exception))

    def test_all_india_allowed(self):
        self.assertEqual(jp.validate_request(["React"], jp.ALL_INDIA, ["shine"])["state"], jp.ALL_INDIA)


# ---------------------------------------------------------------- catalog
class Catalog(unittest.TestCase):
    def test_statuses_and_order(self):
        with mock.patch.dict(os.environ, {"ADZUNA_APP_ID": "", "ADZUNA_APP_KEY": "", "JOOBLE_API_KEY": ""}):
            items = jp.list_portals()
        status = {p["id"]: p["status"] for p in items}
        for pid in ("foundit", "shine", "linkedin", "internshala", "freshersworld", "apna", "instahyre",
                    "remotive", "remoteok", "arbeitnow"):
            self.assertEqual(status[pid], "available", pid)
        self.assertEqual(status["adzuna"], "needs_key")
        self.assertEqual(status["jooble"], "needs_key")
        for pid in ("naukri", "indeed", "glassdoor", "wellfound", "timesjobs", "cutshort", "careerjet", "hirist"):
            self.assertEqual(status[pid], "unavailable", pid)
            self.assertTrue(next(p for p in items if p["id"] == pid)["reason"])
        order = [p["status"] for p in items]
        self.assertEqual(order, sorted(order, key=["available", "needs_key", "unavailable"].index))

    def test_key_makes_api_portal_available(self):
        with mock.patch.dict(os.environ, {"JOOBLE_API_KEY": "k"}):
            self.assertEqual(next(p for p in jp.list_portals() if p["id"] == "jooble")["status"], "available")

    def test_states(self):
        self.assertEqual(len(jp.INDIAN_STATES), 36)  # 28 states + 8 union territories
        self.assertIn("Gujarat", jp.INDIAN_STATES)


# ---------------------------------------------------------------- portal parsers
class Parsers(unittest.TestCase):
    def test_foundit(self):
        data = {"data": [{"title": "React Developer", "company": {"name": "Acme"},
                          "locations": [{"city": "Ahmedabad"}, {"city": "Ahmedabad"}, {"city": "Surat"}],
                          "minimumExperience": {"years": 2}, "maximumExperience": {"years": 5},
                          "minimumSalary": {"absoluteValue": 400000}, "maximumSalary": {"absoluteValue": 800000},
                          "postedAt": 1793000000000, "jdUrl": "/job/react-acme-1",
                          "skills": [{"text": "React"}, {"text": "Redux"}], "description": "<p>Build UI</p>"}]}
        s = FakeSession(_resp(data=data))
        jobs = jp.search_foundit(s, "React Developer", "Gujarat")
        self.assertEqual(s.calls[0][1]["params"]["locations"], "Gujarat")
        j = jobs[0]
        self.assertEqual((j["company"], j["location"], j["experience"]), ("Acme", "Ahmedabad, Surat", "2-5 yrs"))
        self.assertEqual(j["url"], "https://www.foundit.in/job/react-acme-1")
        self.assertEqual(j["salary"], "INR 400,000 - 800,000/yr")
        self.assertEqual(j["description"], "Build UI")
        self.assertTrue(j["posted_at"].startswith("2026-"))

    def test_shine_filters_state_and_dedupes_pages(self):
        jobs_json = json.dumps({"jobs": [
            {"id": "1", "title": "React Developer", "companyName": "A", "locations": ["Ahmedabad"],
             "detailUrl": "/jobs/a/1", "postedAt": "2026-11-03T16:07:52", "skills": ["react"]},
            {"id": "2", "title": "React Developer", "companyName": "B", "locations": ["Hyderabad"],
             "detailUrl": "/jobs/b/2"}]})
        chunk = json.dumps(jobs_json)[1:-1]
        page = f'<script>self.__next_f.push([1,"{chunk}"])</script>'
        s = FakeSession(_resp(text=page), _resp(text=page))
        with mock.patch.object(jp.time, "sleep"):
            jobs = jp.search_shine(s, "React Developer", "Gujarat")
        self.assertEqual([c[0] for c in s.calls], [
            "https://www.shine.com/job-search/react-developer-jobs-in-gujarat",
            "https://www.shine.com/job-search/react-developer-jobs-in-ahmedabad"])
        self.assertEqual([j["company"] for j in jobs], ["A"])  # Hyderabad dropped, page 2 duplicates ignored
        self.assertEqual(jobs[0]["url"], "https://www.shine.com/jobs/a/1")

    def test_shine_layout_change_raises(self):
        with self.assertRaises(jp.PortalError):
            jp.search_shine(FakeSession(_resp(text="<html></html>")), "React", jp.ALL_INDIA)

    def test_internshala(self):
        html = """
        <div class="individual_internship" data-href="/job/detail/react-acme" employment_type="job">
          <a class="job-title-href">React Developer</a><p class="company-name">Acme</p>
          <div class="locations"><span><a>Ahmedabad</a></span></div><span class="stipend">₹ 3,00,000 - 5,00,000</span>
          <div class="about_job"><div class="text">Build apps</div></div><div class="job_skill">React</div></div>
        <div class="individual_internship" data-href="/internship/detail/x" employment_type="internship">
          <a class="job-title-href">React Intern</a><p class="company-name">Beta</p>
          <div class="locations"><span><a>Work from home</a></span></div></div>
        <div class="individual_internship" data-href="/job/detail/y" employment_type="job">
          <a class="job-title-href">React Developer</a><p class="company-name">Gamma</p>
          <div class="locations"><span><a>Pune</a></span></div></div>"""
        jobs = jp.search_internshala(FakeSession(_resp(text=html)), "React Developer", "Gujarat")
        self.assertEqual([j["company"] for j in jobs], ["Acme", "Beta"])  # Pune dropped, WFH kept
        self.assertEqual(jobs[0]["url"], "https://internshala.com/job/detail/react-acme")
        self.assertEqual(jobs[1]["title"], "React Intern (Internship)")
        self.assertEqual(jobs[0]["skills"], "React")

    def test_freshersworld_title_cleanup(self):
        html = """<div class="job-container" job_display_url="https://fw.com/jobs/1">
          <span class="seo_title">Sr. React Developer Jobs Opening in Acme at Ahmedabad<span>Less</span></span>
          <h3 class="company-name">Acme</h3><span class="job-location"><a>Ahmedabad</a></span>
          <span class="experience">0 to 3 Years</span></div>"""
        jobs = jp.search_freshersworld(FakeSession(_resp(text=html)), "React Developer", "Gujarat")
        self.assertEqual(jobs[0]["title"], "Sr. React Developer")
        self.assertEqual((jobs[0]["company"], jobs[0]["experience"]), ("Acme", "0 to 3 Years"))

    def test_linkedin(self):
        html = """<li><a class="base-card__full-link" href="https://in.linkedin.com/jobs/view/1?trk=x"></a>
          <h3 class="base-search-card__title">ReactJS developer</h3><h4 class="base-search-card__subtitle">Acme</h4>
          <span class="job-search-card__location">Rajkot, Gujarat, India</span><time datetime="2026-11-01"></time></li>"""
        s = FakeSession(_resp(text=html))
        jobs = jp.search_linkedin(s, "React Developer", "Gujarat")
        self.assertEqual(s.calls[0][1]["params"]["location"], "Gujarat, India")
        self.assertEqual(jobs[0]["url"], "https://in.linkedin.com/jobs/view/1")  # tracking removed
        self.assertEqual((jobs[0]["company"], jobs[0]["posted_at"]), ("Acme", "2026-11-01"))

    def test_apna(self):
        html = """<a data-testid="job-card" href="/job/ahmedabad/react-1"><div>React Developer</div><div>Acme</div>
          <div>Ahmedabad</div><div>₹25,000 - ₹40,000</div><div>Min. 2 years</div></a>
          <a data-testid="job-card" href="/job/pune/react-2"><div>React Developer</div><div>Beta</div><div>Pune</div></a>"""
        jobs = jp.search_apna(FakeSession(_resp(text=html)), "React Developer", "Gujarat")
        self.assertEqual(len(jobs), 1)
        self.assertEqual((jobs[0]["salary"], jobs[0]["experience"]), ("₹25,000 - ₹40,000", "Min. 2 years"))

    def test_instahyre(self):
        data = {"objects": [{"title": "React Dev", "employer": {"company_name": "Acme"}, "locations": "Ahmedabad",
                             "public_url": "https://instahyre.com/job-1", "keywords": ["React"]},
                            {"title": "React Dev", "employer": {"company_name": "B"}, "locations": "Bangalore",
                             "public_url": "https://instahyre.com/job-2"}]}
        jobs = jp.search_instahyre(FakeSession(_resp(data=data)), "React", "Gujarat")
        self.assertEqual([j["company"] for j in jobs], ["Acme"])

    def test_remote_apis(self):
        remotive = {"jobs": [{"title": "React Engineer", "company_name": "R", "url": "https://r/1",
                              "candidate_required_location": "Worldwide", "publication_date": "2026-11-01T10:00:00"}]}
        self.assertEqual(jp.search_remotive(FakeSession(_resp(data=remotive)), "React", "Gujarat")[0]["location"], "Worldwide")
        remoteok = [{"legal": "notice"}, {"position": "Senior React Dev", "company": "O", "url": "https://o/1",
                                          "salary_min": 50000, "salary_max": 90000},
                    {"position": "Go Dev", "company": "P", "url": "https://p/1"}]
        jobs = jp.search_remoteok(FakeSession(_resp(data=remoteok)), "React Developer", "Gujarat")
        self.assertEqual([j["company"] for j in jobs], ["O"])
        self.assertEqual(jobs[0]["salary"], "USD 50,000 - 90,000")
        arbeit = {"data": [{"title": "React Developer", "company_name": "A", "url": "https://a/1", "remote": True,
                            "created_at": 1793000000}, {"title": "Koch", "company_name": "K", "url": "https://k/1"}]}
        jobs = jp.search_arbeitnow(FakeSession(_resp(data=arbeit)), "React Developer", "Gujarat")
        self.assertEqual((len(jobs), jobs[0]["location"]), (1, "Remote"))

    def test_key_portals_need_keys(self):
        with mock.patch.dict(os.environ, {"ADZUNA_APP_ID": "", "ADZUNA_APP_KEY": "", "JOOBLE_API_KEY": ""}):
            with self.assertRaises(jp.PortalError):
                jp.search_adzuna(FakeSession(), "React", "Gujarat")
            with self.assertRaises(jp.PortalError):
                jp.search_jooble(FakeSession(), "React", "Gujarat")

    def test_adzuna_with_key(self):
        data = {"results": [{"title": "React Dev", "company": {"display_name": "A"},
                             "location": {"display_name": "Ahmedabad, Gujarat"}, "redirect_url": "https://adz/1",
                             "salary_min": 300000, "salary_max": 500000, "created": "2026-11-01T10:00:00Z"}]}
        s = FakeSession(_resp(data=data))
        with mock.patch.dict(os.environ, {"ADZUNA_APP_ID": "id", "ADZUNA_APP_KEY": "key"}):
            jobs = jp.search_adzuna(s, "React", "Gujarat")
        self.assertEqual(s.calls[0][1]["params"]["where"], "Gujarat")
        self.assertEqual(jobs[0]["salary"], "INR 300,000 - 500,000")

    def test_blocked_status_raises_portal_error(self):
        s = FakeSession(_resp(status=406))
        with self.assertRaises(jp.PortalError):
            jp._get(s, "https://example.com")


# ---------------------------------------------------------------- orchestration
class SearchJobs(unittest.TestCase):
    def _job(self, pid, title, url, company="Acme", posted=""):
        return jp.make_job(pid, title=title, company=company, url=url, posted_at=posted, location="Ahmedabad")

    def test_runs_selected_skips_unavailable_and_reports_errors(self):
        def ok(session, title, state):
            return [self._job("foundit", f"{title}", f"https://f/{title}", posted="2026-11-01"),
                    self._job("foundit", ".NET Developer", "https://f/net")]

        def boom(session, title, state):
            raise jp.PortalError("blocked by the site (HTTP 403)")

        with mock.patch.dict(jp.PORTALS["foundit"], {"search": ok}), \
                mock.patch.dict(jp.PORTALS["shine"], {"search": boom}), \
                mock.patch.object(jp.time, "sleep"):
            res = jp.search_jobs(["React Developer", "Python Developer"], "Gujarat", ["foundit", "shine", "naukri"])

        self.assertEqual(res["portals"]["foundit"]["status"], "ok")
        self.assertEqual(res["portals"]["foundit"]["count"], 2)  # .NET results dropped by relevance
        self.assertEqual(res["portals"]["shine"]["status"], "error")
        self.assertEqual(len(res["portals"]["shine"]["errors"]), 2)
        self.assertEqual(res["portals"]["naukri"]["status"], "skipped")
        self.assertEqual(res["total"], 2)
        self.assertEqual({j["searched_title"] for j in res["jobs"]}, {"React Developer", "Python Developer"})

    def test_dedupe_by_url(self):
        jobs = [self._job("foundit", "React", "https://x/1"), self._job("shine", "React", "https://x/1"),
                self._job("shine", "React", "")]
        self.assertEqual(len(jp._dedupe(jobs)), 2)


# ---------------------------------------------------------------- save to leads
class SaveToLeads(unittest.TestCase):
    def test_job_to_raw_lead(self):
        job = jp.make_job("foundit", title="React Developer", company="Acme", location="Ahmedabad",
                          experience="2-5 yrs", url="https://www.foundit.in/job/1", posted_at="2026-11-01 10:00:00")
        raw = jp.job_to_raw_lead(job)
        self.assertEqual(raw["company_name"], "Acme")
        self.assertTrue(raw["description"].startswith("Hiring: React Developer"))
        self.assertEqual(raw["source"], "Job Portal (Foundit (Monster India))")
        self.assertEqual(raw["lead_type"], "Job Posting")

    def test_jobs_from_portals_stay_separate_leads(self):
        """Regression: portal domains must not be treated as company websites (domain dedupe)."""
        with tempfile.TemporaryDirectory() as d:
            reg = ln.MasterLeadRegistry(os.path.join(d, "m.csv"))
            a = reg.add_lead(jp.job_to_raw_lead(jp.make_job("foundit", title="React", company="Acme",
                                                            location="Ahmedabad", url="https://www.foundit.in/job/1")))
            b = reg.add_lead(jp.job_to_raw_lead(jp.make_job("foundit", title="Python", company="Beta",
                                                            location="Surat", url="https://www.foundit.in/job/2")))
            self.assertEqual((a[0], b[0]), ("added", "added"))
            self.assertEqual(reg.leads[0]["website"], "")
            self.assertEqual(len(reg.leads), 2)


# ---------------------------------------------------------------- API endpoints
class Api(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.app_module = app_module
        self.client = app_module.app.test_client()
        ok = SimpleNamespace(status_code=200, json=lambda: {"email": "owner@example.com"})
        self.auth_patch = mock.patch("api_auth.requests.get", return_value=ok)
        self.allow_patch = mock.patch("api_auth.ALLOWED_EMAILS", set())
        self.auth_patch.start()
        self.allow_patch.start()
        self.headers = {"Authorization": "Bearer test-token"}

    def tearDown(self):
        self.auth_patch.stop()
        self.allow_patch.stop()

    def test_requires_login(self):
        self.assertEqual(self.client.get("/api/job-portals").status_code, 401)
        self.assertEqual(self.client.post("/api/job-portals/search", json={}).status_code, 401)
        self.assertEqual(self.client.post("/api/job-portals/save", json={}).status_code, 401)

    def test_catalog(self):
        r = self.client.get("/api/job-portals", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body["states"][0], jp.ALL_INDIA)
        self.assertEqual(len(body["states"]), 37)
        self.assertTrue(any(p["id"] == "naukri" and p["status"] == "unavailable" for p in body["portals"]))

    def test_search_validation_400(self):
        for payload in ({}, {"titles": [], "state": "Gujarat", "portals": ["shine"]},
                        {"titles": ["React"], "state": "Mars", "portals": ["shine"]},
                        {"titles": ["React"], "state": "Gujarat", "portals": []}):
            r = self.client.post("/api/job-portals/search", json=payload, headers=self.headers)
            self.assertEqual(r.status_code, 400, payload)
            self.assertFalse(r.get_json()["success"])
        r = self.client.post("/api/job-portals/search", data="not json", headers=self.headers,
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_search_ok(self):
        fake = {"jobs": [], "total": 0, "portals": {}, "query": {"titles": ["React"], "state": "Gujarat"}}
        with mock.patch.object(jp, "search_jobs", return_value=fake) as s:
            r = self.client.post("/api/job-portals/search", headers=self.headers,
                                 json={"titles": ["React"], "state": "Gujarat", "portals": ["shine"]})
        self.assertEqual(r.status_code, 200)
        s.assert_called_once_with(["React"], "Gujarat", ["shine"])
        self.assertTrue(r.get_json()["success"])

    def test_save_validation_and_write(self):
        self.assertEqual(self.client.post("/api/job-portals/save", json={"jobs": []}, headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post("/api/job-portals/save", json={"jobs": [{"title": "x"}]},
                                          headers=self.headers).status_code, 400)  # no url
        too_many = [{"title": "t", "company": "c", "url": f"https://x/{i}"} for i in range(501)]
        self.assertEqual(self.client.post("/api/job-portals/save", json={"jobs": too_many},
                                          headers=self.headers).status_code, 400)
        with tempfile.TemporaryDirectory() as d:
            master = os.path.join(d, "master.csv")
            jobs = [jp.make_job("shine", title="React Developer", company="Acme", location="Ahmedabad",
                                url="https://www.shine.com/jobs/1"),
                    jp.make_job("shine", title="Python Developer", company="Beta", location="Surat",
                                url="https://www.shine.com/jobs/2")]
            with mock.patch.object(self.app_module, "MASTER_PATH", master):
                r1 = self.client.post("/api/job-portals/save", json={"jobs": jobs}, headers=self.headers)
                r2 = self.client.post("/api/job-portals/save", json={"jobs": jobs}, headers=self.headers)
            self.assertEqual(r1.get_json()["added"], 2)
            self.assertEqual(r2.get_json()["added"], 0)  # saving again does not duplicate
            saved = ln.MasterLeadRegistry(master).leads
            self.assertEqual(len(saved), 2)
            self.assertEqual(saved[0]["lead_type"], "Job Posting")


if __name__ == "__main__":
    unittest.main()
