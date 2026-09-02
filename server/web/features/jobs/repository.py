from typing import Optional, List
from datetime import datetime, timedelta
from server.db.postgres import get_connection, _apply_stored_logo

LIMIT = 50


def list_jobs(
    keyword: Optional[str] = None,
    seniority: Optional[str] = None,
    location: Optional[str] = None,
    posted_date: Optional[str] = None,
    roles: Optional[List[str]] = None,
    years_experience_min: Optional[int] = None,
    skills: Optional[List[str]] = None,
    limit: int = LIMIT,
    offset: int = 0,
) -> dict:
    conn = get_connection()
    try:
        filters = []
        params: list = []

        if keyword:
            filters.append("(title ILIKE %s OR keyword ILIKE %s)")
            params += [f"%{keyword}%", f"%{keyword}%"]
        if seniority:
            # support multiple seniority values sent as a comma-separated string
            if ',' in seniority:
                parts = [s.strip() for s in seniority.split(',') if s.strip()]
                if parts:
                    placeholders = ",".join(["%s"] * len(parts))
                    filters.append(f"seniority ILIKE ANY(ARRAY[{placeholders}])")
                    params.extend([f"%{p}%" for p in parts])
            else:
                filters.append("seniority ILIKE %s")
                params.append(f"%{seniority}%")
        if location:
            filters.append("location ILIKE %s")
            params.append(f"%{location}%")
        
        # Posted date filter
        if posted_date:
            now = datetime.utcnow()
            if posted_date == "last_24h":
                cutoff = now - timedelta(hours=24)
            elif posted_date == "last_3d":
                cutoff = now - timedelta(days=3)
            elif posted_date == "last_week":
                cutoff = now - timedelta(days=7)
            elif posted_date == "last_2w":
                cutoff = now - timedelta(days=14)
            elif posted_date == "last_month":
                cutoff = now - timedelta(days=30)
            else:
                cutoff = None
            
            if cutoff:
                filters.append("posted_at >= %s")
                params.append(cutoff)
        
        # Role filter (multiple roles)
        if roles and len(roles) > 0:
            role_placeholders = ",".join(["%s"] * len(roles))
            filters.append(f"role ILIKE ANY(ARRAY[{role_placeholders}])")
            params.extend([f"%{role}%" for role in roles])
        
        # Years of experience filter
        if years_experience_min is not None:
            filters.append("yearsexperience >= %s")
            params.append(years_experience_min)
        
        # Skills filter (check if any of the skills are in skills_must or skills_nice)
        if skills and len(skills) > 0:
            skill_filters = []
            for skill in skills:
                skill_filters.append(f"(skills_must @> ARRAY[%s] OR skills_nice @> ARRAY[%s])")
            filters.append("(" + " OR ".join(skill_filters) + ")")
            for skill in skills:
                params.extend([skill, skill])

        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        params += [limit, offset]

        # every filter clause in `where` references jobs columns only, none of
        # which collide with company_logos, so they need no table qualifier.
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT COUNT(*) OVER() AS total_count,
                       j.id, j.title, j.role, j.seniority, j.company, j.location, j.url,
                       j.description, j.skills_must, j.skills_nice, j.yearsexperience,
                       j.past_experience, j.keyword, j.source, j.posted_at, j.scraped_at,
                       cl.logo_path
                FROM jobs j
                LEFT JOIN company_logos cl
                       ON cl.company_slug = j.company_slug AND cl.status = 'ok'
                {where}
                ORDER BY j.scraped_at DESC
                LIMIT %s OFFSET %s;
            """, params)

            rows = cur.fetchall()
            if not rows:
                return {"items": [], "total": 0}

            cols = [d[0] for d in cur.description]
            total = rows[0][0]
            items = []

            for row in rows:
                row_dict = dict(zip(cols, row))
                row_dict.pop("total_count")
                _apply_stored_logo(row_dict)
                items.append(row_dict)

            return {"items": items, "total": total}
    finally:
        conn.close()


def get_job(job_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT j.id, j.title, j.role, j.seniority, j.company, j.location, j.url,
                       j.description, j.skills_must, j.skills_nice, j.yearsexperience,
                       j.past_experience, j.keyword, j.source, j.posted_at, j.scraped_at,
                       cl.logo_path
                FROM jobs j
                LEFT JOIN company_logos cl
                       ON cl.company_slug = j.company_slug AND cl.status = 'ok'
                WHERE j.id = %s
            """, (job_id,))
            row = cur.fetchone()
            if not row:
                return None

            cols = [d[0] for d in cur.description]
            row_dict = dict(zip(cols, row))
            _apply_stored_logo(row_dict)
            return row_dict
    finally:
        conn.close()
