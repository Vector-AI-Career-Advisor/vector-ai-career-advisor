from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ResumeOut(BaseModel):
    filename: str
    content: str
    uploaded_at: Optional[datetime]
    updated_at: Optional[datetime]
