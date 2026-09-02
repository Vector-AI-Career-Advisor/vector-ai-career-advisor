
import os
from dotenv import load_dotenv

load_dotenv()
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _resolve(path: str) -> str:
    return path if os.path.isabs(path) else os.path.normpath(os.path.join(_BACKEND_DIR, path))


# ── Database ──────────────────────────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("DOCKER_DB_HOST") or os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 5432)),
    "dbname":   os.getenv("DB_NAME", "jobboard"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

# ── Auth / JWT ────────────────────────────────────────────────────────────────
SECRET_KEY                  = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM                   = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

# ── OAuth providers ───────────────────────────────────────────────────────────   
GOOGLE_CLIENT_ID       = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET   = os.getenv("GOOGLE_CLIENT_SECRET", "")
LINKEDIN_CLIENT_ID     = os.getenv("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")

# ── ChromaDB ──────────────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR = _resolve(os.getenv("CHROMA_DIR", "chroma_db"))
CHROMA_COLLECTION  = os.getenv("CHROMA_COLLECTION")

# ── Static assets (company logos) ─────────────────────────────────────────────
# STATIC_DIR is served at /static by the web app; the ETL pipeline and
# scripts/backfill_logos.py write company logos into STATIC_DIR/logos. In Docker
# that subdirectory is a named volume shared between the `server` and `scheduler`
# containers (see docker-compose.yml).
STATIC_DIR    = _resolve("web/static")
LOGO_DIR      = os.path.join(STATIC_DIR, "logos")
LOGO_URL_BASE = os.getenv("STATIC_BASE_URL", "http://localhost:8000").rstrip("/") + "/static/logos"

# ── Embeddings ────────────────────────────────────────────────────────────────
EMBEDDING_DIM         = 1536
LOCAL_EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ── Ollama (local inference) ──────────────────────────────────────────────────
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_BASE_URL = os.getenv("DOCKER_OLLAMA_URL") or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# ── Anthropic ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL   = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")

# ── Scraper ───────────────────────────────────────────────────────────────────
CHROME_VERSION = int(os.getenv("CHROME_VERSION", 147))
DATE_FILTER    = os.getenv("DATE_FILTER", "r604800")
DAILY_TARGET   = int(os.getenv("DAILY_TARGET", 50))

KEYWORDS = [
    "software engineer", "software developer", "fullstack developer", "full stack developer",
    "developer", "software", "programmer", "r&d",
    "server", "server developer", "client", "client developer",
    "fullstack", "full stack", "web", "application", "systems",
    "python", "java", "javascript", "typescript", "go", "ruby", "php", "kotlin",
    "react", "angular", "html", "css",
    "data analyst", "data engineer", "data scientist", "ai", "machine learning",
    "deep learning", "nlp", "computer vision", "big data", "it", "bi",
    "cloud", "aws", "azure", "docker", "kubernetes", "devops", "ci cd",
    "database", "data", "nosql", "mongodb", "postgres", "mysql",
    "security", "cyber", "infosec", "penetration", "appsec",
    "android", "ios", "mobile", "flutter", "react native",
    "qa", "automation",
    "algorithm", "algorithms", "microservices", "api", "integration", "network", "linux",
    "infrastructure", "platform", "sre", "site reliability",
    "spark", "kafka", "hadoop", "etl", "pipeline",
    "embedded", "firmware",
]

# ── Extraction ────────────────────────────────────────────────────────────────
EXTRACTION_PROMPT = """You are a job data extractor. Given a job title and description, return ONLY a valid JSON object. No markdown, no explanation, no extra text.

{
  "role": "ONE OF: Software Development|Frontend|Backend|Fullstack|AI / ML|Data Scientist|Data Engineer|Data Analyst|BI|DevOps / Cloud|Mobile|QA / Automation|Security|Embedded / Firmware|Database|Network|System Engineer|Product Manager|Team Lead|R&D|Solutions Architect",
  "seniority": "ONE OF: Intern|Junior|Mid|Senior|Lead|Staff|Principal|Manager|Director|VP|Not specified",
  "description": "4-5 sentences about daily work, systems, team context, impact",
  "experience": <integer years or null>,
  "skills_must": ["all required technologies, tools, frameworks, languages, platforms, databases, cloud services, and methodologies that are NOT marked as Advantage/Preferred/Bonus/Nice to have"],
  "skills_nice": ["only skills explicitly marked as Advantage/Preferred/Bonus/Nice to have"],
  "past_experience": ["development domains, job titles, or industry verticals that the post explicitly requires experience in — e.g. 'Backend development', 'Frontend development', 'Mobile development', 'Fullstack Developer', 'FinTech', 'SaaS', 'embedded systems'. Extract the domain/title from phrases like '3-5 years of experience in X', '4+ years of X development', 'background in X'. Do NOT include generic phrases like 'modern technologies' or 'software development'"]

}

Rules:
- role: derive from job TITLE only. Map the primary technology/domain in the title to the closest role value. Use "Software Development" for generic engineer/developer titles. Only use "Other" if the title has no engineering/tech signal at all
- experience: integer years or null. For "X+ years" use X (e.g. "8+ years" -> 8). For a range "X-Y years" use the lower bound X. Never return a value lower than what is written. Search the ENTIRE post for any mention of years of experience
- seniority: derive PRIMARILY from years of experience using these rules: 0-3 years = Junior, 3-5 years = Mid, 5+ years = Senior. Override with title only for explicit leadership roles: Lead/Staff/Principal/Manager/Director/VP/Senior/Mid/Junior. If no experience is mentioned anywhere AND the title has no seniority signal, use "Not specified"
- skills_must: scan the ENTIRE job post for required skills. Include every technology, tool, language, framework, platform, database, cloud service, and methodology that a candidate MUST have. Do not limit to a specific section — many posts mix requirements throughout. Exclude only items explicitly labeled Advantage/Preferred/Bonus/Nice to have
- skills_nice: only items explicitly labeled Advantage/Preferred/Bonus/Nice to have anywhere in the post
- past_experience: extract the domain or title from ANY phrase like "X years of experience in Y", "Y years of Y development", "background in Y", "experience as a Y", or "worked as Y". Capture the Y part (e.g. "Backend development", "Mobile", "FinTech"). Also include explicit job titles (e.g. "Fullstack Developer") or industry verticals (e.g. "SaaS", "FinTech") stated as desired background. Leave [] only if the post mentions zero specific domains or titles
- Always respond in English regardless of input language
- If a field is not mentioned return null for strings/numbers or [] for arrays
- skills_must should NEVER be empty if the job description mentions any technologies — always extract them
"""

VALID_ROLES = {
    "Software Development", "Frontend", "Backend", "Fullstack", "AI / ML",
    "Data Scientist", "Data Engineer", "Data Analyst", "BI", "DevOps / Cloud",
    "Mobile", "QA / Automation", "Security", "Embedded / Firmware", "Database",
    "Network", "System Engineer", "Team Lead", "Product Manager", "Solutions Architect", "R&D",
    "Other",
}

VALID_SENIORITY = {
    "Intern", "Junior", "Mid", "Senior", "Lead", "Staff",
    "Principal", "Manager", "Director", "VP", "Not specified",
}
