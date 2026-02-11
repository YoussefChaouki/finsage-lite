"""initial_schema_documents_and_chunks

Revision ID: 9d4bc4e70648
Revises:
Create Date: 2026-02-11 15:27:35.348830+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "9d4bc4e70648"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- documents table ---
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("cik", sa.String(10), nullable=False),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("filing_type", sa.String(10), nullable=False, server_default="10-K"),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("accession_no", sa.String(20), nullable=False, unique=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("cached_path", sa.Text(), nullable=True),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # --- chunks table ---
    section_enum = sa.Enum(
        "ITEM_1",
        "ITEM_1A",
        "ITEM_7",
        "ITEM_7A",
        "ITEM_8",
        "OTHER",
        name="sectiontype",
    )
    content_type_enum = sa.Enum("TEXT", "TABLE", name="contenttype")

    op.create_table(
        "chunks",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "document_id",
            sa.UUID(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section", section_enum, nullable=False, server_default="OTHER"),
        sa.Column("section_title", sa.String(255), nullable=True),
        sa.Column("content_type", content_type_enum, nullable=False, server_default="TEXT"),
        sa.Column("content_raw", sa.Text(), nullable=False),
        sa.Column("content_context", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # --- indexes ---
    op.create_index(
        "ix_chunks_embedding_cosine",
        "chunks",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_with={"lists": 100},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_chunks_document_section",
        "chunks",
        ["document_id", "section"],
    )
    op.create_index(
        "ix_chunks_metadata",
        "chunks",
        ["metadata"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_chunks_metadata", table_name="chunks")
    op.drop_index("ix_chunks_document_section", table_name="chunks")
    op.drop_index("ix_chunks_embedding_cosine", table_name="chunks")
    op.drop_table("chunks")
    op.drop_table("documents")
    sa.Enum(name="contenttype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="sectiontype").drop(op.get_bind(), checkfirst=True)
    op.execute("DROP EXTENSION IF EXISTS vector")
