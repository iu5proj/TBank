"""Add GPT-OSS salary analysis contract tables.

Revision ID: 002_gpt_oss_contract
Revises: 001_initial
Create Date: 2026-05-16 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002_gpt_oss_contract"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("segment_key", sa.Text, nullable=False),
        sa.Column("role_cluster", sa.Text, nullable=True),
        sa.Column("specialization", sa.Text, nullable=True),
        sa.Column("region", sa.Text, nullable=True),
        sa.Column("experience_bucket", sa.Text, nullable=True),
        sa.Column("last_successful_update_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("segment_data_version", sa.Text, nullable=True),
        sa.Column("vacancies_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("segment_key", name="uq_market_segments_segment_key"),
    )
    op.create_index("ix_market_segments_segment_key", "market_segments", ["segment_key"])

    op.create_table(
        "vacancies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("segment_key", sa.Text, nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("source_vacancy_id", sa.Text, nullable=True),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("location", sa.Text, nullable=True),
        sa.Column("salary_min_net", sa.Integer, nullable=True),
        sa.Column("salary_max_net", sa.Integer, nullable=True),
        sa.Column("salary_currency", sa.Text, nullable=False, server_default="RUB"),
        sa.Column("experience_range", sa.Text, nullable=True),
        sa.Column("skills_required", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parsed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("raw_payload", postgresql.JSONB, nullable=True),
        sa.UniqueConstraint("source", "source_vacancy_id", name="uq_vacancies_source_source_vacancy_id"),
    )
    op.create_index("ix_vacancies_segment_key", "vacancies", ["segment_key"])
    op.create_index("ix_vacancies_title", "vacancies", ["title"])
    op.create_index("ix_vacancies_location", "vacancies", ["location"])

    op.create_table(
        "llm_salary_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("request_hash", sa.Text, nullable=False),
        sa.Column("profile_snapshot", postgresql.JSONB, nullable=False),
        sa.Column("segment_key", sa.Text, nullable=False),
        sa.Column("segment_data_version", sa.Text, nullable=False),
        sa.Column("model_name", sa.Text, nullable=False),
        sa.Column("model_version", sa.Text, nullable=False),
        sa.Column("prompt_version", sa.Text, nullable=False),
        sa.Column("input_payload", postgresql.JSONB, nullable=False),
        sa.Column("output_payload", postgresql.JSONB, nullable=True),
        sa.Column("validation_status", sa.Text, nullable=False),
        sa.Column("validation_errors", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("request_hash", name="uq_llm_salary_results_request_hash"),
    )
    op.create_index("ix_llm_salary_results_request_hash", "llm_salary_results", ["request_hash"])
    op.create_index("ix_llm_salary_results_segment_key", "llm_salary_results", ["segment_key"])


def downgrade() -> None:
    op.drop_index("ix_llm_salary_results_segment_key", table_name="llm_salary_results")
    op.drop_index("ix_llm_salary_results_request_hash", table_name="llm_salary_results")
    op.drop_table("llm_salary_results")
    op.drop_index("ix_vacancies_location", table_name="vacancies")
    op.drop_index("ix_vacancies_title", table_name="vacancies")
    op.drop_index("ix_vacancies_segment_key", table_name="vacancies")
    op.drop_table("vacancies")
    op.drop_index("ix_market_segments_segment_key", table_name="market_segments")
    op.drop_table("market_segments")
