"""Advisor Tools — read-only tools for the Job Advisor Agent.

Thin re-exports of the two DB tools the advisor needs.
Keeping them separate means the advisor's ToolNode only binds
what it should have access to.
"""
from server.web.agents.data.db_tools import get_job_details, top_skills
from server.web.agents.advisor.course_tools import recommend_courses

ADVISOR_TOOLS = [get_job_details, top_skills, recommend_courses]
