"""Pure-function tests for the tier 1/2/3 job-matching helpers (no DB)."""
from server.web.features.profile import job_matching as jm


# ── matches_core (tier 1, hard) ──────────────────────────────────────────────

def test_matches_core_no_bounds_passes_everything():
    assert jm.matches_core({"yearsexperience": 12}, {"min_experience": None, "max_experience": None})


def test_matches_core_missing_experience_always_passes():
    core = {"min_experience": 3, "max_experience": 5}
    assert jm.matches_core({"yearsexperience": ""}, core)
    assert jm.matches_core({"yearsexperience": None}, core)
    assert jm.matches_core({}, core)


def test_matches_core_enforces_both_bounds():
    core = {"min_experience": 2, "max_experience": 5}
    assert not jm.matches_core({"yearsexperience": 1}, core)
    assert jm.matches_core({"yearsexperience": 2}, core)
    assert jm.matches_core({"yearsexperience": 5}, core)
    assert not jm.matches_core({"yearsexperience": 6}, core)


# ── apply_preferences (tier 2, soft w/ auto-relax) ───────────────────────────

def _hit(loc="", sen=""):
    return {"metadata": {"location": loc, "seniority": sen}}


def test_apply_preferences_noop_when_nothing_set():
    hits = [_hit("Center"), _hit("North")]
    assert jm.apply_preferences(hits, jm._PREF_DEFAULT, 5) is hits


def test_apply_preferences_filters_by_location_when_plentiful():
    prefs = {"preferred_locations": ["Center"], "preferred_seniority": [], "remote_only": False}
    hits = [_hit("Center Tel Aviv"), _hit("North"), _hit("Center"), _hit("South")]
    out = jm.apply_preferences(hits, prefs, want_n=2)
    assert [h["metadata"]["location"] for h in out] == ["Center Tel Aviv", "Center"]


def test_apply_preferences_auto_relaxes_when_too_few_match():
    prefs = {"preferred_locations": ["Center"], "preferred_seniority": [], "remote_only": False}
    hits = [_hit("Center"), _hit("North"), _hit("South")]
    out = jm.apply_preferences(hits, prefs, want_n=3)  # only 1 matches < 3
    assert out is hits


def test_apply_preferences_remote_only():
    prefs = {"preferred_locations": [], "preferred_seniority": [], "remote_only": True}
    hits = [_hit("Remote"), _hit("Center"), _hit("Fully Remote")]
    out = jm.apply_preferences(hits, prefs, want_n=2)
    assert {h["metadata"]["location"] for h in out} == {"Remote", "Fully Remote"}


# ── skill_rank (tier 3, ranking) ────────────────────────────────────────────

def test_skill_rank_counts_overlap_across_must_and_nice():
    meta = {"skills_must": "Python, SQL", "skills_nice": "Airflow, dbt"}
    assert jm.skill_rank(meta, ["python", "AIRFLOW", "rust"]) == 2
    assert jm.skill_rank(meta, []) == 0
    assert jm.skill_rank({}, ["python"]) == 0


# ── query_text / summarize / has_signal ─────────────────────────────────────

def _profile(**kw):
    base = {
        "core": dict(jm._CORE_DEFAULT),
        "preferences": {k: (list(v) if isinstance(v, list) else v) for k, v in jm._PREF_DEFAULT.items()},
        "skills": [], "soft_skills": [], "education": {}, "career_stage": None, "active_resume_id": None,
    }
    base.update(kw)
    return base


def test_query_text_combines_roles_skills_and_field_of_study():
    p = _profile(
        preferences={**jm._PREF_DEFAULT, "preferred_roles": ["Data Scientist"]},
        skills=["Python"],
        education={"field_of_study": "Statistics"},
    )
    assert jm.query_text(p) == "Data Scientist, Python, Statistics"


def test_query_text_falls_back_to_space():
    assert jm.query_text(_profile()) == " "


def test_has_signal():
    assert not jm.has_signal(_profile())
    assert jm.has_signal(_profile(skills=["Python"]))
    assert jm.has_signal(_profile(preferences={**jm._PREF_DEFAULT, "preferred_roles": ["Backend"]}))


def test_summarize_for_prompt_mentions_set_fields():
    p = _profile(
        core={"min_experience": 0, "max_experience": 4, "education_level": "bachelor"},
        preferences={**jm._PREF_DEFAULT, "preferred_locations": ["Center"], "remote_only": True},
        skills=["Python", "SQL"],
    )
    s = jm.summarize_for_prompt(p)
    assert "Center" in s and "remote only" in s and "0–4 yrs" in s and "bachelor" in s and "Python" in s


def test_summarize_for_prompt_empty():
    assert jm.summarize_for_prompt(_profile()) == "no saved job profile"
