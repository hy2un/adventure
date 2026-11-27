"""북플래닛 PAGE 0 | 독서 성장 기록."""

from __future__ import annotations

import calendar
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
import streamlit as st

from bookplanet_db import (
    connect,
    reset_legacy_session,
)

st.set_page_config(
    page_title="북플래닛 | 독서 성장 기록",
    page_icon="📊",
    layout="wide",
)

ROOT = Path(__file__).resolve().parent.parent

TODAY = datetime.now(
    ZoneInfo("Asia/Seoul")
).date()

MONTH = TODAY.strftime("%Y-%m")


# 사용자별 기록 불러오기
def load_data():
    uid = st.session_state.get("bm_user_id")

    if uid is None:
        return {
            "books": dict(
                st.session_state.setdefault("bm_books", {})
            ),
            "reviews": dict(
                st.session_state.setdefault("bm_reviews", {})
            ),
            "reports": dict(
                st.session_state.setdefault("bm_reports", {})
            ),
            "bookmarks": dict(
                st.session_state.setdefault("bm_bookmarks", {})
            ),
            "progress": dict(
                st.session_state.setdefault("rg_progress", {})
            ),
            "goals": dict(
                st.session_state.setdefault("rg_goals", {})
            ),
            "events": list(
                st.session_state.setdefault("rg_events", [])
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


# 월간 독서 목표 저장
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
                "INSERT INTO reading_goals "
                "(user_id,month,target_books) "
                "VALUES(?,?,?) "
                "ON CONFLICT (user_id,month) "
                "DO UPDATE SET "
                "target_books=EXCLUDED.target_books",
                (uid, MONTH, target),
            )

        return True

    except (psycopg.Error, OSError):
        st.error("목표 저장에 실패했습니다.")
        return False


# 독서 진도 저장
def save_progress(
    key, book, total, current, status, old
):
    if total < 1 or current < 0 or current > total:
        st.warning(
            "전체 쪽수와 현재 읽은 쪽수를 확인하세요."
        )
        return

    if status == "완독":
        current = total

    completed_on = (
        (old.get("completed_on") or TODAY.isoformat())
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
        if status == "완독"
        and old.get("status") != "완독"
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
                    "INSERT INTO reading_progress "
                    "(user_id,book_key,title,author,total_pages,"
                    "current_page,status,completed_on,updated_on) "
                    "VALUES(?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT (user_id,book_key) "
                    "DO UPDATE SET "
                    "title=EXCLUDED.title,"
                    "author=EXCLUDED.author,"
                    "total_pages=EXCLUDED.total_pages,"
                    "current_page=EXCLUDED.current_page,"
                    "status=EXCLUDED.status,"
                    "completed_on=EXCLUDED.completed_on,"
                    "updated_on=EXCLUDED.updated_on",
                    (
                        uid,
                        key,
                        value["title"],
                        value["author"],
                        total,
                        current,
                        status,
                        completed_on,
                        value["updated_on"],
                    ),
                )

                db.execute(
                    "INSERT INTO reading_events "
                    "(user_id,book_key,kind,event_date,created_at) "
                    "VALUES(?,?,?,?,?)",
                    (
                        uid,
                        key,
                        kind,
                        event["event_date"],
                        event["created_at"],
                    ),
                )

        st.rerun()

    except (psycopg.Error, OSError):
        st.error("독서 진도 저장에 실패했습니다.")


# 사이드바
def sidebar():
    with st.sidebar:
        st.title("🪐 북플래닛")

        links = [
            ("main.py", "📖 도서 활동"),
            (
                "pages/0_독서_성장_기록.py",
                "📊 독서 성장 기록"
            ),
            (
                "pages/1_독서_집중실.py",
                "⏱️ 독서 집중실"
            ),
            (
                "pages/2_숏폼_브레이커.py",
                "🎮 숏폼 브레이커"
            ),
        ]

        for path, label in links:
            if (ROOT / path).is_file():
                st.page_link(
                    path,
                    label=label,
                    use_container_width=True,
                )

        st.divider()
        st.markdown("#### 👤 내 계정")

        uid = st.session_state.get("bm_user_id")

        if uid is not None:
            username = (
                st.session_state.get("bm_username")
                or "사용자"
            )

            st.success(f"{username}님 로그인 중")

        else:
            st.info(
                "도서 활동에서 로그인할 수 있습니다."
            )


# 독서 활동 달력
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
        for col, day in zip(st.columns(7), week):

            if not day:
                col.write(" ")

            elif f"{MONTH}-{day:02d}" in active_days:
                col.markdown(f"🟢 **{day}**")

            else:
                col.write(str(day))

    st.caption(
        "🟢 기록을 저장한 날짜를 표시합니다."
    )


# 독후감 열람 전용
def show_report(report):
    st.markdown("**📝 독후감**")

    fields = [
        ("1. 읽게 된 이유", "reason"),
        ("2. 기억에 남는 내용", "scene"),
        ("3. 읽은 뒤의 생각과 배운 점", "thought"),
    ]

    for title, field in fields:
        st.markdown(f"**{title}**")
        st.write(report.get(field, ""))

    st.caption(
        "저장된 독후감은 열람만 가능합니다."
    )


# 한줄평 및 책갈피 수정 화면 이동
def open_activity(key, book, zone):
    if zone not in (0, 2):
        return

    st.session_state.setdefault(
        "bm_books", {}
    )[key] = book

    st.session_state.bm_selected = key
    st.session_state.bm_zone = zone

    st.switch_page("main.py")


# 메인 화면
def main():
    reset_legacy_session()
    sidebar()

    st.title("📊 독서 성장 기록")

    st.caption(
        "독후감과 독서 활동을 확인하고 "
        "목표와 진도를 관리하는 공간입니다."
    )

    if st.session_state.get("bm_user_id") is None:
        st.info(
            "로그인하면 독서 기록과 목표를 "
            "외부 데이터베이스에 저장할 수 있습니다."
        )

    try:
        data = load_data()

    except (psycopg.Error, OSError):
        st.error("독서 기록을 불러올 수 없습니다.")
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
        and str(
            item["completed_on"] or ""
        ).startswith(MONTH)
        for item in progress.values()
    )

    active_days = len({
        event["event_date"]
        for event in events
        if str(
            event["event_date"]
        ).startswith(MONTH)
    })

    # 독서 활동 요약
    labels = [
        "완독한 책",
        "이번 달 완독",
        "작성한 독후감",
        "이번 달 활동일",
    ]

    values = [
        f"{completed}권",
        f"{monthly}권",
        f"{len(reports)}편",
        f"{active_days}일",
    ]

    for col, label, value in zip(
        st.columns(4), labels, values
    ):
        col.metric(label, value)

    st.divider()

    # 월간 목표 설정
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

        st.caption(
            f"{monthly} / {target}권 완독"
        )

    st.progress(
        min(1.0, monthly / max(target, 1))
    )

    st.divider()

    # 책별 독서 진도
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

        with st.form(f"rg_progress_{key}"):
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

    # 작성한 독서 활동 열람
    st.markdown("### 📝 작성한 독서 활동 확인")

    st.caption(
        "독후감은 도서 활동에서 작성하며, "
        "저장된 독후감은 이곳에서 열람만 가능합니다."
    )

    keys = list(
        dict.fromkeys([
            *reports,
            *reviews,
            *bookmarks,
        ])
    )

    if not keys:
        st.info("아직 작성한 기록이 없습니다.")

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
                show_report(reports[key])

            if key in reviews:
                st.divider()
                st.markdown("**💬 한줄평**")

                st.write(
                    "⭐" * int(reviews[key]["rating"]),
                    reviews[key]["text"],
                )

                if st.button(
                    "한줄평 수정하기",
                    key=f"rg_review_{key}",
                ):
                    open_activity(key, book, 0)

            if key in bookmarks:
                st.divider()
                st.markdown("**🔖 책갈피 문장**")

                st.write(
                    bookmarks[key].get("quote", "")
                )

                if st.button(
                    "책갈피 수정하기",
                    key=f"rg_bookmark_{key}",
                ):
                    open_activity(key, book, 2)

    st.caption(
        "로그인한 사용자의 독서 목표와 진도, "
        "활동 기록은 Neon 외부 데이터베이스에 저장됩니다."
    )


if __name__ == "__main__":
    main()
