from types import SimpleNamespace

from server.web.agents.resume import resume_tools


class FakeCursor:
    def __init__(self):
        self._results = iter([
            {"content": "Senior software engineer with Python, SQL, and product work."},
            {
                "title": "Senior Product Engineer",
                "company": "Acme",
                "description": "Build products with Python and SQL. Work with cross-functional teams.",
                "skills_must": ["Python", "SQL"],
                "skills_nice": ["React"],
            },
        ])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *args, **kwargs):
        self._current = next(self._results)

    def fetchone(self):
        return self._current


class FakeConn:
    def cursor(self, *args, **kwargs):
        return FakeCursor()

    def close(self):
        pass


class FakeResponse:
    def __init__(self, text):
        self.content = [SimpleNamespace(text=text)]


class FakeMessages:
    def create(self, **kwargs):
        return FakeResponse("Acme resume tailored for Python and SQL work.")


class FakeAnthropic:
    def __init__(self, *args, **kwargs):
        self.messages = FakeMessages()


def test_generate_tailored_resume_for_job_returns_editable_text(monkeypatch):
    monkeypatch.setattr(resume_tools, "_conn", lambda: FakeConn())
    monkeypatch.setattr(resume_tools.anthropic, "Anthropic", lambda api_key=None: FakeAnthropic())
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-3-5-sonnet")

    result = resume_tools.generate_tailored_resume_for_job(7, "job-123")

    assert result["job_title"] == "Senior Product Engineer"
    assert result["company"] == "Acme"
    assert "tailored" in result["tailored_resume"].lower()
    assert len(result["tailored_resume"]) > 20
