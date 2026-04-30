from pydantic import BaseModel, Field


class WorkExperience(BaseModel):
    company: str
    role: str
    start_date: str | None = None
    end_date: str | None = None  # None means "Present" / "Current"
    description: str | None = None


class Education(BaseModel):
    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class ParsedResume(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    summary: str | None = None
    work_experience: list[WorkExperience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    detail: str
