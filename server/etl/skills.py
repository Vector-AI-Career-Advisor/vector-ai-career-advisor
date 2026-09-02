"""
Skill-string normalisation.

The LLM extractor returns skills in whatever casing the description used —
"react", "React", "REACT", "rest apis", "REST APIs". This module gives every
skill one canonical spelling so PostgreSQL, ChromaDB metadata and the UI all
agree. Kept in sync with the client-side copy in client/src/lib/skills.ts.

The rules are deliberately conservative — a word the model already capitalised
is left untouched — so proper nouns like "DNS", "SaaS", "PyTorch" and phrases
like "Data structures and algorithms" survive intact.
"""
from __future__ import annotations

import re

# Exact spellings for skills whose casing isn't just "capitalise the word":
# tech names, tools, and multi-word terms with fixed casing. Keys are lower-case.
_CANONICAL: dict[str, str] = {
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "node": "Node.js",
    "reactjs": "React",
    "react.js": "React",
    "react": "React",
    "react native": "React Native",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "vue": "Vue.js",
    "angular": "Angular",
    "redux": "Redux",
    "graphql": "GraphQL",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "nosql": "NoSQL",
    "mongodb": "MongoDB",
    "dynamodb": "DynamoDB",
    "redis": "Redis",
    "kafka": "Kafka",
    "elasticsearch": "Elasticsearch",
    "restful apis": "REST APIs",
    "rest apis": "REST APIs",
    "restful api": "REST API",
    "rest api": "REST API",
    "restful": "REST",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "tcp/udp": "TCP/UDP",
    "tcp/ip": "TCP/IP",
    "oauth": "OAuth",
    "grpc": "gRPC",
    "k8s": "K8s",
    "devops": "DevOps",
    "mlops": "MLOps",
    "vxworks": "VxWorks",
    "git": "Git",
    "github": "GitHub",
    "gitlab": "GitLab",
    "jira": "Jira",
    "linux": "Linux",
    "unix": "Unix",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "jenkins": "Jenkins",
    "terraform": "Terraform",
    "ansible": "Ansible",
    "nginx": "nginx",
    "npm": "npm",
    "webpack": "webpack",
    "tcpdump": "tcpdump",
    "ebpf": "eBPF",
    "openai": "OpenAI",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "numpy": "NumPy",
    "pandas": "pandas",
    "scikit-learn": "scikit-learn",
    "matplotlib": "matplotlib",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "spring": "Spring",
    "spring boot": "Spring Boot",
    ".net": ".NET",
    "dotnet": ".NET",
    "c++": "C++",
    "c#": "C#",
    "c/c++": "C/C++",
    "f#": "F#",
    "objective-c": "Objective-C",
    "golang": "Go",
    "kotlin": "Kotlin",
    "scala": "Scala",
    "swift": "Swift",
    "rust": "Rust",
    "ruby": "Ruby",
    "ruby on rails": "Ruby on Rails",
    "html/css": "HTML/CSS",
    "ui/ux": "UI/UX",
    "ms sql": "MS SQL",
    "ms sql server": "MS SQL Server",
    "ibm mq": "IBM MQ",
    "opc ua": "OPC UA",
    "iec 62304": "IEC 62304",
    "soc 2": "SOC 2",
    "iso 13485": "ISO 13485",
    "iso 27001": "ISO 27001",
    "saas": "SaaS",
    "paas": "PaaS",
    "iaas": "IaaS",
    "ios": "iOS",
    "macos": "macOS",
}

# Standalone words to upper-case, mapped to their exact display form so plurals
# like "APIs" / "LLMs" keep the trailing lower-case "s".
_ACRONYMS: dict[str, str] = {
    a: a.upper()
    for a in (
        "ai", "ml", "nlp", "llm", "api", "sdk", "cli", "ui", "ux", "css", "html",
        "sql", "json", "xml", "yaml", "http", "https", "dns", "tcp", "udp", "rest",
        "rpc", "aws", "gcp", "sap", "crm", "erp", "etl", "ci", "cd", "qa",
        "seo", "ssr", "orm", "jwt", "gpu", "cpu", "os", "ide",
        "oop", "tdd", "bdd", "wpf", "sqs", "sns", "rdma", "eda", "cad", "hil",
        "sil", "vpc", "iam", "ssl", "tls", "ssh", "vpn", "cdn", "wcag",
    )
}
_ACRONYMS.update({"apis": "APIs", "llms": "LLMs", "ids": "IDs", "sdks": "SDKs"})

_WS_RE = re.compile(r"\s+")
_UPPER_RE = re.compile(r"[A-Z]")


def normalize_skill(raw: str) -> str:
    """Return the canonical spelling of a single skill string."""
    skill = _WS_RE.sub(" ", str(raw)).strip()
    if not skill:
        return skill

    if skill.lower() in _CANONICAL:
        return _CANONICAL[skill.lower()]

    # A multi-word phrase the model shouted ("DISTRIBUTED SYSTEMS") — fold it so
    # it doesn't stay all-caps. Needs a word of 5+ letters so short all-caps
    # product names ("MS SQL", "AWS EC2") and acronym runs are left alone.
    parts = skill.split(" ")
    if len(parts) > 1 and skill.isupper() and any(len(p) >= 5 for p in parts):
        skill = skill.lower()

    words = skill.split(" ")
    out: list[str] = []
    for i, word in enumerate(words):
        low = word.lower()
        if low in _CANONICAL:
            out.append(_CANONICAL[low])
        elif low in _ACRONYMS:
            out.append(_ACRONYMS[low])
        elif _UPPER_RE.search(word):
            out.append(word)                       # model already cased it
        elif i == 0:
            out.append(low[:1].upper() + low[1:])   # sentence-case the phrase
        else:
            out.append(low)
    return " ".join(out)


def normalize_skills(skills) -> list[str]:
    """
    Normalise a list of skills: canonical spelling, blanks dropped, and
    case-insensitive duplicates collapsed while preserving first-seen order.
    """
    if not isinstance(skills, list):
        return []

    seen: set[str] = set()
    out: list[str] = []
    for raw in skills:
        if not raw:
            continue
        norm = normalize_skill(raw)
        if not norm:
            continue
        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(norm)
    return out
