from pydantic import BaseModel
from typing import List, Dict


class StatsSummary(BaseModel):
    total_jobs: int
    total_companies: int
    total_locations: int
    total_skills: int
