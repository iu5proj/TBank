"""ORM models package — import all models here so Alembic can discover them."""

from app.models.audit_log import AuditLogResume
from app.models.estimate import SalaryEstimate
from app.models.llm_salary_result import LlmSalaryResult
from app.models.market_segment import MarketSegment
from app.models.recommendation import Recommendation
from app.models.resume import Resume
from app.models.user import User
from app.models.vacancy import Vacancy

__all__ = [
    "AuditLogResume",
    "LlmSalaryResult",
    "MarketSegment",
    "Recommendation",
    "Resume",
    "SalaryEstimate",
    "User",
    "Vacancy",
]
