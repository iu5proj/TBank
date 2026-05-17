"""Tighten ML/RAG indexes from Codex technical spec.

Revision ID: 003_tz_indexes
Revises: 002_gpt_oss_contract
Create Date: 2026-05-17 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "003_tz_indexes"
down_revision: str | None = "002_gpt_oss_contract"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE vacancies SET source_vacancy_id = id::text WHERE source_vacancy_id IS NULL")
    op.alter_column("vacancies", "source_vacancy_id", existing_type=sa.Text(), nullable=False)
    op.create_index("ix_vacancies_published_at", "vacancies", ["published_at"], unique=False)
    op.create_index(
        "ix_llm_salary_results_segment_version",
        "llm_salary_results",
        ["segment_key", "segment_data_version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_llm_salary_results_segment_version", table_name="llm_salary_results")
    op.drop_index("ix_vacancies_published_at", table_name="vacancies")
    op.alter_column("vacancies", "source_vacancy_id", existing_type=sa.Text(), nullable=True)
