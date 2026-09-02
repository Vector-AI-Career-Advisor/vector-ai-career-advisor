from server.etl.skills import normalize_skill, normalize_skills


def test_canonical_spellings():
    assert normalize_skill("react") == "React"
    assert normalize_skill("REACT") == "React"
    assert normalize_skill("nodejs") == "Node.js"
    assert normalize_skill("postgres") == "PostgreSQL"
    assert normalize_skill("ci/cd") == "CI/CD"
    assert normalize_skill(".net") == ".NET"
    assert normalize_skill("golang") == "Go"
    assert normalize_skill("OAUTH") == "OAuth"


def test_acronym_tokens_upper_cased():
    assert normalize_skill("aws") == "AWS"
    assert normalize_skill("rest apis") == "REST APIs"           # whole-string canonical
    assert normalize_skill("sql databases") == "SQL databases"   # token fix, rest untouched
    assert normalize_skill("llms in production") == "LLMs in production"


def test_conservative_casing():
    # plain phrases get sentence case, not Title Case
    assert normalize_skill("machine learning") == "Machine learning"
    assert normalize_skill("  data   pipelines  ") == "Data pipelines"
    assert normalize_skill("data structures and algorithms") == "Data structures and algorithms"
    # a shouted multi-word phrase is folded
    assert normalize_skill("DISTRIBUTED SYSTEMS") == "Distributed systems"


def test_words_the_model_already_cased_are_left_alone():
    assert normalize_skill("PyTorch") == "PyTorch"
    assert normalize_skill("GraphQL") == "GraphQL"
    assert normalize_skill("DNS") == "DNS"
    assert normalize_skill("SaaS") == "SaaS"
    assert normalize_skill("TCP/UDP communication protocols") == "TCP/UDP communication protocols"
    assert normalize_skill("OIDC") == "OIDC"


def test_idempotent():
    for s in ("react", "REST APIs", "machine learning", "PyTorch", ".net",
              "DISTRIBUTED SYSTEMS", "sql databases", "OAUTH"):
        once = normalize_skill(s)
        assert once == normalize_skill(once), s


def test_normalize_skills_dedupes_case_insensitively():
    assert normalize_skills(["React", "react", "REACT", "Redux"]) == ["React", "Redux"]
    assert normalize_skills(["RESTful APIs", "REST APIs"]) == ["REST APIs"]


def test_normalize_skills_drops_blanks_and_non_lists():
    assert normalize_skills(["Python", "", None, "  "]) == ["Python"]
    assert normalize_skills(None) == []
    assert normalize_skills("Python") == []
