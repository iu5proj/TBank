"""Initial schema — all tables + audit trigger.

Revision ID: 001_initial
Revises: None
Create Date: 2025-01-01 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === Users ===
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # === Resumes ===
    op.create_table(
        "resumes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("job_title", sa.String(255), nullable=False),
        sa.Column("experience_years", sa.Numeric(4, 1), nullable=False),
        sa.Column("skills", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column("education_level", sa.String(50), nullable=False, server_default="none"),
        sa.Column("experience_entries", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # === Salary Estimates ===
    op.create_table(
        "salary_estimates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "resume_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("resumes.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("p25_salary", sa.Integer, nullable=False),
        sa.Column("p50_salary", sa.Integer, nullable=False),
        sa.Column("p75_salary", sa.Integer, nullable=False),
        sa.Column("shap_values", postgresql.JSONB, nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # === Recommendations ===
    op.create_table(
        "recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "estimate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("salary_estimates.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("priority", sa.Integer, nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("impact", sa.String(255), nullable=False),
        sa.Column("action", sa.Text, nullable=False),
    )

    # === Vacancies Dataset ===
    op.create_table(
        "vacancies_dataset",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("salary_net", sa.Integer, nullable=True),
        sa.Column("skills_required", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("location", sa.String(255), nullable=True, index=True),
        sa.Column("experience_range", sa.String(50), nullable=True),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("parsed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # === Audit Log Resumes ===
    op.create_table(
        "audit_log_resumes",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("action_type", sa.String(10), nullable=False),
        sa.Column("old_data", postgresql.JSONB, nullable=True),
        sa.Column("new_data", postgresql.JSONB, nullable=True),
        sa.Column("changed_fields", sa.Text, nullable=True),
        sa.Column("performed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # === PL/pgSQL Trigger Function for Audit ===
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_audit_resume_changes()
        RETURNS TRIGGER AS $$
        DECLARE
            v_changed_fields TEXT := '';
            v_old JSONB;
            v_new JSONB;
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                v_old := to_jsonb(OLD);
                v_new := to_jsonb(NEW);

                -- Compute changed fields
                SELECT string_agg(key, ', ')
                INTO v_changed_fields
                FROM jsonb_each(v_new) AS n(key, value)
                WHERE n.key NOT IN ('updated_at', 'created_at')
                  AND (v_old -> n.key IS DISTINCT FROM n.value);

                IF v_changed_fields IS NOT NULL AND v_changed_fields != '' THEN
                    INSERT INTO audit_log_resumes (resume_id, action_type, old_data, new_data, changed_fields)
                    VALUES (NEW.id, 'UPDATE', v_old, v_new, v_changed_fields);
                END IF;

                RETURN NEW;

            ELSIF TG_OP = 'INSERT' THEN
                INSERT INTO audit_log_resumes (resume_id, action_type, old_data, new_data, changed_fields)
                VALUES (NEW.id, 'INSERT', NULL, to_jsonb(NEW), 'ALL');
                RETURN NEW;

            ELSIF TG_OP = 'DELETE' THEN
                INSERT INTO audit_log_resumes (resume_id, action_type, old_data, new_data, changed_fields)
                VALUES (OLD.id, 'DELETE', to_jsonb(OLD), NULL, 'ALL');
                RETURN OLD;
            END IF;

            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # === Attach Trigger to resumes table ===
    op.execute("""
        CREATE TRIGGER trg_audit_resumes
        AFTER INSERT OR UPDATE OR DELETE ON resumes
        FOR EACH ROW EXECUTE FUNCTION fn_audit_resume_changes();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_resumes ON resumes;")
    op.execute("DROP FUNCTION IF EXISTS fn_audit_resume_changes();")
    op.drop_table("audit_log_resumes")
    op.drop_table("vacancies_dataset")
    op.drop_table("recommendations")
    op.drop_table("salary_estimates")
    op.drop_table("resumes")
    op.drop_table("users")
