"""책모아 · 나의 서재.

내가 별도 저장한 책만 이곳에 나타납니다.
'현재 활동 도서'와 '나의 서재에 담기'는 독립적인 동작입니다.
"""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="책모아 | 나의 서재",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = (
    Path(tempfile.gettempdir())
    / "bookmoa_local"
    / "records.db"
)


def book_id(title, author):
    return (
        title.strip().casefold()
        + "|"
        + author.strip().casefold()
    )


def get_connection():
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )
    return sqlite3.connect(
        DB_PATH, timeout=5
    )


def ensure_library_table():
    try:
        with get_connection() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS library_books (
                    user_id INTEGER NOT NULL,
                    book_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    publisher TEXT NOT NULL DEFAULT '',
                    image_url TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY(user_id, book_key)
                )
            """)
        return True
    except (sqlite3.Error, OSError):
        return False


def reload_library():
    """로그인한 경우 SQLite에서 읽는다."""
    st.session_state.setdefault(
        "bm_library_books", {}
    )

    uid = st.session_state.get(
        "bm_user_id"
    )
    if uid is None:
        return True

    try:
        with get_connection() as db:
            rows = db.execute(
                "SELECT book_key,title,author,"
                "publisher,image_url "
                "FROM library_books WHERE user_id=?",
                (uid,)
            ).fetchall()

        st.session_state.bm_library_books = {
            k: {
                "title": title,
                "author": author,
                "publisher": publisher,
                "image_url": image_url
            }
            for (
                k, title, author,
                publisher, image_url
            ) in rows
        }
        return True

    except (sqlite3.Error, OSError):
        return False


def add_library(book):
    title = book.get(
        "title", ""
    ).strip()
    author = book.get(
        "author", ""
    ).strip()

    if not title:
        st.warning(
            "책 제목을 입력해 주세요."
        )
        return

    key = book_id(title, author)
    data = {
        "title": title,
        "author": author,
        "publisher": book.get(
            "publisher", ""
        ),
        "image_url": book.get(
            "image_url", ""
        ),
    }

    uid = st.session_state.get(
        "bm_user_id"
    )

    if uid is not None:
        try:
            with get_connection() as db:
                db.execute(
                    "INSERT OR REPLACE INTO library_books "
                    "(user_id,book_key,title,author,"
                    "publisher,image_url) "
                    "VALUES(?,?,?,?,?,?)",
                    (
                        uid,
                        key,
                        data["title"],
                        data["author"],
                        data["publisher"],
                        data["image_url"],
                    )
                )
        except (sqlite3.Error, OSError):
            st.error(
                "나의 서재에 책을 저장하지 못했습니다."
            )
            return

    st.session_state.bm_library_books[key] = data
    st.rerun()


def remove_library(key):
    uid = st.session_state.get(
        "bm_user_id"
    )

    if uid is not None:
        try:
            with get_connection() as db:
                db.execute(
                    "DELETE FROM library_books "
                    "WHERE user_id=? AND book_key=?",
                    (uid, key)
                )
        except (sqlite3.Error, OSError):
            st.error(
                "서재에서 책을 삭제하지 못했습니다."
            )
            return

    st.session_state.bm_library_books.pop(
        key, None
    )
    st.session_state.pop(
        "bm_library_pending_delete",
        None
    )
    st.rerun()


def use_for_activity(key, data):
    """서재의 책을 활동 도서로 선택한다."""
    st.session_state.setdefault(
        "bm_books", {}
    )
    st.session_state.bm_books[key] = {
        "title": data["title"],
        "author": data["author"],
    }

    uid = st.session_state.get(
        "bm_user_id"
    )

    if uid is not None:
        try:
            with get_connection() as db:
                db.execute(
                    "INSERT OR REPLACE INTO books "
                    "(user_id,book_key,title,author) "
                    "VALUES(?,?,?,?)",
                    (
                        uid,
                        key,
                        data["title"],
                        data["author"]
                    )
                )
        except (sqlite3.Error, OSError):
            st.error(
                "활동할 책 정보를 저장하지 못했습니다."
            )
            return

    st.session_state.bm_selected = key
    st.switch_page("main.py")


def sidebar():
    with st.sidebar:
        st.title("📚 책모아")

        st.page_link(
            "main.py",
            label="🏠 도서관",
            use_container_width=True
        )

        links = [
            (
                "pages/0_나의_서재.py",
                "📚 나의 서재"
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
                    use_container_width=True
                )

        st.divider()

        if st.session_state.get(
            "bm_user_id"
        ) is not None:
            user = (
                st.session_state.get("bm_username")
                or "사용자"
            )
            st.success(
                f"{user}님 로그인 중"
            )
        else:
            st.info(
                "로그인하지 않으면 서재는 "
                "현재 접속 중에만 유지됩니다."
            )


sidebar()

st.title("📚 나의 서재")
st.caption(
    "'서재에 담기'를 누른 책만 보관합니다. "
    "활동할 책을 선택하는 것과는 별개입니다."
)

if (
    not ensure_library_table()
    or not reload_library()
):
    st.warning(
        "서재 저장소를 읽지 못했습니다. "
        "현재 접속의 기록만 표시될 수 있습니다."
    )

library = st.session_state.setdefault(
    "bm_library_books", {}
)

st.metric(
    "서재에 담아둔 책",
    f"{len(library)}권"
)

with st.expander(
    "＋ 서재에 책 직접 담기"
):
    with st.form(
        "library_manual_book",
        clear_on_submit=True
    ):
        a, b = st.columns([2, 1])
        title = a.text_input(
            "책 제목 *",
            max_chars=100
        )
        author = b.text_input(
            "저자 (선택)",
            max_chars=70
        )
        add = st.form_submit_button(
            "📚 나의 서재에 담기",
            type="primary"
        )

    if add:
        add_library({
            "title": title,
            "author": author
        })


if not library:
    st.info(
        "아직 서재에 담은 책이 없어요. "
        "도서관에서 검색한 뒤 "
        "'나의 서재에 담기'를 누르거나 "
        "위에서 직접 추가하세요."
    )
else:
    st.markdown("### 나의 책 목록")
    st.caption(
        "'이 책으로 활동'을 누르면 "
        "메인 도서관으로 이동합니다."
    )

    items = list(library.items())

    for start in range(
        0, len(items), 3
    ):
        cols = st.columns(
            3, gap="small"
        )
        for col, (key, book) in zip(
            cols,
            items[start:start+3]
        ):
            with col:
                with st.container(border=True):
                    image = book.get(
                        "image_url", ""
                    )

                    if (
                        isinstance(image, str)
                        and image.startswith(
                            ("https://", "http://")
                        )
                    ):
                        try:
                            st.image(
                                image, width=100
                            )
                        except Exception:
                            st.caption(
                                "📘 책 표지 없음"
                            )
                    else:
                        st.caption(
                            "📘 책 표지 없음"
                        )

                    st.markdown(
                        f"**{book['title']}**"
                    )

                    if book.get("author"):
                        st.caption(
                            f"저자: {book['author']}"
                        )

                    if book.get("publisher"):
                        st.caption(
                            f"출판사: {book['publisher']}"
                        )

                    st.session_state.setdefault(
                        "bm_reviews", {}
                    )
                    st.session_state.setdefault(
                        "bm_reports", {}
                    )
                    st.session_state.setdefault(
                        "bm_bookmarks", {}
                    )

                    completed = []

                    if key in st.session_state.bm_reviews:
                        completed.append(
                            "한줄평"
                        )
                    if key in st.session_state.bm_reports:
                        completed.append(
                            "독후감"
                        )
                    if key in st.session_state.bm_bookmarks:
                        completed.append(
                            "책갈피"
                        )

                    if completed:
                        st.caption(
                            "완료: "
                            + " · ".join(completed)
                        )

                    if st.button(
                        "📖 이 책으로 활동",
                        key=f"library_use_{key}",
                        use_container_width=True,
                        type="primary"
                    ):
                        use_for_activity(
                            key, book
                        )

                    if (
                        st.session_state.get(
                            "bm_library_pending_delete"
                        ) == key
                    ):
                        st.warning(
                            "서재에서만 제거합니다. "
                            "독서 기록은 삭제하지 않습니다."
                        )

                        a, b = st.columns(2)

                        if a.button(
                            "삭제 확인",
                            key=f"library_yes_{key}"
                        ):
                            remove_library(key)

                        if b.button(
                            "취소",
                            key=f"library_no_{key}"
                        ):
                            st.session_state.bm_library_pending_delete = None
                            st.rerun()

                    elif st.button(
                        "서재에서 빼기",
                        key=f"library_del_{key}",
                        use_container_width=True
                    ):
                        st.session_state.bm_library_pending_delete = key
                        st.rerun()

st.divider()
st.caption(
    "로그인 계정의 서재는 현재 서버의 SQLite에 저장됩니다. "
    "서버 재시작·재배포 또는 서버 교체 시 "
    "자료가 사라질 수 있습니다."
)
