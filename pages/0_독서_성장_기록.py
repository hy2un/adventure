"""북플래닛 PAGE 0 | 독서 성장 기록."""

from __future__ import annotations

import calendar
from datetime import date, datetime
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

MIN_YEAR = 2000
MAX_YEAR = 2100


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

        # 과거 활동까지 확인할 수 있도록
        # 기존 최대 1000개 조회 제한 제거
        events = db.execute(
            "SELECT book_key,kind,event_date,created_at "
            "FROM reading_events WHERE user_id=? "
            "ORDER BY id DESC",
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


# 달력 초기 설정
def init_calendar():
    st.session_state.setdefault(
        "rg_calendar_date",
        TODAY,
    )


# 달력 선택 날짜 변경
def set_calendar_date(selected):
    st.session_state["rg_calendar_date"] = selected

    st.session_state["rg_calendar_year"] = (
        selected.year
    )

    st.session_state["rg_calendar_month"] = (
        selected.month
    )


# 이전 달 및 다음 달 이동
def move_calendar_month(direction):
    selected = st.session_state.get(
        "rg_calendar_date",
        TODAY,
    )

    year = selected.year
    month = selected.month + direction

    if month < 1:
        year -= 1
        month = 12

    elif month > 12:
        year += 1
        month = 1

    if not MIN_YEAR <= year <= MAX_YEAR:
        return

    last_day = calendar.monthrange(
        year,
        month,
    )[1]

    day = min(
        selected.day,
        last_day,
    )

    set_calendar_date(
        date(year, month, day)
    )


# 연도 및 월 직접 선택
def change_calendar_month():
    selected = st.session_state.get(
        "rg_calendar_date",
        TODAY,
    )

    year = int(
        st.session_state["rg_calendar_year"]
    )

    month = int(
        st.session_state["rg_calendar_month"]
    )

    last_day = calendar.monthrange(
        year,
        month,
    )[1]

    day = min(
        selected.day,
        last_day,
    )

    set_calendar_date(
        date(year, month, day)
    )


# 이번 달로 이동
def return_to_today():
    set_calendar_date(TODAY)


# 선택한 날짜의 활동 기록 확인
def show_daily_events(selected, events, books):
    selected_text = selected.isoformat()

    daily_events = [
        event
        for event in events
        if str(event["event_date"]) == selected_text
    ]

    st.markdown(
        f"#### 📅 {selected.year}년 "
        f"{selected.month}월 {selected.day}일 활동 기록"
    )

    if not daily_events:
        st.info(
            "선택한 날짜에 기록된 독서 활동이 없습니다."
        )

        return

    st.caption(
        f"총 {len(daily_events)}개의 독서 활동"
    )

    icons = {
        "독후감": "📝",
        "한줄평": "💬",
        "책갈피": "🔖",
        "독서 진도": "📖",
        "완독": "🏆",
    }

    daily_events.sort(
        key=lambda event: str(
            event.get("created_at", "")
        ),
        reverse=True,
    )

    for event in daily_events:
        key = event["book_key"]

        book = books.get(
            key,
            {
                "title": key.split("|")[0],
                "author": "",
            },
        )

        kind = event["kind"]

        icon = icons.get(
            kind,
            "📚",
        )

        created = str(
            event.get("created_at", "")
        )

        try:
            timestamp = datetime.fromisoformat(
                created
            )

            if timestamp.tzinfo is not None:
                timestamp = timestamp.astimezone(
                    ZoneInfo("Asia/Seoul")
                )

            activity_time = timestamp.strftime(
                "%H:%M"
            )

        except (ValueError, TypeError):
            activity_time = ""

        with st.container(border=True):
            st.markdown(
                f"**📘 {book['title']}**"
            )

            if book.get("author"):
                st.caption(book["author"])

            st.write(
                f"{icon} {kind}"
            )

            if activity_time:
                st.caption(
                    f"기록 시간: {activity_time}"
                )


# 독서 활동 달력
def activity_calendar(events, books):
    init_calendar()

    selected = st.session_state[
        "rg_calendar_date"
    ]

    st.markdown("### 🗓️ 독서 활동 달력")

    # 위젯과 현재 선택 날짜 동기화
    st.session_state["rg_calendar_year"] = (
        selected.year
    )

    st.session_state["rg_calendar_month"] = (
        selected.month
    )

    # 달력 이동 버튼
    left, middle, right = st.columns(3)

    with left:
        st.button(
            "◀ 이전 달",
            key="rg_previous_month",
            use_container_width=True,
            on_click=move_calendar_month,
            args=(-1,),
            disabled=(
                selected.year == MIN_YEAR
                and selected.month == 1
            ),
        )

    with middle:
        st.button(
            "이번 달",
            key="rg_today_month",
            use_container_width=True,
            on_click=return_to_today,
        )

    with right:
        st.button(
            "다음 달 ▶",
            key="rg_next_month",
            use_container_width=True,
            on_click=move_calendar_month,
            args=(1,),
            disabled=(
                selected.year == MAX_YEAR
                and selected.month == 12
            ),
        )

    # 연도 및 월 직접 선택
    year_col, month_col = st.columns(2)

    with year_col:
        st.selectbox(
            "연도 선택",
            list(
                range(
                    MIN_YEAR,
                    MAX_YEAR + 1,
                )
            ),
            format_func=lambda y: f"{y}년",
            key="rg_calendar_year",
            on_change=change_calendar_month,
        )

    with month_col:
        st.selectbox(
            "월 선택",
            list(range(1, 13)),
            format_func=lambda m: f"{m}월",
            key="rg_calendar_month",
            on_change=change_calendar_month,
        )

    selected = st.session_state[
        "rg_calendar_date"
    ]

    year = selected.year
    month = selected.month

    displayed_month = (
        f"{year:04d}-{month:02d}"
    )

    # 해당 월 활동 날짜
    active_days = {
        str(event["event_date"])
        for event in events
        if str(
            event["event_date"]
        ).startswith(displayed_month)
    }

    st.markdown(
        f"""
        <div style="
            text-align:center;
            font-size:26px;
            font-weight:700;
            color:#397B57;
            padding:16px 0;
        ">
            {year}년 {month}월
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 요일 표시
    weekdays = (
        "월", "화", "수", "목",
        "금", "토", "일",
    )

    for index, (col, name) in enumerate(
        zip(st.columns(7), weekdays)
    ):
        color = (
            "#D65A5A"
            if index == 6
            else "#4683C5"
            if index == 5
            else "#668173"
        )

        col.markdown(
            f"""
            <div style="
                text-align:center;
                font-weight:700;
                color:{color};
            ">
                {name}
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 월별 달력 생성
    weeks = calendar.Calendar(
        firstweekday=0
    ).monthdayscalendar(
        year,
        month,
    )

    for week in weeks:
        columns = st.columns(7)

        for col, day in zip(
            columns,
            week,
        ):
            if day == 0:
                col.write(" ")
                continue

            current_date = date(
                year,
                month,
                day,
            )

            date_text = (
                current_date.isoformat()
            )

            has_activity = (
                date_text in active_days
            )

            is_selected = (
                current_date == selected
            )

            # 독서 기록이 있는 날짜 표시
            label = (
                f"🟢 {day}"
                if has_activity
                else str(day)
            )

            with col:
                st.button(
                    label,
                    key=f"rg_day_{date_text}",
                    use_container_width=True,
                    type=(
                        "primary"
                        if is_selected
                        else "secondary"
                    ),
                    on_click=set_calendar_date,
                    args=(current_date,),
                    help=(
                        "독서 활동 기록 보기"
                        if has_activity
                        else "날짜 선택"
                    ),
                )

    st.caption(
        "🟢 독서 활동 기록이 있는 날짜입니다. "
        "날짜를 클릭하면 활동 내용을 확인할 수 있습니다."
    )

    st.caption(
        f"{month}월 독서 활동일: "
        f"{len(active_days)}일"
    )

    st.divider()

    # 선택한 날짜의 상세 기록
    show_daily_events(
        selected,
        events,
        books,
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

        st.write(
            report.get(field, "")
        )

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
        st.error(
            "독서 기록을 불러올 수 없습니다."
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
        st.columns(4),
        labels,
        values,
    ):
        col.metric(
            label,
            value,
        )

    st.divider()

    # 월간 목표 설정
    st.markdown(
        "### 🎯 이번 달 독서 목표"
    )

    target = int(
        goals.get(MONTH, 4)
    )

    left, right = st.columns([2, 1])

    with left:
        with st.form("rg_goal"):
            requested = st.number_input(
                "이번 달 완독 목표(권)",
                min_value=1,
                max_value=30,
                value=max(
                    1,
                    min(30, target),
                ),
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
        min(
            1.0,
            monthly / max(target, 1),
        )
    )

    st.divider()

    # 책별 독서 진도
    st.markdown(
        "### 📖 책별 독서 진도"
    )

    if not books:
        st.info(
            "'도서 활동'에서 책을 선택하면 "
            "이곳에 나타납니다."
        )

    else:
        keys = list(books)

        current = st.session_state.get(
            "bm_selected"
        )

        key = st.selectbox(
            "진도 기록할 책",
            keys,
            index=(
                keys.index(current)
                if current in keys
                else 0
            ),
            format_func=lambda k: (
                books[k]["title"]
            ),
        )

        old = progress.get(
            key,
            {},
        )

        with st.form(f"rg_progress_{key}"):
            total = st.number_input(
                "전체 쪽수",
                min_value=1,
                max_value=100000,
                value=max(
                    1,
                    int(old.get("total_pages", 1)),
                ),
            )

            current_page = st.number_input(
                "현재 읽은 쪽수",
                min_value=0,
                max_value=100000,
                value=max(
                    0,
                    int(old.get("current_page", 0)),
                ),
            )

            status = st.radio(
                "상태",
                ("읽는 중", "완독"),
                horizontal=True,
                index=(
                    1
                    if old.get("status") == "완독"
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

    # 월 이동 및 날짜 선택이 가능한 달력
    activity_calendar(
        events,
        books,
    )

    st.divider()

    # 작성한 독서 활동 열람
    st.markdown(
        "### 📝 작성한 독서 활동 확인"
    )

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

            # 독후감은 열람만 가능
            if key in reports:
                show_report(
                    reports[key]
                )

            # 한줄평은 수정 가능
            if key in reviews:
                st.divider()

                st.markdown(
                    "**💬 한줄평**"
                )

                st.write(
                    "⭐" * int(
                        reviews[key]["rating"]
                    ),
                    reviews[key]["text"],
                )

                if st.button(
                    "한줄평 수정하기",
                    key=f"rg_review_{key}",
                ):
                    open_activity(
                        key,
                        book,
                        0,
                    )

            # 책갈피는 수정 가능
            if key in bookmarks:
                st.divider()

                st.markdown(
                    "**🔖 책갈피 문장**"
                )

                st.write(
                    bookmarks[key].get(
                        "quote",
                        "",
                    )
                )

                if st.button(
                    "책갈피 수정하기",
                    key=f"rg_bookmark_{key}",
                ):
                    open_activity(
                        key,
                        book,
                        2,
                    )

    st.caption(
        "로그인한 사용자의 독서 목표와 진도, "
        "활동 기록은 Neon 외부 데이터베이스에 저장됩니다."
    )


if __name__ == "__main__":
    main()
