from server.etl.skills import (
    _ALIASES,
    _CANONICAL,
    expand_skill,
    normalize_skill,
    normalize_skills,
)


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
    assert normalize_skill("rest apis") == "REST APIs"
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
    assert normalize_skill("OIDC") == "OIDC"
    assert normalize_skill("IoT") == "IoT"          # mixed case, not an acronym
    assert normalize_skill("PCIe") == "PCIe"
    assert normalize_skill("AWS Glue") == "AWS Glue"
    assert normalize_skill("NVIDIA Jetson") == "NVIDIA Jetson"


def test_generic_words_are_lower_cased_mid_phrase():
    # the same skill shouted in Title Case must land on the same string
    assert normalize_skill("Distributed Systems") == normalize_skill("distributed systems")
    assert normalize_skill("Design Patterns") == "Design patterns"
    assert normalize_skill("Unit Testing") == "Unit testing"
    assert normalize_skill("Computer Vision") == "Computer vision"
    assert normalize_skill("Object-Oriented Programming") == "OOP"
    assert normalize_skill("Multi-Threading") == "Multithreading"


def test_filler_words_are_stripped():
    # the case the extractor produces most: one language, three spellings
    assert normalize_skill("C") == "C"
    assert normalize_skill("C programming") == "C"
    assert normalize_skill("C development") == "C"
    assert normalize_skill("Python development") == "Python"
    assert normalize_skill("iOS development") == "iOS"
    assert normalize_skill("strong hands-on experience with Kafka") == "Kafka"
    assert normalize_skill("deep understanding of Kubernetes") == "Kubernetes"
    # …but only when a real technology is left over
    assert normalize_skill("Software development") == "Software development"
    assert normalize_skill("Vector databases") == "Vector databases"


def test_filler_adjective_is_not_stripped_from_a_real_name():
    assert normalize_skill("Deep learning") == "Deep learning"
    assert normalize_skill("Deep learning systems") == "Deep learning systems"


def test_versions_and_parentheticals_are_dropped():
    assert normalize_skill("Angular 5+") == "Angular"
    assert normalize_skill(".NET 6+") == ".NET"
    assert normalize_skill("Java 8") == "Java"
    assert normalize_skill("C++17") == "C++"
    assert normalize_skill("Google Cloud Platform (GCP)") == "GCP"
    assert normalize_skill("AWS (specific advantage)") == "AWS"


def test_plural_variants_collapse():
    assert normalize_skill("Code reviews") == normalize_skill("Code review")
    assert normalize_skill("Microservices architectures") == normalize_skill("Microservices architecture")
    assert normalize_skill("Event-driven architectures") == "Event-driven architecture"
    assert normalize_skill("Distributed system") == "Distributed systems"


def test_synonyms_merge():
    assert normalize_skill("K8s") == "Kubernetes"
    assert normalize_skill("Google Cloud") == "GCP"
    assert normalize_skill("Apache Kafka") == "Kafka"
    assert normalize_skill("Backend engineering") == "Backend development"
    assert normalize_skill("Agile methodologies") == "Agile"
    assert normalize_skill("CI/CD pipelines") == "CI/CD"
    assert normalize_skill("Continuous integration") == "CI/CD"
    assert normalize_skill("Microservices architecture") == "Microservices"
    assert normalize_skill("NoSQL databases") == "NoSQL"
    assert normalize_skill("REST API") == "REST APIs"
    assert normalize_skill("ML") == "Machine learning"


def test_compounds_split_into_real_skills():
    assert expand_skill("C/C++") == ["C", "C++"]
    assert expand_skill("AI/ML") == ["AI", "Machine learning"]
    assert expand_skill("Linux/Unix") == ["Linux", "Unix"]
    # names that merely contain a slash stay whole
    assert expand_skill("CI/CD") == ["CI/CD"]
    assert expand_skill("TCP/IP") == ["TCP/IP"]
    assert expand_skill("UI/UX") == ["UI/UX"]


def test_idempotent():
    for s in ("react", "REST APIs", "machine learning", "PyTorch", ".net",
              "DISTRIBUTED SYSTEMS", "sql databases", "OAUTH", "C programming",
              "C/C++", "Agentic AI", "Google Cloud Platform (GCP)", "IoT"):
        once = normalize_skill(s)
        assert once == normalize_skill(once), s


def test_tables_are_self_consistent():
    """Every canonical/alias target must already be in its final form."""
    for table in (_CANONICAL, _ALIASES):
        for key, value in table.items():
            assert normalize_skill(value) == value, f"{key} → {value}"


def test_normalize_skills_dedupes_case_insensitively():
    assert normalize_skills(["React", "react", "REACT", "Redux"]) == ["React", "Redux"]
    assert normalize_skills(["RESTful APIs", "REST APIs"]) == ["REST APIs"]
    assert normalize_skills(["C", "C/C++", "C programming", "C++"]) == ["C", "C++"]
    assert normalize_skills(["Distributed Systems", "distributed systems"]) == ["Distributed systems"]


def test_normalize_skills_drops_blanks_and_non_lists():
    assert normalize_skills(["Python", "", None, "  "]) == ["Python"]
    assert normalize_skills(None) == []
    assert normalize_skills("Python") == []
