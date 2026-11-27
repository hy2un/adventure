import re
from contextlib import contextmanager

import psycopg
import streamlit as st


# 테이블별 기본키 설정
PRIMARY_KEYS = {
    "books": ("user_id", "book_key"),
    "reviews": ("user_id", "book_key"),
    "reports": ("user_id", "book_key"),
    "bookmarks": ("user_id", "book_key"),
    "library_books": ("user_id", "book_key"),
    "reading_progress": ("user_id", "book_key"),
    "reading_goals": ("user_id", "month"),
}


# 기존 SQLite 명령을 PostgreSQL 명령으로 변환
def convert_sql(query):
    query = query.strip()

    match = re.fullmatch(
        r"INSERT OR REPLACE INTO\s+"
        r"(\w+)\s*\(([\w,\s]+)\)\s*"
        r"VALUES\s*\(([?,\s]+)\)",
        query,
        flags=re.IGNORECASE,
    )

    if match:
        table, columns, placeholders = match.groups()

        if table not in PRIMARY_KEYS:
            raise ValueError(
                "지원하지 않는 저장 테이블입니다."
            )

        fields = [
            field.strip()
            for field in columns.split(",")
        ]

        keys = PRIMARY_KEYS[table]

        updates = [
            f"{field}=EXCLUDED.{field}"
            for field in fields
            if field not in keys
        ]

        query = (
            f"INSERT INTO {table} "
            f"({','.join(fields)}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT ({','.join(keys)}) "
        )

        if updates:
            query += (
                "DO UPDATE SET "
                + ",".join(updates)
            )
        else:
            query += "DO NOTHING"

    elif query.upper().startswith("INSERT OR REPLACE"):
        raise ValueError(
            "지원하지 않는 저장 명령입니다."
        )

    return query.replace("?", "%s")


# 데이터베이스 명령 실행
class Database:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, params=None):
        converted = convert_sql(query)

        if params is None:
            return self.connection.execute(
                converted
            )

        return self.connection.execute(
            converted,
            params,
        )


# Neon 데이터베이스 연결
@contextmanager
def connect():
    try:
        database_url = str(
            st.secrets["DATABASE_URL"]
        ).strip()

        if not database_url:
            raise ValueError("연결 주소 없음")

    except Exception:
        raise OSError(
            "데이터베이스 연결 설정을 확인하세요."
        ) from None

    with psycopg.connect(
        database_url,
        connect_timeout=10,
        prepare_threshold=None,
    ) as connection:

        yield Database(connection)


# 데이터베이스 연결 상태 확인
@st.cache_data(ttl=60, show_spinner=False)
def check_database():
    try:
        with connect() as db:
            db.execute(
                "SELECT 1 FROM users LIMIT 1"
            )

        return True

    except (psycopg.Error, OSError):
        return False


# 기존 SQLite 로그인 정보 초기화
def reset_legacy_session():
    if not st.session_state.get(
        "bm_neon_session_v1", False
    ):
        st.session_state.clear()

        st.session_state[
            "bm_neon_session_v1"
        ] = True
