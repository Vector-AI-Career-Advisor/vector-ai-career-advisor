"""
Skill-string normalisation.

The LLM extractor returns the same skill in many shapes — different casing
("react" / "React" / "REACT"), different verbosity ("C" / "C programming" /
"C development"), plurals ("Code review" / "Code reviews"), versions
("Angular 5+"), and compounds ("C/C++"). This module folds all of those onto
one canonical spelling so PostgreSQL, ChromaDB metadata, the skill filter and
the stats charts all agree. Kept in sync with client/src/lib/skills.ts.

The pipeline, in order (see `_resolve`):

1.  clean       — whitespace, quotes, trailing punctuation, "(parentheticals)"
2.  prefix trim — "experience with X", "strong X", "knowledge of X" → "X"
3.  alias       — explicit synonym table ("k8s" → "Kubernetes")
4.  suffix trim — "<known tech> development/programming/tools/…" → "<tech>",
                  and a trailing version ("Angular 5+" → "Angular")
5.  recase      — canonical spellings, acronyms upper-cased, generic words
                  lower-cased mid-phrase ("Distributed Systems" → "…systems")
6.  last word   — one preferred number per generic head noun
                  ("Microservices architectures" → "…architecture")

Steps 3-6 run to a fixed point, so `normalize_skill` is idempotent — the
backfill can be re-run safely and re-scraped jobs never drift.

Casing stays conservative outside the whitelists: a word the model already
capitalised is left alone, so "PyTorch", "SaaS", "AWS Glue" survive intact.
Multi-word product names whose second word is a generic noun ("Entity
Framework", "Visual Studio") must be listed in `_CANONICAL`, which is checked
as a whole phrase before any of the generic rules run.
"""
from __future__ import annotations

import re

# ── Canonical spellings ──────────────────────────────────────────────────────
# Exact display form for skills whose casing isn't just "capitalise the word",
# plus the multi-word product names that must bypass the generic rules below.
# Keys are lower-case; matched both as a whole phrase and per word.
_CANONICAL: dict[str, str] = {
    # languages
    "c": "C",
    "c++": "C++",
    "c#": "C#",
    "f#": "F#",
    "go": "Go",
    "golang": "Go",
    "rust": "Rust",
    "ruby": "Ruby",
    "scala": "Scala",
    "swift": "Swift",
    "kotlin": "Kotlin",
    "java": "Java",
    "python": "Python",
    "perl": "Perl",
    "php": "PHP",
    "bash": "Bash",
    "matlab": "MATLAB",
    "objective-c": "Objective-C",
    "objective c": "Objective-C",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "assembly": "Assembly",
    "verilog": "Verilog",
    "vhdl": "VHDL",
    # web / frontend
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
    "jquery": "jQuery",
    "material ui": "Material UI",
    "tailwind": "Tailwind CSS",
    "tailwind css": "Tailwind CSS",
    # data stores
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "nosql": "NoSQL",
    "mongodb": "MongoDB",
    "dynamodb": "DynamoDB",
    "redis": "Redis",
    "kafka": "Kafka",
    "elasticsearch": "Elasticsearch",
    "opensearch": "OpenSearch",
    "clickhouse": "ClickHouse",
    "cassandra": "Cassandra",
    "couchbase": "Couchbase",
    "aerospike": "Aerospike",
    "memcached": "Memcached",
    "neo4j": "Neo4j",
    "snowflake": "Snowflake",
    "bigquery": "BigQuery",
    "redshift": "Redshift",
    "databricks": "Databricks",
    "sql server": "SQL Server",
    "delta lake": "Delta Lake",
    # protocols / APIs
    "rest": "REST APIs",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "tcp/udp": "TCP/UDP",
    "tcp/ip": "TCP/IP",
    "http/s": "HTTP/S",
    "oauth": "OAuth",
    "grpc": "gRPC",
    "soap": "SOAP",
    "mqtt": "MQTT",
    "amqp": "AMQP",
    "webhooks": "Webhooks",
    "websockets": "WebSockets",
    # infra / ops
    "k8s": "Kubernetes",
    "devops": "DevOps",
    "mlops": "MLOps",
    "vxworks": "VxWorks",
    "git": "Git",
    "github": "GitHub",
    "gitlab": "GitLab",
    "github actions": "GitHub Actions",
    "github copilot": "GitHub Copilot",
    "azure devops": "Azure DevOps",
    "jira": "Jira",
    "linux": "Linux",
    "unix": "Unix",
    "windows": "Windows",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "jenkins": "Jenkins",
    "terraform": "Terraform",
    "ansible": "Ansible",
    "helm": "Helm",
    "argocd": "ArgoCD",
    "prometheus": "Prometheus",
    "grafana": "Grafana",
    "nginx": "nginx",
    "npm": "npm",
    "webpack": "webpack",
    "tcpdump": "tcpdump",
    "wireshark": "Wireshark",
    "ebpf": "eBPF",
    "qemu": "QEMU",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "aws glue": "AWS Glue",
    "aws bedrock": "AWS Bedrock",
    "aws lambda": "AWS Lambda",
    "visual studio": "Visual Studio",
    "visual studio code": "VS Code",
    "vs code": "VS Code",
    "django rest framework": "Django REST Framework",
    "entity framework": "Entity Framework",
    "windows services": "Windows Services",
    "stored procedures": "Stored Procedures",
    "web services": "Web Services",
    "active directory": "Active Directory",
    "linux kernel": "Linux kernel",
    # AI / ML
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "claude": "Claude",
    "claude code": "Claude Code",
    "cursor": "Cursor",
    "gemini": "Gemini",
    "chatgpt": "ChatGPT",
    "codex": "Codex",
    "copilot": "GitHub Copilot",
    "azure openai": "Azure OpenAI",
    "azure openai service": "Azure OpenAI",
    "claude agent sdk": "Claude Agent SDK",
    "anthropic claude agent sdk": "Claude Agent SDK",
    "openai agents sdk": "OpenAI Agents SDK",
    "openai api": "OpenAI API",
    "langchain": "LangChain",
    "langgraph": "LangGraph",
    "llamaindex": "LlamaIndex",
    "crewai": "CrewAI",
    "autogen": "AutoGen",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "numpy": "NumPy",
    "pandas": "pandas",
    "scikit-learn": "scikit-learn",
    "matplotlib": "matplotlib",
    "opencv": "OpenCV",
    "cuda": "CUDA",
    "vllm": "vLLM",
    "pydantic": "Pydantic",
    "pytest": "pytest",
    # backend frameworks
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "spring": "Spring",
    "spring boot": "Spring Boot",
    "spring security": "Spring Security",
    "play framework": "Play Framework",
    "elastic stack": "Elastic Stack",
    "nestjs": "NestJS",
    "express": "Express",
    "ruby on rails": "Ruby on Rails",
    "asp.net": "ASP.NET",
    ".net": ".NET",
    "dotnet": ".NET",
    "rabbitmq": "RabbitMQ",
    "airflow": "Airflow",
    "spark": "Spark",
    "flink": "Flink",
    "pyspark": "PySpark",
    "selenium": "Selenium",
    "playwright": "Playwright",
    # standards / platforms
    "ms sql": "SQL Server",
    "ms sql server": "SQL Server",
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
    "android": "Android",
    "flutter": "Flutter",
    "unity": "Unity",
}

# Standalone words to upper-case, mapped to their exact display form so plurals
# like "APIs" / "LLMs" keep the trailing lower-case "s".
_ACRONYMS: dict[str, str] = {
    a: a.upper()
    for a in (
        "ai", "nlp", "api", "sdk", "cli", "ui", "ux", "css", "html",
        "sql", "json", "xml", "yaml", "http", "https", "dns", "tcp", "udp", "rest",
        "rpc", "aws", "gcp", "sap", "crm", "erp", "etl", "ci", "cd", "qa",
        "seo", "ssr", "orm", "jwt", "gpu", "cpu", "os", "ide", "rag", "mcp",
        "oop", "tdd", "bdd", "wpf", "sqs", "sns", "rdma", "eda", "cad", "hil",
        "sil", "vpc", "iam", "ssl", "tls", "ssh", "vpn", "cdn", "wcag", "rtos",
        "fpga", "asic", "dsp", "usb", "uart", "pcie", "iot", "sdlc", "solid",
    )
}
_ACRONYMS.update({"apis": "APIs", "llms": "LLMs", "ids": "IDs", "sdks": "SDKs"})

# ── Synonym table ────────────────────────────────────────────────────────────
# Variant (lower-case, after prefix trimming) → the canonical skill it means.
# Values are fed back through the pipeline, so they only need to be spelled the
# way a human would write them. This is where genuinely different wordings get
# merged; the generic rules below handle casing, plurals and filler words.
_ALIASES: dict[str, str] = {
    # ── languages & runtimes ─────────────────────────────────────────────────
    "c language": "C",
    "ansi c": "C",
    "embedded c": "C",
    "modern c++": "C++",
    "c++11": "C++",
    "c++14": "C++",
    "c++17": "C++",
    "c++20": "C++",
    "c++/stl": "C++",
    "stl": "C++",
    "c#.net": "C#",
    "c# .net": "C#",
    ".net core": ".NET",
    ".net framework": ".NET",
    ".net desktop application development": ".NET",
    "asp.net core": "ASP.NET",
    "asp.net web api": "ASP.NET",
    "asp.net mvc": "ASP.NET",
    "js": "JavaScript",
    "ts": "TypeScript",
    "es6": "JavaScript",
    "es2015": "JavaScript",
    "ecmascript": "JavaScript",
    "html5": "HTML",
    "css3": "CSS",
    "sass": "SASS",
    "scss": "SASS",
    "angularjs": "Angular",
    "python3": "Python",
    "go lang": "Go",
    "shell": "Bash",
    "shell scripting": "Bash",
    "bash scripting": "Bash",
    "powershell scripting": "PowerShell",
    # ── clouds & vendors ─────────────────────────────────────────────────────
    "amazon web services": "AWS",
    "google cloud": "GCP",
    "google cloud platform": "GCP",
    "microsoft azure": "Azure",
    "aws s3": "S3",
    "amazon s3": "S3",
    "aws sqs": "SQS",
    "aws sns": "SNS",
    "aws ec2": "EC2",
    "apache kafka": "Kafka",
    "apache spark": "Spark",
    "apache airflow": "Airflow",
    "apache flink": "Flink",
    "apache tomcat": "Tomcat",
    "ms sql db": "SQL Server",
    "mssql": "SQL Server",
    "microsoft sql server": "SQL Server",
    "t-sql": "SQL Server",
    "kubernetes (k8s)": "Kubernetes",
    "k8s operators": "Kubernetes",
    "kubernetes operators": "Kubernetes",
    # ── AI / ML ──────────────────────────────────────────────────────────────
    "artificial intelligence": "AI",
    "ml": "Machine learning",
    "machine learning (ml)": "Machine learning",
    "ai/ml": "Machine learning",
    "deep learning": "Deep learning",
    "llm": "LLMs",
    "large language models": "LLMs",
    "large language models (llms)": "LLMs",
    "llm apis": "LLMs",
    "llm integration": "LLMs",
    "natural language processing": "NLP",
    "computer vision (cv)": "Computer vision",
    "generative ai": "Generative AI",
    "genai": "Generative AI",
    "gen ai": "Generative AI",
    "retrieval augmented generation": "RAG",
    "retrieval-augmented generation": "RAG",
    "model context protocol": "MCP",
    "agent-to-agent protocol": "A2A",
    "ai agents": "AI agents",
    "agentic ai": "AI agents",
    "autonomous agents": "AI agents",
    "agentic systems": "AI agents",
    "agentic architectures": "AI agents",
    "agent frameworks": "AI agent frameworks",
    "agentic frameworks": "AI agent frameworks",
    "agentic ai frameworks": "AI agent frameworks",
    "agentic workflows": "AI agent workflows",
    "agentic flows": "AI agent workflows",
    "agent orchestration": "AI agent workflows",
    "ai agent orchestration": "AI agent workflows",
    "ai coding tools": "AI coding tools",
    "ai coding": "AI coding tools",
    "ai coding agents": "AI coding tools",
    "ai development tools": "AI coding tools",
    "ai-assisted coding tools": "AI coding tools",
    "ai-assisted development": "AI coding tools",
    "ai-assisted development tools": "AI coding tools",
    "ai-assisted software development": "AI coding tools",
    "ai-assisted development workflows": "AI coding tools",
    "ai-powered development tools": "AI coding tools",
    "ai-powered developer tools": "AI coding tools",
    "ai-native coding tools": "AI coding tools",
    "ai-driven development": "AI coding tools",
    "ai-first development": "AI coding tools",
    "ai-assisted workflows": "AI coding tools",
    "ai code assistance tools": "AI coding tools",
    "ai-assisted coding": "AI coding tools",
    "agentic coding": "AI coding tools",
    "vector db": "Vector databases",
    "vector stores": "Vector databases",
    "embeddings": "Embeddings",
    # ── architecture & systems ───────────────────────────────────────────────
    "distributed computing": "Distributed systems",
    "distributed systems design": "Distributed systems",
    "distributed architecture": "Distributed systems",
    "micro-services": "Microservices",
    "microservices architecture": "Microservices",
    "microservices architecture design": "Microservices",
    "microservice architecture": "Microservices",
    "software design": "Software architecture",
    "software design and architecture": "Software architecture",
    "software architecture design": "Software architecture",
    "architecture": "Software architecture",
    "architecture design": "Software architecture",
    "system architecture": "Software architecture",
    "software design principles": "Software design principles",
    "design principles": "Software design principles",
    "solid principles": "SOLID",
    "scalable system design": "System design",
    "scalable systems design": "System design",
    "large-scale system architecture": "System design",
    "large-scale systems": "Scalable systems",
    "high-scale systems": "Scalable systems",
    "scalable systems": "Scalable systems",
    "scalability": "Scalable systems",
    "event driven architecture": "Event-driven architecture",
    "event-driven systems": "Event-driven architecture",
    "cloud native architecture": "Cloud-native architecture",
    "cloud-native technologies": "Cloud-native architecture",
    "serverless architecture": "Serverless",
    "object oriented programming": "OOP",
    "object-oriented programming": "OOP",
    "object-oriented design": "OOP",
    "object oriented design": "OOP",
    "object-oriented analysis and design": "OOP",
    "ood": "OOP",
    "design patterns": "Design patterns",
    "async design patterns": "Design patterns",
    # ── domains ──────────────────────────────────────────────────────────────
    "back-end development": "Backend development",
    "backend engineering": "Backend development",
    "backend software development": "Backend development",
    "backend software engineering": "Backend development",
    "backend programming": "Backend development",
    "backend server programming": "Backend development",
    "backend/server-side development": "Backend development",
    "server-side development": "Backend development",
    "backend services": "Backend development",
    "backend systems": "Backend development",
    "front-end development": "Frontend development",
    "front end development": "Frontend development",
    "back end development": "Backend development",
    "frontend engineering": "Frontend development",
    "front-end engineering": "Frontend development",
    "client-side development": "Frontend development",
    "full stack": "Full-stack development",
    "fullstack": "Full-stack development",
    "full stack development": "Full-stack development",
    "fullstack development": "Full-stack development",
    "full-stack engineering": "Full-stack development",
    "software engineering": "Software development",
    "software development life cycle": "SDLC",
    "web application development": "Web development",
    "web applications": "Web development",
    "mobile app development": "Mobile development",
    "mobile application development": "Mobile development",
    "embedded software": "Embedded systems",
    "embedded development": "Embedded systems",
    "embedded programming": "Embedded systems",
    "embedded software development": "Embedded systems",
    "embedded systems development": "Embedded systems",
    "firmware": "Firmware development",
    "kernel development": "Linux kernel",
    "linux kernel development": "Linux kernel",
    "real time systems": "Real-time systems",
    "realtime systems": "Real-time systems",
    "real-time software development": "Real-time systems",
    "real-time operating systems": "RTOS",
    "low level development": "Low-level development",
    "system-level programming": "Low-level development",
    "systems programming": "Low-level development",
    # ── practices ────────────────────────────────────────────────────────────
    "agile development": "Agile",
    "agile methodologies": "Agile",
    "agile methodology": "Agile",
    "agile methods": "Agile",
    "agile development methodologies": "Agile",
    "agile practices": "Agile",
    "continuous integration": "CI/CD",
    "continuous delivery": "CI/CD",
    "continuous deployment": "CI/CD",
    "continuous integration/continuous deployment": "CI/CD",
    "code reviews": "Code review",
    "peer review": "Code review",
    "peer code review": "Code review",
    "test automation": "Test automation",
    "automated testing": "Test automation",
    "automation testing": "Test automation",
    "automated tests": "Test automation",
    "automated testing frameworks": "Test automation",
    "testing frameworks": "Test automation",
    "unit tests": "Unit testing",
    "integration tests": "Integration testing",
    "software testing": "Testing",
    "test-driven development": "TDD",
    "test driven development": "TDD",
    "behavior-driven development": "BDD",
    "infrastructure-as-code": "Infrastructure as code",
    "iac": "Infrastructure as code",
    "source control": "Version control",
    "version control systems": "Version control",
    "technical documentation": "Technical documentation",
    "documentation": "Technical documentation",
    "clean code": "Code quality",
    "code quality standards": "Code quality",
    "best practices": "Software development best practices",
    "leadership": "Team leadership",
    "team lead experience": "Team leadership",
    "mentoring": "Mentoring",
    "mentorship": "Mentoring",
    "problem-solving": "Problem solving",
    "problem solving skills": "Problem solving",
    "analytical skills": "Problem solving",
    "troubleshooting": "Debugging",
    "debugging skills": "Debugging",
    "debugging tools": "Debugging",
    "root cause analysis": "Debugging",
    # ── concurrency & performance ────────────────────────────────────────────
    "multi-threading": "Multithreading",
    "multi threading": "Multithreading",
    "multithreaded programming": "Multithreading",
    "multi-threaded programming": "Multithreading",
    "multi-threading programming": "Multithreading",
    "multithreaded systems": "Multithreading",
    "multi-threaded systems": "Multithreading",
    "threading": "Multithreading",
    "concurrent programming": "Concurrency",
    "concurrency control": "Concurrency",
    "async programming": "Asynchronous programming",
    "async/concurrent programming": "Asynchronous programming",
    "asynchronous processing": "Asynchronous programming",
    "async processing": "Asynchronous programming",
    "performance tuning": "Performance optimization",
    "performance improvements": "Performance optimization",
    "optimization": "Performance optimization",
    "latency optimization": "Performance optimization",
    "code profiling": "Performance profiling",
    "performance engineering": "Performance optimization",
    "caching solutions": "Caching",
    "caching strategies": "Caching",
    # ── data & storage ───────────────────────────────────────────────────────
    "rdbms": "Relational databases",
    "relational database": "Relational databases",
    "sql databases": "Relational databases",
    "non-relational databases": "NoSQL",
    "nosql databases": "NoSQL",
    "database optimization": "Query optimization",
    "sql optimization": "Query optimization",
    "sql queries": "SQL",
    "data pipeline": "Data pipelines",
    "etl processes": "ETL",
    "etl pipelines": "ETL",
    "big data": "Big data",
    "message brokers": "Message queues",
    "messaging systems": "Message queues",
    "messaging technologies": "Message queues",
    "queues": "Message queues",
    "data modelling": "Data modeling",
    # ── networking, security, ops ────────────────────────────────────────────
    "networks": "Networking",
    "networking concepts": "Networking",
    "networking fundamentals": "Networking",
    "computer networking": "Networking",
    "networking protocols": "Network protocols",
    "networking concepts and protocols": "Network protocols",
    "communication protocols": "Network protocols",
    "information security": "Cybersecurity",
    "infosec": "Cybersecurity",
    "cyber security": "Cybersecurity",
    "containers": "Containerization",
    "containerisation": "Containerization",
    "container orchestration": "Kubernetes",
    "cloud": "Cloud computing",
    "cloud platforms": "Cloud computing",
    "cloud environments": "Cloud computing",
    "cloud technologies": "Cloud computing",
    "cloud systems": "Cloud computing",
    "cloud-based systems": "Cloud computing",
    "cloud infrastructure": "Cloud computing",
    "cloud computing infrastructure": "Cloud computing",
    "monitoring systems": "Monitoring",
    "production monitoring": "Monitoring",
    "performance monitoring": "Monitoring",
    "alerting systems": "Monitoring",
    "operating system": "Operating systems",
    "os fundamentals": "Operating systems",
    # ── API shapes ───────────────────────────────────────────────────────────
    "restful": "REST APIs",
    "rest api": "REST APIs",
    "rest apis": "REST APIs",
    "restful api": "REST APIs",
    "restful apis": "REST APIs",
    "restful services": "REST APIs",
    "rest services": "REST APIs",
    "api": "APIs",
    "api development": "API design",
    "api design and development": "API design",
    "api integrations": "API integration",
    "third-party service integrations": "API integration",
}

# Whole-string compounds that stay as one skill even though every side is a
# known technology (the "/" is part of the name, not a list separator).
_NO_SPLIT = frozenset({
    "ci/cd", "tcp/ip", "tcp/udp", "ui/ux", "http/s", "i/o", "r&d", "and/or",
})

# ── Generic-word whitelists ──────────────────────────────────────────────────
# Words that are lower-cased when they appear after the first word of a phrase,
# so "Distributed Systems" and "distributed systems" land on one string. Only
# generic engineering vocabulary is listed — anything else the model capitalised
# is assumed to be a product name and left alone ("AWS Glue", "NVIDIA Jetson").
_COMMON_WORDS = frozenset("""
and or of in for the to with on as at a an
development developer developers programming coding engineering design designs
architecture architectures testing tests test tooling tools system systems
agent agents workflow workflows learning vision pattern patterns review reviews
quality protocol protocols database databases service services methodology
methodologies method methods process processes pipeline pipelines optimization
optimisation management integration integrations infrastructure framework
frameworks platform platforms application applications environment environments
practice practices principle principles concept concepts technology technologies
operations monitoring observability scripting security networking storage
computing analysis analytics modeling modelling structure structures algorithm
algorithms queue queues broker brokers internals kernel driver drivers thread
threading threaded solution solutions library libraries language languages
deployment delivery automation orchestration virtualization containerization
science software hardware programming stack side end fundamentals basics web
lifecycle assurance
ecosystem experience knowledge skills capabilities standards best code
oriented driven based level time native scale source party powered assisted
enabled first aware ready critical facing grade term related specific free safe
performance scalable distributed real high low multi cross open modern
""".split())

# One preferred number per generic head noun, applied to the last word of a
# multi-word phrase: "Microservices architectures" → "Microservices
# architecture", "Distributed system" → "Distributed systems".
_PREFERRED_NUMBER: dict[str, str] = {}
for _word in (
    "systems", "tools", "frameworks", "databases", "protocols", "services",
    "pipelines", "applications", "platforms", "methodologies", "practices",
    "principles", "algorithms", "patterns", "workflows", "agents", "queues",
    "drivers", "technologies", "environments", "structures", "languages",
    "libraries", "concepts", "brokers", "solutions", "processes", "standards",
):
    _PREFERRED_NUMBER[_word] = _word
    _PREFERRED_NUMBER[_word[:-3] + "y" if _word.endswith("ies") else _word[:-1]] = _word
for _word in (
    "architecture", "development", "engineering", "design", "testing",
    "optimization", "management", "monitoring", "learning", "review",
    "scripting", "networking", "computing", "storage", "analysis", "modeling",
    "quality", "documentation", "leadership", "mentoring", "debugging",
    "deployment", "automation", "orchestration", "virtualization",
):
    _PREFERRED_NUMBER[_word] = _word
    _PREFERRED_NUMBER[_word + "s"] = _word

# ── Filler stripping ─────────────────────────────────────────────────────────
# "Experience with X", "strong X", "knowledge of X" → "X".
#
# Only adjectives that are never part of a skill's own name are stripped on
# their own — "deep"/"advanced"/"basic" are not, or "Deep learning" and
# "Advanced analytics" would lose their heads; they're allowed only in front of
# an explicit filler noun ("deep understanding of Kafka").
_PREFIX_RE = re.compile(
    r"^(?:"
    r"(?:strong|excellent|proven|hands[- ]on|in[- ]depth|practical|extensive|"
    r"solid|working|prior|demonstrated|significant)\s+"
    r"|(?:(?:deep|good|basic|advanced|strong|solid)\s+)?"
    r"(?:experience|expertise|proficiency|proficient|familiarity|background|"
    r"understanding|knowledge|fluency)\s+(?:with|in|of|using|as)\s+"
    r"|(?:ability|willingness)\s+to\s+"
    r")",
    re.IGNORECASE,
)

# "<known tech> development / tools / experience" → "<known tech>". Only applied
# when what's left is a technology we recognise, so "Software development" and
# "Vector databases" (whose heads mean nothing on their own) survive.
_NOISE_SUFFIXES = (
    "development", "programming", "coding", "experience", "expertise",
    "knowledge", "proficiency", "skills", "skill", "fundamentals", "basics",
    "ecosystem", "language", "stack", "technologies", "technology", "tools",
    "tooling", "pipelines", "processes", "practices", "platforms", "services",
    "frameworks", "environments", "solutions",
)

# Trailing version markers: "Angular 5+", ".NET 6", "Python 3.11".
_VERSION_RE = re.compile(r"\s+v?\d+(?:\.\d+)*\+?$")

_WS_RE = re.compile(r"\s+")
_PARENS_RE = re.compile(r"\s*\([^)]*\)")
_UPPER_RE = re.compile(r"[A-Z]")
_INNER_UPPER_RE = re.compile(r".[A-Z]")   # mixed-case name: "IoT", "PCIe", "eBPF"

# Bare technology names, used to decide whether a filler suffix or a version
# marker may be stripped, and whether a "a/b" compound is really two skills.
_TECH_NAMES = frozenset(_CANONICAL) | frozenset(_ACRONYMS)


def _clean(raw: str) -> str:
    """Whitespace, quotes, stray punctuation and "(parentheticals)"."""
    skill = _WS_RE.sub(" ", str(raw).replace(" ", " ")).strip()
    skill = skill.strip("\"'`“”‘’").strip()
    stripped = _PARENS_RE.sub("", skill).strip()
    if stripped:
        skill = stripped
    skill = skill.replace(" & ", " and ")
    skill = skill.rstrip(".,;:").strip()
    return _WS_RE.sub(" ", skill)


def _strip_prefix(skill: str) -> str:
    """
    Drop leading filler ("strong hands-on experience with React").

    A phrase the tables already know is left alone, so real skills that start
    with a filler adjective ("Deep learning", "Advanced analytics") survive.
    """
    while True:
        low = skill.lower()
        if low in _ALIASES or low in _CANONICAL:
            return skill
        trimmed = _PREFIX_RE.sub("", skill).strip()
        if trimmed == skill or not trimmed:
            return skill
        skill = trimmed


def _strip_suffix(skill: str) -> str:
    """Drop trailing filler and versions when a known technology is left."""
    while True:
        low = skill.lower()
        head = None
        for suffix in _NOISE_SUFFIXES:
            if low.endswith(" " + suffix):
                head = skill[: -(len(suffix) + 1)].strip()
                break
        if head is None:
            versioned = _VERSION_RE.sub("", skill).strip()
            if versioned != skill:
                head = versioned
        if not head:
            return skill
        # An alias head is already a skill in its own right ("Google Cloud
        # Platform services" → GCP); take it and stop, so a second pass can't
        # keep eating words ("AI coding tools" → "AI coding" → "AI").
        if head.lower() in _ALIASES:
            return _ALIASES[head.lower()]
        if head.lower() not in _TECH_NAMES:
            return skill
        skill = head


def _recase_token(token: str, is_first: bool, casing_only: bool = False) -> str:
    low = token.lower()
    # Only single-word canonical forms may fire per word: an entry that expands
    # to a phrase ("rest" → "REST APIs") is about the skill as a whole, and
    # applying it inside one would give "Django REST APIs framework". Inside a
    # hyphenated name only re-casings apply, so "Node-RED" keeps its "Node".
    canonical = _CANONICAL.get(low)
    if canonical and " " not in canonical and not (casing_only and canonical.lower() != low):
        return canonical
    # Hyphen parts are cased independently ("Real-Time" → "Real-time"), so this
    # runs before the mixed-case check below — the hyphen is not inner casing.
    if "-" in token and len(token) > 1:
        parts = token.split("-")
        return "-".join(_recase_token(p, is_first and i == 0, True) for i, p in enumerate(parts))
    if token != token.upper() and _INNER_UPPER_RE.search(token):
        return token                      # "IoT", "PCIe", "gRPC" — leave as written
    if low in _ACRONYMS:
        return _ACRONYMS[low]
    if not token:
        return token
    if is_first:
        return token if _UPPER_RE.search(token) else low[:1].upper() + low[1:]
    if low in _COMMON_WORDS:
        return low
    if _UPPER_RE.search(token):
        return token                      # model already cased it — a proper noun
    return low


def _recase(skill: str) -> str:
    """Canonical spellings, acronyms, sentence case for everything else."""
    words = skill.split(" ")
    # A multi-word phrase the model shouted ("DISTRIBUTED SYSTEMS") — fold it so
    # it doesn't stay all-caps. Needs a word of 5+ letters so short all-caps
    # product names ("MS SQL", "AWS EC2") and acronym runs are left alone.
    if len(words) > 1 and skill.isupper() and any(len(w) >= 5 for w in words):
        words = skill.lower().split(" ")
    return " ".join(_recase_token(w, i == 0) for i, w in enumerate(words))


def _fix_last_word(skill: str) -> str:
    """One preferred singular/plural per generic head noun."""
    words = skill.split(" ")
    if len(words) < 2:
        return skill
    last = words[-1]
    if last.islower() and last in _PREFERRED_NUMBER:
        words[-1] = _PREFERRED_NUMBER[last]
    return " ".join(words)


def _resolve(skill: str) -> str:
    """One pass of alias → suffix trim → recase → head-noun number."""
    skill = _ALIASES.get(skill.lower(), skill)
    canonical = _CANONICAL.get(skill.lower())
    if canonical:
        return canonical
    skill = _strip_suffix(skill)
    skill = _ALIASES.get(skill.lower(), skill)
    canonical = _CANONICAL.get(skill.lower())
    if canonical:
        return canonical
    skill = _fix_last_word(_recase(skill))
    return _ALIASES.get(skill.lower(), skill)


def normalize_skill(raw: str) -> str:
    """Return the canonical spelling of a single skill string."""
    skill = _strip_prefix(_clean(raw))
    if not skill:
        return ""

    # The table lookups inside _resolve can rewrite a skill into another form
    # that itself needs normalising ("agentic ai" → "AI agents"), so iterate to
    # a fixed point. Three passes is plenty; the cap only guards a table cycle.
    for _ in range(3):
        nxt = _resolve(skill)
        if nxt == skill:
            break
        skill = nxt
    return skill


def expand_skill(raw: str) -> list[str]:
    """
    Normalise one skill string into the list of skills it actually names.

    Compounds the model writes as one entry are split when every side is a
    technology in its own right — "C/C++" → ["C", "C++"], "AI/ML" → ["AI",
    "Machine learning"] — so the two spellings stop competing in filters.
    Names that merely contain a slash ("CI/CD", "TCP/IP") are left whole.
    """
    skill = _strip_prefix(_clean(raw))
    if not skill:
        return []

    low = skill.lower()
    if "/" in skill and " " not in skill and low not in _NO_SPLIT and low not in _CANONICAL:
        parts = [p.strip() for p in skill.split("/") if p.strip()]
        if len(parts) > 1 and all(p.lower() in _TECH_NAMES or p.lower() in _ALIASES for p in parts):
            out = []
            for part in parts:
                norm = normalize_skill(part)
                if norm and norm not in out:
                    out.append(norm)
            return out

    norm = normalize_skill(skill)
    return [norm] if norm else []


def normalize_skills(skills) -> list[str]:
    """
    Normalise a list of skills: canonical spelling, compounds expanded, blanks
    dropped, and case-insensitive duplicates collapsed in first-seen order.
    """
    if not isinstance(skills, list):
        return []

    seen: set[str] = set()
    out: list[str] = []
    for raw in skills:
        if not raw:
            continue
        for norm in expand_skill(raw):
            key = norm.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(norm)
    return out
