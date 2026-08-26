import logging
import httpx

from fastapi import HTTPException
from server.db.postgres import get_connection
from server.web.core.security import hash_password, verify_password, create_access_token
from server.web.core.logging import open_user_session
from server.web.core.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET
from server.web.features.auth.schemas import UserCreate, UserLogin, TokenResponse, OAuthCallbackRequest

log = logging.getLogger(__name__)


# ── Email / password ─────────────────────────────────────────────────────────

def signup(user: UserCreate):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (user.email,))
            if cur.fetchone():
                log.warning("Signup rejected — email already registered: %s", user.email)
                raise HTTPException(status_code=400, detail="Email already registered")

            cur.execute(
                "INSERT INTO users (email, password) VALUES (%s, %s)",
                (user.email, hash_password(user.password)),
            )
        conn.commit()
        log.info("New user registered: %s", user.email)
        return {"message": "Account created successfully"}
    finally:
        conn.close()


def login(user: UserLogin) -> TokenResponse:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, password FROM users WHERE email = %s", (user.email,)
            )
            row = cur.fetchone()

        if not row or not verify_password(user.password, row[1]):
            log.warning("Failed login attempt for email: %s", user.email)
            raise HTTPException(status_code=401, detail="Invalid email or password")

        open_user_session(row[0])
        return TokenResponse(access_token=create_access_token(row[0]))
    finally:
        conn.close()


def get_me(user_id: str) -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT email, created_at FROM users WHERE id = %s",
                (int(user_id),),
            )
            row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return {"email": row[0], "created_at": row[1]}
    finally:
        conn.close()


# ── OAuth helpers ─────────────────────────────────────────────────────────────

def _exchange_google(code: str, redirect_uri: str) -> dict:
    """Exchange Google auth code for user info."""
    token_res = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    token_res.raise_for_status()
    access_token = token_res.json()["access_token"]

    info_res = httpx.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    info_res.raise_for_status()
    data = info_res.json()
    return {
        "provider_user_id": data["id"],
        "email": data["email"],
        "name": data.get("name"),
        "avatar_url": data.get("picture"),
    }


def _exchange_linkedin(code: str, redirect_uri: str) -> dict:
    """Exchange LinkedIn auth code for user info."""
    token_res = httpx.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": LINKEDIN_CLIENT_ID,
            "client_secret": LINKEDIN_CLIENT_SECRET,
        },
        timeout=10,
    )
    token_res.raise_for_status()
    access_token = token_res.json()["access_token"]

    profile_res = httpx.get(
        "https://api.linkedin.com/v2/me?projection=(id,localizedFirstName,localizedLastName)",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    email_res = httpx.get(
        "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    profile_res.raise_for_status()
    email_res.raise_for_status()

    p = profile_res.json()
    email = email_res.json()["elements"][0]["handle~"]["emailAddress"]
    name = f"{p.get('localizedFirstName', '')} {p.get('localizedLastName', '')}".strip()
    return {
        "provider_user_id": p["id"],
        "email": email,
        "name": name or None,
        "avatar_url": None,
    }


def _upsert_oauth_user(provider: str, provider_user_id: str, email: str, name: str | None) -> int:
    """Return the Vector user id, creating the account if needed."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Check by oauth identity
            cur.execute(
                "SELECT user_id FROM oauth_identities WHERE provider=%s AND provider_user_id=%s",
                (provider, provider_user_id),
            )
            row = cur.fetchone()
            if row:
                return row[0]

            # Check by email (link accounts)
            cur.execute("SELECT id FROM users WHERE email=%s", (email,))
            user_row = cur.fetchone()
            if user_row:
                user_id = user_row[0]
            else:
                cur.execute(
                    "INSERT INTO users (email, password) VALUES (%s, %s) RETURNING id",
                    (email, ""),  # no password for OAuth users
                )
                user_id = cur.fetchone()[0]

            cur.execute(
                "INSERT INTO oauth_identities (user_id, provider, provider_user_id) VALUES (%s,%s,%s)",
                (user_id, provider, provider_user_id),
            )
        conn.commit()
        log.info("OAuth login: provider=%s email=%s user_id=%s", provider, email, user_id)
        return user_id
    finally:
        conn.close()


def oauth_login(body: OAuthCallbackRequest) -> TokenResponse:
    try:
        if body.provider == "google":
            info = _exchange_google(body.code, body.redirect_uri)
        elif body.provider == "linkedin":
            info = _exchange_linkedin(body.code, body.redirect_uri)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {body.provider}")
    except httpx.HTTPStatusError as exc:
        log.error("OAuth token exchange failed: %s", exc)
        raise HTTPException(status_code=400, detail="OAuth token exchange failed")

    user_id = _upsert_oauth_user(
        provider=body.provider,
        provider_user_id=info["provider_user_id"],
        email=info["email"],
        name=info.get("name"),
    )
    return TokenResponse(access_token=create_access_token(user_id))


# ── Legal pages ───────────────────────────────────────────────────────────────

_LEGAL_CSS = """
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root { --bg:#0b0c12; --surface:#13141e; --border:rgba(255,255,255,0.08);
            --text:#f0f0fa; --muted:#9898b4; --accent:#7c5af7; --accent2:#30bfb8;
            --font:'Outfit',sans-serif; }
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Lora:ital,wght@0,400;1,400&display=swap');
    body { background:var(--bg); color:var(--text); font-family:var(--font);
           line-height:1.75; font-size:1rem; }
    .wrap { max-width:760px; margin:0 auto; padding:4rem 2rem 6rem; }
    .back { display:inline-flex; align-items:center; gap:8px; color:var(--accent2);
            font-size:.85rem; font-weight:500; text-decoration:none; margin-bottom:3rem;
            border:1px solid rgba(48,191,184,.25); border-radius:8px; padding:.45rem .9rem;
            transition:background .2s; }
    .back:hover { background:rgba(48,191,184,.08); }
    .badge { display:inline-block; font-size:.65rem; font-weight:700; letter-spacing:.14em;
             text-transform:uppercase; color:var(--accent); background:rgba(124,90,247,.12);
             border:1px solid rgba(124,90,247,.25); border-radius:6px;
             padding:.3rem .7rem; margin-bottom:1.2rem; }
    h1 { font-family:'Lora',serif; font-size:clamp(2rem,4vw,2.8rem); font-weight:400;
         line-height:1.15; margin-bottom:.6rem; }
    .meta { font-size:.82rem; color:var(--muted); margin-bottom:3rem;
            padding-bottom:2rem; border-bottom:1px solid var(--border); }
    h2 { font-size:1.1rem; font-weight:600; color:var(--text); margin:2.5rem 0 .7rem;
         padding-left:1rem; border-left:3px solid var(--accent); }
    p { color:var(--muted); margin-bottom:1rem; }
    ul { color:var(--muted); padding-left:1.4rem; margin-bottom:1rem; }
    li { margin-bottom:.4rem; }
    strong { color:var(--text); font-weight:600; }
    a { color:var(--accent2); text-decoration:none; border-bottom:1px solid rgba(48,191,184,.3); }
    a:hover { border-color:var(--accent2); }
    .contact-box { margin-top:3rem; padding:1.5rem; background:var(--surface);
                   border:1px solid var(--border); border-radius:12px; }
    .contact-box p { margin:0; }
  </style>
"""


def render_terms() -> str:
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Terms of Service — Vector</title>{_LEGAL_CSS}</head><body>
<div class="wrap">
  <a class="back" href="/login">&#8592; Back to Vector</a>
  <span class="badge">Legal</span>
  <h1>Terms of Service</h1>
  <p class="meta">Effective date: 1 June 2025 &nbsp;·&nbsp; Last updated: 1 June 2025</p>

  <h2>1. Acceptance of Terms</h2>
  <p>By accessing or using Vector ("the Service"), you agree to be bound by these Terms of Service and all applicable laws. If you do not agree, you may not use the Service.</p>

  <h2>2. Description of Service</h2>
  <p>Vector is an AI-powered career platform that aggregates job listings, assists with application materials, and tracks your hiring pipeline. Features include but are not limited to daily job feeds, CV tailoring, interview preparation, and application tracking.</p>

  <h2>3. Eligibility</h2>
  <p>You must be at least 16 years of age to use Vector. By using the Service you represent that you meet this requirement and that the information you provide is accurate and complete.</p>

  <h2>4. Account Responsibilities</h2>
  <ul>
    <li>You are responsible for maintaining the confidentiality of your credentials.</li>
    <li>You must notify us immediately of any unauthorised access to your account.</li>
    <li>You may not share your account with any third party.</li>
    <li>Each person may hold only one account.</li>
  </ul>

  <h2>5. Acceptable Use</h2>
  <p>You agree not to:</p>
  <ul>
    <li>Use the Service for any unlawful purpose or in violation of any regulations.</li>
    <li>Scrape, crawl, or systematically extract data from the Service without written permission.</li>
    <li>Attempt to gain unauthorised access to any part of the Service or its infrastructure.</li>
    <li>Upload or transmit malicious code, viruses, or any software intended to disrupt the Service.</li>
    <li>Impersonate any person or entity or misrepresent your affiliation.</li>
  </ul>

  <h2>6. Intellectual Property</h2>
  <p>All content, trademarks, and technology comprising the Service are the exclusive property of Vector or its licensors. Nothing in these Terms grants you any right to use Vector's intellectual property except as expressly permitted.</p>
  <p>You retain ownership of content you submit (e.g. CV data). By submitting content you grant Vector a limited, non-exclusive licence to process and display it solely to provide the Service.</p>

  <h2>7. AI-Generated Content</h2>
  <p>Vector uses artificial intelligence to generate suggestions including CV text and interview questions. Such content is provided <strong>as-is for informational purposes only</strong>. You are solely responsible for reviewing, editing, and submitting any AI-generated content. Vector makes no warranty that AI-generated content is accurate, complete, or suitable for any particular purpose.</p>

  <h2>8. Third-Party Services</h2>
  <p>The Service may integrate with third-party platforms (e.g. LinkedIn, Google, job boards). Your use of those integrations is governed by the respective third party's terms. Vector is not responsible for third-party content or conduct.</p>

  <h2>9. Disclaimer of Warranties</h2>
  <p>The Service is provided <strong>"as is" and "as available"</strong> without warranty of any kind, express or implied, including but not limited to merchantability, fitness for a particular purpose, and non-infringement. Vector does not warrant that the Service will be uninterrupted, error-free, or free of harmful components.</p>

  <h2>10. Limitation of Liability</h2>
  <p>To the maximum extent permitted by applicable law, Vector and its affiliates shall not be liable for any indirect, incidental, special, consequential, or punitive damages arising from your use of or inability to use the Service, even if advised of the possibility of such damages.</p>

  <h2>11. Termination</h2>
  <p>Vector reserves the right to suspend or terminate your access at any time, with or without notice, for conduct that violates these Terms or is otherwise harmful. You may delete your account at any time from your account settings.</p>

  <h2>12. Changes to Terms</h2>
  <p>We may update these Terms from time to time. Continued use of the Service after changes constitutes acceptance of the revised Terms. We will provide reasonable notice of material changes.</p>

  <h2>13. Governing Law</h2>
  <p>These Terms are governed by the laws of England and Wales. Any disputes shall be subject to the exclusive jurisdiction of the courts of England and Wales.</p>

  <div class="contact-box">
    <p><strong>Questions?</strong> Contact us at <a href="mailto:legal@vector.app">legal@vector.app</a></p>
  </div>
</div></body></html>"""


def render_privacy() -> str:
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Privacy Policy — Vector</title>{_LEGAL_CSS}</head><body>
<div class="wrap">
  <a class="back" href="/login">&#8592; Back to Vector</a>
  <span class="badge">Legal</span>
  <h1>Privacy Policy</h1>
  <p class="meta">Effective date: 1 June 2025 &nbsp;·&nbsp; Last updated: 1 June 2025</p>

  <h2>1. Who We Are</h2>
  <p>Vector ("we", "us", "our") operates the Vector career platform. This policy explains how we collect, use, and protect your personal data in accordance with the UK GDPR and the Data Protection Act 2018.</p>

  <h2>2. Data We Collect</h2>
  <ul>
    <li><strong>Account data</strong> — email address, hashed password, name (when provided via OAuth).</li>
    <li><strong>Profile & CV data</strong> — employment history, skills, education, and other career information you choose to provide.</li>
    <li><strong>Usage data</strong> — pages visited, features used, search queries, and timestamps, collected via server logs and analytics.</li>
    <li><strong>OAuth tokens</strong> — temporary access tokens from Google or LinkedIn, used solely to retrieve your email and basic profile at sign-in. We do not store raw OAuth tokens beyond the authentication handshake.</li>
    <li><strong>Device & technical data</strong> — IP address, browser type, operating system, and referrer URL.</li>
  </ul>

  <h2>3. How We Use Your Data</h2>
  <ul>
    <li>Providing and personalising the Service (legal basis: contract performance).</li>
    <li>Tailoring job recommendations and AI-generated content to your profile (legitimate interests).</li>
    <li>Sending transactional emails such as account confirmations (contract performance).</li>
    <li>Improving and securing the Service through aggregated analytics (legitimate interests).</li>
    <li>Complying with legal obligations.</li>
  </ul>

  <h2>4. Data Sharing</h2>
  <p>We do not sell your personal data. We may share data with:</p>
  <ul>
    <li><strong>Infrastructure providers</strong> — cloud hosting and database services operating under data processing agreements.</li>
    <li><strong>AI model providers</strong> — anonymised or pseudonymised text may be processed by third-party AI APIs to generate suggestions.</li>
    <li><strong>Analytics tools</strong> — aggregated, non-identifying usage statistics.</li>
    <li><strong>Law enforcement</strong> — only where required by applicable law or valid legal process.</li>
  </ul>

  <h2>5. Data Retention</h2>
  <p>We retain your account and profile data for as long as your account is active. You may request deletion at any time. Backups are purged within 90 days of deletion. Anonymised analytics data may be retained indefinitely.</p>

  <h2>6. Your Rights</h2>
  <p>Under UK GDPR you have the right to:</p>
  <ul>
    <li><strong>Access</strong> — obtain a copy of the personal data we hold about you.</li>
    <li><strong>Rectification</strong> — correct inaccurate data.</li>
    <li><strong>Erasure</strong> — request deletion of your data ("right to be forgotten").</li>
    <li><strong>Restriction</strong> — ask us to limit processing in certain circumstances.</li>
    <li><strong>Portability</strong> — receive your data in a structured, machine-readable format.</li>
    <li><strong>Objection</strong> — object to processing based on legitimate interests.</li>
  </ul>
  <p>To exercise any of these rights, contact <a href="mailto:privacy@vector.app">privacy@vector.app</a>. We will respond within 30 days.</p>

  <h2>7. Cookies</h2>
  <p>We use strictly necessary cookies to maintain your session. We do not use advertising or cross-site tracking cookies. You can disable cookies in your browser settings, though this may affect functionality.</p>

  <h2>8. Security</h2>
  <p>We employ industry-standard security measures including TLS encryption in transit, bcrypt password hashing, and access controls. No system is completely secure; if you suspect unauthorised access, contact us immediately.</p>

  <h2>9. Children's Privacy</h2>
  <p>The Service is not directed at persons under 16. We do not knowingly collect data from children. If you believe a child has provided us data, contact us and we will delete it promptly.</p>

  <h2>10. Changes to This Policy</h2>
  <p>We may update this policy periodically. We will notify registered users of material changes via email or an in-app notice at least 14 days before they take effect.</p>

  <div class="contact-box">
    <p><strong>Data controller:</strong> Vector &nbsp;·&nbsp; <a href="mailto:privacy@vector.app">privacy@vector.app</a></p>
  </div>
</div></body></html>"""