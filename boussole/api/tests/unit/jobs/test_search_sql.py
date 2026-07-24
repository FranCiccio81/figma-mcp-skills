"""Tests de construction des requêtes de recherche (D07) par COMPILATION.

Les statements SQLAlchemy sont compilés vers le dialecte postgresql sans base
de données : on vérifie la forme du SQL généré (full-text websearch, filtres
durs, keyset, absence d'OFFSET) plutôt que son exécution.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import Select

from app.modules.jobs.repository import (
    SearchCursor,
    SearchFilters,
    build_search_statement,
)

USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def compile_pg(stmt: Select) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def build_sql(filters: SearchFilters, limit: int = 20,
              cursor: SearchCursor | None = None) -> str:
    return compile_pg(build_search_statement(USER_ID, filters, limit, cursor))


class TestFullText:
    def test_query_uses_websearch_to_tsquery_and_rank(self) -> None:
        sql = build_sql(SearchFilters(q="python fastapi", sort="relevance"))
        assert "websearch_to_tsquery" in sql
        assert "ts_rank_cd" in sql
        assert "@@" in sql  # match full-text sur job_postings.tsv
        assert "job_postings.tsv" in sql

    def test_no_fulltext_clause_without_q(self) -> None:
        sql = build_sql(SearchFilters(sort="date"))
        assert "websearch_to_tsquery" not in sql
        assert "ts_rank_cd" not in sql

    def test_relevance_orders_by_rank_desc_then_id(self) -> None:
        sql = build_sql(SearchFilters(q="python", sort="relevance"))
        order = sql.split("ORDER BY", 1)[1]
        assert "ts_rank_cd" in order
        assert "DESC" in order
        assert "job_postings.id DESC" in order


class TestHardFilters:
    def test_always_filters_on_active_status(self) -> None:
        sql = build_sql(SearchFilters(sort="date"))
        assert "job_postings.status" in sql

    def test_remote_and_contract_use_in_clauses(self) -> None:
        sql = build_sql(
            SearchFilters(remote=("hybrid", "full_remote"), contract=("permanent",),
                          sort="date")
        )
        assert "job_postings.remote IN" in sql
        assert "job_postings.contract IN" in sql

    def test_salary_min_includes_null_salaries_q32(self) -> None:
        # Q32 : les offres sans salaire restent incluses (badge « non
        # communiqué ») — le filtre doit contenir la branche IS NULL.
        sql = build_sql(SearchFilters(salary_min=45000, sort="date"))
        assert "coalesce(job_postings.salary_max, job_postings.salary_min)" in sql
        assert "IS NULL" in sql
        assert ">=" in sql

    def test_salary_min_compares_annualized_amounts(self) -> None:
        # Une offre à 4 000 €/mois (~48 k€/an) ne doit pas être exclue par
        # salary_min=45000 : le filtre annualise via CASE sur salary_period.
        sql = build_sql(SearchFilters(salary_min=45000, sort="date"))
        assert "CASE WHEN (job_postings.salary_period = " in sql
        assert "* CASE" in sql or "CASE WHEN" in sql

    def test_posted_since_filters_on_last_seen_at(self) -> None:
        sql = build_sql(SearchFilters(posted_since_days=7, sort="date"))
        assert "job_postings.last_seen_at >=" in sql

    def test_geo_filter_uses_haversine_on_job_locations(self) -> None:
        sql = build_sql(SearchFilters(lat=45.75, lon=4.85, radius_km=30, sort="date"))
        assert "acos" in sql
        assert "radians" in sql
        assert "job_locations" in sql
        assert "EXISTS" in sql

    def test_country_filter_uses_job_locations(self) -> None:
        sql = build_sql(SearchFilters(country="FR", sort="date"))
        assert "job_locations.country_code" in sql

    def test_hidden_jobs_filtered_via_saved_jobs_join(self) -> None:
        sql = build_sql(SearchFilters(include_hidden=False, sort="date"))
        assert "LEFT OUTER JOIN saved_jobs" in sql
        assert "IS NULL" in sql  # saved.state IS NULL OR saved.state != 'hidden'

    def test_saved_only_filters_on_saved_state(self) -> None:
        sql = build_sql(SearchFilters(saved_only=True, sort="date"))
        assert "LEFT OUTER JOIN saved_jobs" in sql
        assert "saved_jobs_1.state =" in sql


class TestKeysetPagination:
    def test_never_uses_offset(self) -> None:
        for filters in (
            SearchFilters(sort="date"),
            SearchFilters(q="python", sort="relevance"),
        ):
            cursor = SearchCursor(
                sort=filters.sort,
                value=datetime.now(UTC) if filters.sort == "date" else 0.5,
                last_id=uuid.uuid4(),
            )
            sql = build_sql(filters, cursor=cursor)
            assert "OFFSET" not in sql
            assert "LIMIT" in sql

    def test_fetches_limit_plus_one(self) -> None:
        stmt = build_search_statement(USER_ID, SearchFilters(sort="date"), 20, None)
        compiled = stmt.compile(dialect=postgresql.dialect())
        assert "LIMIT" in str(compiled)
        assert 21 in compiled.params.values()  # limit + 1 : détection de page suivante

    def test_date_cursor_compiles_to_tuple_comparison(self) -> None:
        cursor = SearchCursor(sort="date", value=datetime.now(UTC), last_id=uuid.uuid4())
        sql = build_sql(SearchFilters(sort="date"), cursor=cursor)
        assert "(job_postings.last_seen_at, job_postings.id) <" in sql

    def test_relevance_cursor_compiles_to_tuple_on_rank(self) -> None:
        cursor = SearchCursor(sort="relevance", value=0.42, last_id=uuid.uuid4())
        sql = build_sql(SearchFilters(q="python", sort="relevance"), cursor=cursor)
        assert ", job_postings.id) <" in sql
        assert sql.count("ts_rank_cd") >= 2  # sélection + keyset

    def test_date_sort_orders_by_last_seen_then_id_desc(self) -> None:
        sql = build_sql(SearchFilters(sort="date"))
        order = sql.split("ORDER BY", 1)[1]
        assert "job_postings.last_seen_at DESC" in order
        assert "job_postings.id DESC" in order
