"""find_jobs_for_me: core hard-excludes, preferences relax, skills rank (no real DB)."""
import pytest

from server.web.agents.data import db_tools
from server.web.features.profile import job_matching


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=None):
        ids = params[0] if params else []
        self._out = [r for r in self._rows if r["id"] in set(ids)]

    def fetchall(self):
        return self._out

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self, *a, **k):
        return _FakeCursor(self._rows)

    def close(self):
        pass


def _hit(jid, ye="", loc="", sen="", must="", nice=""):
    return {"metadata": {
        "job_id": jid, "yearsexperience": ye, "location": loc,
        "seniority": sen, "skills_must": must, "skills_nice": nice,
    }}


@pytest.fixture
def wired(monkeypatch):
    jobs = [{"id": f"j{i}", "title": f"T{i}", "company": "C", "role": "R",
             "location": "L", "url": "u", "description": "d"} for i in range(1, 9)]
    monkeypatch.setitem(db_tools._context, "user_id", 42)
    monkeypatch.setattr(db_tools, "_collection", lambda: object())
    monkeypatch.setattr(db_tools, "_conn", lambda: _FakeConn(jobs))
    return monkeypatch


def _run(n=5):
    return db_tools.find_jobs_for_me.func(n_results=n)


def test_no_user(monkeypatch):
    monkeypatch.setitem(db_tools._context, "user_id", None)
    assert _run()["jobs"] == []


def test_no_profile_signal(wired):
    wired.setattr(job_matching, "build_job_search_profile",
                  lambda uid: job_matching_stub(skills=[], roles=[]))
    out = _run()
    assert out["jobs"] == [] and "note" in out


def job_matching_stub(skills=("Python",), roles=("Backend",), core=None):
    return {
        "core": core or dict(job_matching._CORE_DEFAULT),
        "preferences": {**job_matching._PREF_DEFAULT, "preferred_roles": list(roles)},
        "skills": list(skills), "soft_skills": [], "education": {},
        "career_stage": None, "active_resume_id": 1,
    }


def test_core_hard_excludes_out_of_range(wired):
    wired.setattr(job_matching, "build_job_search_profile",
                  lambda uid: job_matching_stub(core={"min_experience": 0, "max_experience": 3,
                                                      "education_level": None}))
    hits = [_hit("j1", ye=2), _hit("j2", ye=9), _hit("j3", ye="")]
    wired.setattr(db_tools, "chroma_search", lambda *a, **k: hits)
    ids = [j["id"] for j in _run()["jobs"]]
    assert "j2" not in ids and {"j1", "j3"} <= set(ids)


def test_skills_rank_orders_results(wired):
    wired.setattr(job_matching, "build_job_search_profile",
                  lambda uid: job_matching_stub(skills=["Python", "SQL"]))
    hits = [
        _hit("j1", must=""),
        _hit("j2", must="Python, SQL"),
        _hit("j3", must="Python"),
    ]
    wired.setattr(db_tools, "chroma_search", lambda *a, **k: hits)
    ids = [j["id"] for j in _run()["jobs"]]
    assert ids[:2] == ["j2", "j3"]


def test_preferences_relax_when_sparse(wired):
    prof = job_matching_stub()
    prof["preferences"] = {**job_matching._PREF_DEFAULT, "preferred_locations": ["Center"]}
    wired.setattr(job_matching, "build_job_search_profile", lambda uid: prof)
    hits = [_hit("j1", loc="North"), _hit("j2", loc="South")]  # none match Center
    wired.setattr(db_tools, "chroma_search", lambda *a, **k: hits)
    ids = {j["id"] for j in _run()["jobs"]}
    assert ids == {"j1", "j2"}  # relaxed rather than empty
