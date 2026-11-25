
"""북플래닛 PAGE 0 | 독서 성장 기록.

도서 활동에서 작성한 독후감, 한줄평, 책갈피 조회.
월간 목표, 독서 진도, 완독 여부, 활동 달력 관리.
"""
from __future__ import annotations

import calendar
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

st.set_page_config(
    page_title="북플래닛 | 독서 성장 기록",
    page_icon="📊",
    layout="wide",
)

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = (
    Path(tempfile.gettempdir())
    / "bookmoa_local"
    / "records.db"
)
TODAY = datetime.now(ZoneInfo("Asia/Seoul")).date()
MONTH = TODAY.strftime("%Y-%m")


def connect():
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    return sqlite3.connect(
        str(DB_PATH), timeout=5
    )


def ensure_tables():
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS reading_progress (
                user_id INTEGER NOT NULL,
                book_key TEXT NOT NULL,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                total_pages INTEGER NOT NULL DEFAULT 0,
                current_page INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT '읽는 중',
                completed_on TEXT,
                updated_on TEXT NOT NULL,
                PRIMARY KEY(user_id, book_key)
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS reading_goals (
                user_id INTEGER NOT NULL,
                month TEXT NOT NULL,
                target_books INTEGER NOT NULL,
                PRIMARY KEY(user_id, month)
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS reading_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                book_key TEXT NOT NULL,
                kind TEXT NOT NULL,
                event_date TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


def load_data():
    uid = st.session_state.get("bm_user_id")

    if uid is None:
        return {
            "books": dict(
                st.session_state.setdefault(
                    "bm_books", {}
                )
            ),
            "reviews": dict(
                st.session_state.setdefault(
                    "bm_reviews", {}
                )
            ),
            "reports": dict(
                st.session_state.setdefault(
                    "bm_reports", {}
                )
            ),
            "bookmarks": dict(
                st.session_state.setdefault(
                    "bm_bookmarks", {}
                )
            ),
            "progress": dict(
                st.session_state.setdefault(
                    "rg_progress", {}
                )
            ),
            "goals": dict(
                st.session_state.setdefault(
                    "rg_goals", {}
                )
            ),
            "events": list(
                st.session_state.setdefault(
                    "rg_events", []
                )
            ),
        }

    with connect() as db:
        books = db.execute(
            "SELECT book_key,title,author "
            "FROM books WHERE user_id=?",
            (uid,),
        ).fetchall()

        reviews = db.execute(
            "SELECT book_key,rating,content "
            "FROM reviews WHERE user_id=?",
            (uid,),
        ).fetchall()

        reports = db.execute(
            "SELECT book_key,reason,scene,thought "
            "FROM reports WHERE user_id=?",
            (uid,),
        ).fetchall()

        bookmarks = db.execute(
            "SELECT book_key,quote,palette "
            "FROM bookmarks WHERE user_id=?",
            (uid,),
        ).fetchall()

        progress = db.execute(
            "SELECT book_key,title,author,total_pages,"
            "current_page,status,completed_on,updated_on "
            "FROM reading_progress WHERE user_id=?",
            (uid,),
        ).fetchall()

        goals = db.execute(
            "SELECT month,target_books "
            "FROM reading_goals WHERE user_id=?",
            (uid,),
        ).fetchall()

        events = db.execute(
            "SELECT book_key,kind,event_date,created_at "
            "FROM reading_events WHERE user_id=? "
            "ORDER BY id DESC LIMIT 1000",
            (uid,),
        ).fetchall()

    return {
        "books": {
            key: {
                "title": title,
                "author": author,
            }
            for key, title, author in books
        },
        "reviews": {
            key: {
                "rating": rating,
                "text": text,
            }
            for key, rating, text in reviews
        },
        "reports": {
            key: {
                "reason": reason,
                "scene": scene,
                "thought": thought,
            }
            for key, reason, scene, thought in reports
        },
        "bookmarks": {
            key: {
                "quote": quote,
                "palette": palette,
            }
            for key, quote, palette in bookmarks
        },
        "progress": {
            key: {
                "title": title,
                "author": author,
                "total_pages": total,
                "current_page": current,
                "status": status,
                "completed_on": completed,
                "updated_on": updated,
            }
            for (
                key, title, author, total,
                current, status, completed, updated
            ) in progress
        },
        "goals": {
            month: target
            for month, target in goals
        },
        "events": [
            {
                "book_key": key,
                "kind": kind,
                "event_date": day,
                "created_at": created,
            }
            for key, kind, day, created in events
        ],
    }


def save_goal(target):
    uid = st.session_state.get("bm_user_id")

    if uid is None:
        st.session_state.setdefault(
            "rg_goals", {}
        )[MONTH] = target
        return True

    try:
        with connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO reading_goals "
                "(user_id,month,target_books) "
                "VALUES(?,?,?)",
                (uid, MONTH, target),
            )
        return True
    except (sqlite3.Error, OSError):
        st.error("목표 저장에 실패했습니다.")
        return False


def save_progress(
    key, book, total, current, status, old
):
    if total < 1 or current > total:
        st.warning(
            "전체 쪽수와 현재 읽은 쪽수를 확인하세요."
        )
        return

    if status == "완독":
        current = total

    completed_on = (
        old.get("completed_on")
        or TODAY.isoformat()
        if status == "완독"
        else None
    )

    value = {
        "title": book["title"],
        "author": book.get("author", ""),
        "total_pages": total,
        "current_page": current,
        "status": status,
        "completed_on": completed_on,
        "updated_on": TODAY.isoformat(),
    }

    kind = (
        "완독"
        if (
            status == "완독"
            and old.get("status") != "완독"
        )
        else "독서 진도"
    )

    moment = datetime.now(
        ZoneInfo("Asia/Seoul")
    )

    event = {
        "book_key": key,
        "kind": kind,
        "event_date": moment.date().isoformat(),
        "created_at": moment.isoformat(
            timespec="seconds"
        ),
    }

    uid = st.session_state.get("bm_user_id")

    try:
        if uid is None:
            st.session_state.setdefault(
                "rg_progress", {}
            )[key] = value
            st.session_state.setdefault(
                "rg_events", []
            ).append(event)

        else:
            with connect() as db:
                db.execute(
                    "INSERT OR REPLACE INTO reading_progress "
                    "(user_id,book_key,title,author,total_pages,"
                    "current_page,status,completed_on,updated_on) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        uid, key, value["title"],
                        value["author"],
                        total, current, status,
                        completed_on, value["updated_on"],
                    ),
                )
                db.execute(
                    "INSERT INTO reading_events "
                    "(user_id,book_key,kind,event_date,created_at) "
                    "VALUES(?,?,?,?,?)",
                    (
                        uid, key, kind,
                        event["event_date"],
                        event["created_at"],
                    ),
                )

        st.rerun()

    except (sqlite3.Error, OSError):
        st.error("독서 진도 저장에 실패했습니다.")


def sidebar():
    with st.sidebar:
        st.title("🪐 북플래닛")

        for path, label in (
            ("main.py", "📖 도서 활동"),
            (
                "pages/0_독서_성장_기록.py",
                "📊 독서 성장 기록",
            ),
            (
                "pages/1_독서_집중실.py",
                "⏱️ 독서 집중실",
            ),
            (
                "pages/2_숏폼_브레이커.py",
                "🎮 숏폼 브레이커",
            ),
        ):
            if (ROOT / path).is_file():
                st.page_link(
                    path,
                    label=label,
                    use_container_width=True,
                )

        st.divider()

        uid = st.session_state.get("bm_user_id")

        if uid is not None:
            st.success(
                f"{st.session_state.get('bm_username', '사용자')}"
                "님 로그인 중"
            )
        else:
            st.caption(
                "도서 활동에서 로그인할 수 있습니다."
            )


def activity_calendar(events):
    st.markdown(
        f"### 🗓️ {TODAY.year}년 "
        f"{TODAY.month}월 독서 활동"
    )

    active_days = {
        str(event["event_date"])
        for event in events
        if str(event["event_date"]).startswith(MONTH)
    }

    for col, name in zip(
        st.columns(7),
        ("월", "화", "수", "목", "금", "토", "일"),
    ):
        col.markdown(f"**{name}**")

    for week in calendar.monthcalendar(
        TODAY.year, TODAY.month
    ):
        for col, day in zip(
            st.columns(7), week
        ):
            if not day:
                col.write(" ")
            elif f"{MONTH}-{day:02d}" in active_days:
                col.markdown(f"🟢 **{day}**")
            else:
                col.write(str(day))

    st.caption(
        "🟢 기록을 저장한 날짜를 표시합니다."
    )


def main():
    sidebar()

    st.title("📊 독서 성장 기록")
    st.caption(
        "독후감과 독서 활동을 확인하고 "
        "목표와 진도를 관리하는 공간입니다."
    )

    try:
        ensure_tables()
        data = load_data()
    except (sqlite3.Error, OSError):
        st.error(
            "기록을 불러올 수 없습니다."
        )
        return

    books = data["books"]
    reviews = data["reviews"]
    reports = data["reports"]
    bookmarks = data["bookmarks"]
    progress = data["progress"]
    goals = data["goals"]
    events = data["events"]

    for key, item in progress.items():
        books.setdefault(
            key,
            {
                "title": item["title"],
                "author": item["author"],
            },
        )

    completed = sum(
        item["status"] == "완독"
        for item in progress.values()
    )
    monthly = sum(
        item["status"] == "완독"
        and str(item["completed_on"] or "").startswith(MONTH)
        for item in progress.values()
    )
    active_days = len({
        event["event_date"]
        for event in events
        if str(event["event_date"]).startswith(MONTH)
    })

    for col, label, value in zip(
        st.columns(4),
        (
            "완독한 책",
            "이번 달 완독",
            "작성한 독후감",
            "이번 달 활동일",
        ),
        (
            f"{completed}권",
            f"{monthly}권",
            f"{len(reports)}편",
            f"{active_days}일",
        ),
    ):
        col.metric(label, value)

    st.divider()
    st.markdown("### 🎯 이번 달 독서 목표")

    target = int(goals.get(MONTH, 4))

    left, right = st.columns([2, 1])

    with left:
        with st.form("rg_goal"):
            requested = st.number_input(
                "이번 달 완독 목표(권)",
                min_value=1,
                max_value=30,
                value=max(1, min(30, target)),
            )
            clicked = st.form_submit_button(
                "목표 저장",
                type="primary",
            )

        if clicked and save_goal(int(requested)):
            st.rerun()

    with right:
        st.metric(
            "달성률",
            f"{monthly / max(target, 1):.0%}",
        )
        st.caption(f"{monthly} / {target}권 완독")

    st.progress(
        min(1.0, monthly / max(target, 1))
    )

    st.divider()
    st.markdown("### 📖 책별 독서 진도")

    if not books:
        st.info(
            "'도서 활동'에서 책을 선택하면 "
            "이곳에 나타납니다."
        )
    else:
        keys = list(books)
        current = st.session_state.get("bm_selected")

        key = st.selectbox(
            "진도 기록할 책",
            keys,
            index=(
                keys.index(current)
                if current in keys else 0
            ),
            format_func=lambda k: books[k]["title"],
        )
        old = progress.get(key, {})

        with st.form("rg_progress"):
            total = st.number_input(
                "전체 쪽수",
                min_value=1,
                max_value=100000,
                value=max(
                    1, int(old.get("total_pages", 1))
                ),
            )
            current_page = st.number_input(
                "현재 읽은 쪽수",
                min_value=0,
                max_value=100000,
                value=max(
                    0, int(old.get("current_page", 0))
                ),
            )
            status = st.radio(
                "상태",
                ("읽는 중", "완독"),
                horizontal=True,
                index=(
                    1 if old.get("status") == "완독"
                    else 0
                ),
            )
            clicked = st.form_submit_button(
                "독서 진도 저장",
                type="primary",
            )

        if clicked:
            save_progress(
                key,
                books[key],
                int(total),
                int(current_page),
                status,
                old,
            )

        if old:
            st.progress(
                min(
                    1.0,
                    old["current_page"]
                    / max(old["total_pages"], 1),
                )
            )
            st.caption(
                f"{old['current_page']} / "
                f"{old['total_pages']}쪽 · "
                f"{old['status']}"
            )

    st.divider()
    activity_calendar(events)
    st.divider()

    st.markdown("### 📝 작성한 독서 활동 확인")
    st.caption(
        "독후감은 도서 활동에서 작성하고 "
        "이곳에서는 확인합니다."
    )

    keys = list(
        dict.fromkeys([
            *reports,
            *reviews,
            *bookmarks,
        ])
    )

    if not keys:
        st.info(
            "아직 작성한 기록이 없습니다."
        )

    for key in keys:
        book = books.get(
            key,
            {
                "title": key.split("|")[0],
                "author": "",
            },
        )
        labels = [
            label
            for label, source in (
                ("독후감", reports),
                ("한줄평", reviews),
                ("책갈피", bookmarks),
            )
            if key in source
        ]

        with st.expander(
            f"📘 {book['title']} · "
            f"{' · '.join(labels)}"
        ):
            if key in reports:
                st.markdown("**📝 독후감**")
                for title, field in (
                    ("읽게 된 이유", "reason"),
                    ("기억에 남는 내용", "scene"),
                    ("읽은 뒤 생각", "thought"),
                ):
                    st.markdown(f"**{title}**")
                    st.write(reports[key][field])

            if key in reviews:
                st.markdown("**💬 한줄평**")
                st.write(
                    "⭐" * int(reviews[key]["rating"]),
                    reviews[key]["text"],
                )

            if key in bookmarks:
                st.markdown("**🔖 책갈피 문장**")
                st.write(
                    bookmarks[key].get("quote", "")
                )

            if st.button(
                "도서 활동에서 수정하기",
                key=f"rg_edit_{key}",
            ):
                st.session_state.setdefault(
                    "bm_books", {}
                )[key] = book
                st.session_state.bm_selected = key
                st.session_state.bm_zone = (
                    1 if key in reports
                    else 0 if key in reviews
                    else 2
                )
                st.switch_page("main.py")

    st.caption(
        "현재는 기존 SQLite 저장 방식을 유지합니다. "
        "서버 재배포 시 기록 보존이 보장되지 않습니다."
    )


if __name__ == "__main__":
    main()
