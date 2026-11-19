"""책모아 메인 도서관 - 로컬 로그인 체험판.

PAGE 1 숏폼 브레이커와 PAGE 2 독서 집중실을 연결합니다.
Streamlit Community Cloud의 SQLite는 영구 저장을 보장하지 않습니다.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import sqlite3
import tempfile
import unicodedata
from io import BytesIO
from pathlib import Path

import streamlit as st
from PIL import Image, ImageDraw, ImageFont


st.set_page_config(
    page_title="책모아 도서관",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent
CHARACTER_PATH = ROOT / "reader_character.png"
DB_PATH = Path(tempfile.gettempdir()) / "bookmoa_local" / "records.db"

ZONES = ["한줄평", "독후감", "책갈피"]
EMOJIS = ["💬", "📝", "🔖"]

PALETTES = {
    "크림": ("#FFF4E4", "#91644C", "#49372C"),
    "민트": ("#E2F4EC", "#3D8577", "#29473E"),
    "라벤더": ("#F1E9FA", "#7862A6", "#4C3D62"),
}


def init_state():
    defaults = {
        "bm_pos": 0,
        "bm_zone": None,
        "bm_user_id": None,
        "bm_username": None,
        "bm_books": {},
        "bm_selected": None,
        "bm_reviews": {},
        "bm_reports": {},
        "bm_bookmarks": {},
        "bm_png": None,
        "bm_png_key": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def record_id(title, author):
    return (
        title.strip().casefold()
        + "|"
        + author.strip().casefold()
    )


def db_connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(DB_PATH), timeout=5)


def init_database():
    try:
        with db_connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    salt BLOB NOT NULL,
                    pw_hash BLOB NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS books (
                    user_id INTEGER NOT NULL,
                    book_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    PRIMARY KEY(user_id, book_key)
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    user_id INTEGER NOT NULL,
                    book_key TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    PRIMARY KEY(user_id, book_key)
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    user_id INTEGER NOT NULL,
                    book_key TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    scene TEXT NOT NULL,
                    thought TEXT NOT NULL,
                    PRIMARY KEY(user_id, book_key)
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS bookmarks (
                    user_id INTEGER NOT NULL,
                    book_key TEXT NOT NULL,
                    quote TEXT NOT NULL,
                    palette TEXT NOT NULL,
                    PRIMARY KEY(user_id, book_key)
                )
            """)
        return True
    except (OSError, sqlite3.Error):
        return False


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        200_000,
    )


def register_user(username, password):
    if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", username):
        return "아이디는 영문·숫자·밑줄로 3~20자 입력해 주세요."

    if len(password) < 8:
        return "비밀번호는 8자 이상 입력해 주세요."

    salt = os.urandom(16)

    try:
        with db_connect() as db:
            db.execute(
                "INSERT INTO users(username,salt,pw_hash) VALUES(?,?,?)",
                (username, salt, password_hash(password, salt)),
            )
        return None
    except sqlite3.IntegrityError:
        return "이미 사용 중인 아이디입니다."
    except (OSError, sqlite3.Error):
        return "계정 저장소에 연결하지 못했습니다."


def authenticate(username, password):
    try:
        with db_connect() as db:
            row = db.execute(
                "SELECT id,salt,pw_hash FROM users WHERE username=?",
                (username,),
            ).fetchone()

        if row and hmac.compare_digest(
            password_hash(password, row[1]),
            row[2],
        ):
            return row[0]
    except (OSError, sqlite3.Error):
        return None

    return None


def reset_session():
    for name in (
        "bm_books",
        "bm_reviews",
        "bm_reports",
        "bm_bookmarks",
    ):
        st.session_state[name] = {}

    st.session_state.bm_selected = None
    st.session_state.bm_png = None
    st.session_state.bm_png_key = None
    st.session_state.bm_user_id = None
    st.session_state.bm_username = None

    for key in list(st.session_state):
        if (
            str(key).startswith("quote_")
            or str(key).startswith("palette_")
        ):
            del st.session_state[key]


def load_records(user_id):
    try:
        with db_connect() as db:
            book_rows = db.execute(
                "SELECT book_key,title,author FROM books WHERE user_id=?",
                (user_id,),
            ).fetchall()

            review_rows = db.execute(
                "SELECT book_key,rating,content FROM reviews WHERE user_id=?",
                (user_id,),
            ).fetchall()

            report_rows = db.execute(
                "SELECT book_key,reason,scene,thought FROM reports WHERE user_id=?",
                (user_id,),
            ).fetchall()

            bookmark_rows = db.execute(
                "SELECT book_key,quote,palette FROM bookmarks WHERE user_id=?",
                (user_id,),
            ).fetchall()
    except (OSError, sqlite3.Error):
        return False

    st.session_state.bm_books = {
        k: {"title": t, "author": a}
        for k, t, a in book_rows
    }
    st.session_state.bm_reviews = {
        k: {"rating": r, "text": c}
        for k, r, c in review_rows
    }
    st.session_state.bm_reports = {
        k: {"reason": a, "scene": b, "thought": c}
        for k, a, b, c in report_rows
    }
    st.session_state.bm_bookmarks = {
        k: {"quote": q, "palette": p}
        for k, q, p in bookmark_rows
    }

    st.session_state.bm_selected = next(
        iter(st.session_state.bm_books),
        None,
    )
    st.session_state.bm_png = None
    st.session_state.bm_png_key = None
    return True


TABLES = {
    "bookmoa_books": (
        "books", ("title", "author")
    ),
    "bookmoa_reviews": (
        "reviews", ("rating", "content")
    ),
    "bookmoa_reports": (
        "reports", ("reason", "scene", "thought")
    ),
    "bookmoa_bookmarks": (
        "bookmarks", ("quote", "palette")
    ),
}


def save_record(table, data, key):
    uid = st.session_state.bm_user_id

    if uid is None:
        return True

    if table not in TABLES:
        return False

    sql_table, fields = TABLES[table]
    sql_columns = ",".join(
        ("user_id", "book_key", *fields)
    )
    placeholders = ",".join(
        "?" for _ in range(len(fields) + 2)
    )
    vals = (
        uid,
        key,
        *(data[field] for field in fields),
    )

    try:
        with db_connect() as db:
            db.execute(
                f"INSERT OR REPLACE INTO {sql_table} "
                f"({sql_columns}) VALUES ({placeholders})",
                vals,
            )
        return True
    except (OSError, sqlite3.Error) as exc:
        st.error(f"기록을 저장하지 못했습니다: {exc}")
        return False


def delete_record(table, key):
    uid = st.session_state.bm_user_id

    if uid is None:
        return True

    if table not in TABLES:
        return False

    sql_table = TABLES[table][0]

    try:
        with db_connect() as db:
            db.execute(
                f"DELETE FROM {sql_table} "
                "WHERE user_id=? AND book_key=?",
                (uid, key),
            )
        return True
    except (OSError, sqlite3.Error) as exc:
        st.error(f"기록을 삭제하지 못했습니다: {exc}")
        return False


@st.cache_data(show_spinner=False)
def shelf_image(index, selected):
    w, h = 440, 370

    base = Image.new(
        "RGBA",
        (w, h),
        ["#FFF1E4", "#E4F2EB", "#F1E9F8"][index],
    )
    d = ImageDraw.Draw(base)

    trim = ["#A17658", "#5F9387", "#8B74AA"][index]
    inner = ["#F7E0C4", "#CFEADF", "#E5D9F4"][index]

    d.rectangle(
        (0, 294, w, h),
        fill="#DCC6AB",
    )

    if index == 0:
        d.rounded_rectangle(
            (30, 30, 410, 294),
            radius=17,
            fill=trim,
        )
        d.rounded_rectangle(
            (49, 51, 391, 283),
            radius=7,
            fill=inner,
        )
    elif index == 1:
        d.rounded_rectangle(
            (26, 26, 414, 294),
            radius=72,
            fill=trim,
        )
        d.rounded_rectangle(
            (46, 47, 394, 283),
            radius=52,
            fill=inner,
        )
    else:
        d.polygon(
            [
                (32, 72),
                (110, 18),
                (330, 18),
                (408, 72),
            ],
            fill="#B29ACA",
        )
        d.rounded_rectangle(
            (32, 66, 408, 294),
            radius=7,
            fill=trim,
        )
        d.rectangle(
            (51, 82, 389, 282),
            fill=inner,
        )

    book_colors = [
        "#DFA58C",
        "#7EB5CB",
        "#D6BE73",
        "#B49CD1",
        "#7EB8A1",
    ]

    for row, y in enumerate((116, 189, 259)):
        for j in range(12):
            x = 56 + j * 27
            top = y - 30 - (j * 4 + row * 5) % 15

            d.rounded_rectangle(
                (x, top, x + 19, y),
                radius=2,
                fill=book_colors[
                    (row + j + index) % len(book_colors)
                ],
            )
            d.line(
                (x + 5, top + 5, x + 5, top + 13),
                fill="#FFF4E9",
                width=2,
            )

        d.rectangle(
            (49, y, 391, y + 11),
            fill=trim,
        )

    if selected:
        if CHARACTER_PATH.exists():
            with Image.open(CHARACTER_PATH) as raw:
                character = raw.convert("RGBA")
                character.thumbnail(
                    (215, 245),
                    Image.Resampling.LANCZOS,
                )

                x = (w - character.width) // 2
                y = h - character.height - 5

                base.alpha_composite(
                    character,
                    (x, y),
                )
        else:
            d.ellipse(
                (174, 208, 266, 300),
                fill="#FFD8C2",
            )
            d.ellipse(
                (197, 240, 204, 249),
                fill="#403134",
            )
            d.ellipse(
                (235, 240, 242, 249),
                fill="#403134",
            )

        d.rounded_rectangle(
            (5, 5, w - 5, h - 5),
            radius=20,
            outline="#F6C34E",
            width=7,
        )

    return base.convert("RGB")


def ko_font(size):
    candidates = [
        ROOT / "fonts" / "NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "C:/Windows/Fonts/malgun.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    ]

    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(str(path), size)

    raise RuntimeError(
        "책갈피에 사용할 한글 글꼴이 없습니다. "
        "packages.txt를 확인해 주세요."
    )


def word_lines(draw, text, font, max_width):
    result = []
    cur = ""

    for char in text:
        if char == "\n":
            result.append(cur)
            cur = ""
            continue

        if (
            draw.textbbox(
                (0, 0),
                cur + char,
                font=font,
            )[2]
            <= max_width
        ):
            cur += char
        else:
            result.append(cur)
            cur = char

    if cur:
        result.append(cur)

    return result


def make_bookmark(title, author, quote, palette):
    bg, accent, ink = PALETTES[palette]

    image = Image.new(
        "RGB",
        (560, 920),
        bg,
    )
    d = ImageDraw.Draw(image)

    d.rounded_rectangle(
        (23, 23, 537, 897),
        radius=25,
        outline=accent,
        width=5,
    )

    title_font = ko_font(35)
    sub_font = ko_font(22)
    body_font = ko_font(29)

    d.text(
        (180, 82),
        "MY BOOKMARK",
        font=sub_font,
        fill=accent,
    )
    d.line(
        (80, 141, 480, 141),
        fill=accent,
        width=3,
    )

    for i, line in enumerate(
        word_lines(d, title, title_font, 430)[:3]
    ):
        d.text(
            (65, 180 + i * 52),
            line,
            font=title_font,
            fill=ink,
        )

    for i, line in enumerate(
        word_lines(d, author, sub_font, 430)[:2]
    ):
        d.text(
            (65, 365 + i * 34),
            line,
            font=sub_font,
            fill=accent,
        )

    lines = word_lines(
        d,
        quote,
        body_font,
        430,
    )

    if len(lines) > 8:
        raise ValueError(
            "책갈피 문장을 조금 짧게 작성해 주세요."
        )

    start = 505 - len(lines) * 24

    for i, line in enumerate(lines):
        d.text(
            (65, start + i * 50),
            line,
            font=body_font,
            fill=ink,
        )

    d.line(
        (80, 788, 480, 788),
        fill=accent,
        width=3,
    )
    d.text(
        (178, 826),
        "책모아 도서관",
        font=sub_font,
        fill=accent,
    )

    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


# -------------------------------
# 화면 시작
# -------------------------------

init_state()

st.title("📚 책모아 도서관")
st.caption(
    "책장 사이를 이동하며 한줄평·독후감·"
    "책갈피를 만들어 보세요."
)

db_ready = init_database()


# -------------------------------
# 사이드바
# -------------------------------

with st.sidebar:
    st.title("📚 책모아")
    st.markdown("#### 페이지 이동")

    st.page_link(
        "main.py",
        label="🏠 MAIN · 도서관",
    )

    page_candidates = sorted(
        (ROOT / "pages").glob("*.py")
    )

    def norm(name):
        return unicodedata.normalize(
            "NFC",
            name,
        ).casefold()

    shortform = next(
        (
            p for p in page_candidates
            if (
                "숏폼" in norm(p.name)
                or "shortform" in norm(p.name)
            )
        ),
        None,
    )

    if shortform is None:
        shortform = next(
            (
                p for p in page_candidates
                if norm(p.stem).startswith("1_")
            ),
            None,
        )

    if shortform is None and len(page_candidates) == 1:
        shortform = page_candidates[0]

    if shortform is not None:
        try:
            st.page_link(
                f"pages/{shortform.name}",
                label="🎮 PAGE 1 · 숏폼 브레이커",
            )
        except Exception:
            st.caption(
                "PAGE 1 파일 이름과 페이지 등록 "
                "상태를 확인해 주세요."
            )
    else:
        st.caption(
            "PAGE 1은 pages 폴더에 파일을 "
            "넣으면 나타납니다."
        )

    # 신규 PAGE 2 메뉴
    focus_room = next(
        (
            p for p in page_candidates
            if (
                "집중실" in norm(p.name)
                or norm(p.stem).startswith("2_")
            )
        ),
        None,
    )

    if (
        focus_room is not None
        and focus_room != shortform
    ):
        try:
            st.page_link(
                f"pages/{focus_room.name}",
                label="⏱️ PAGE 2 · 독서 집중실",
            )
        except Exception:
            st.caption(
                "PAGE 2 파일 경로를 확인해 주세요."
            )

    st.divider()
    st.markdown("#### 👤 내 독서 기록")

    if not db_ready:
        st.warning(
            "로그인 저장소를 사용할 수 없습니다. "
            "현재는 체험만 가능합니다."
        )

    elif st.session_state.bm_user_id is None:
        t_login, t_signup = st.tabs(
            ["로그인", "회원가입"]
        )

        with t_login:
            with st.form("login_form"):
                username = st.text_input(
                    "아이디",
                    key="login_username",
                )
                password = st.text_input(
                    "비밀번호",
                    type="password",
                    key="login_password",
                )
                submitted = st.form_submit_button(
                    "로그인"
                )

            if submitted:
                uid = authenticate(
                    username.strip(),
                    password,
                )

                if uid is None:
                    st.error(
                        "아이디 또는 비밀번호를 확인해 주세요."
                    )
                elif load_records(uid):
                    st.session_state.bm_user_id = uid
                    st.session_state.bm_username = (
                        username.strip()
                    )
                    st.rerun()
                else:
                    st.error(
                        "계정 기록을 불러올 수 없습니다."
                    )

        with t_signup:
            with st.form("signup_form"):
                new_username = st.text_input(
                    "새 아이디",
                    key="signup_username",
                )
                new_password = st.text_input(
                    "새 비밀번호 (8자 이상)",
                    type="password",
                    key="signup_password",
                )
                confirm = st.text_input(
                    "비밀번호 확인",
                    type="password",
                    key="signup_confirm",
                )
                submitted_new = (
                    st.form_submit_button("회원가입")
                )

            if submitted_new:
                if new_password != confirm:
                    st.error(
                        "비밀번호가 일치하지 않습니다."
                    )
                else:
                    result = register_user(
                        new_username.strip(),
                        new_password,
                    )
                    if result:
                        st.error(result)
                    else:
                        st.success(
                            "가입되었습니다. "
                            "로그인 탭에서 로그인해 주세요."
                        )

    else:
        st.success(
            f"{st.session_state.bm_username}님 로그인 중"
        )
        if st.button(
            "로그아웃",
            use_container_width=True,
        ):
            reset_session()
            st.rerun()

    st.caption(
        "로컬 저장 방식입니다. "
        "Streamlit Cloud 재시작·재배포 후에는 "
        "계정과 기록이 사라질 수 있습니다."
    )


# -------------------------------
# 메인 도서관 책장
# -------------------------------

st.subheader("🏛️ 도서관 둘러보기")

cols = st.columns(3, gap="small")

for i, c in enumerate(cols):
    with c:
        st.markdown(
            f"#### {EMOJIS[i]} {ZONES[i]} 책장"
        )
        st.image(
            shelf_image(
                i,
                i == st.session_state.bm_pos,
            ),
            use_container_width=True,
        )

left, center, right = st.columns(
    [1, 2, 1]
)

with left:
    if st.button(
        "◀ 왼쪽",
        disabled=st.session_state.bm_pos == 0,
        use_container_width=True,
    ):
        st.session_state.bm_pos -= 1
        st.session_state.bm_zone = None
        st.rerun()

with center:
    i = st.session_state.bm_pos
    if st.button(
        f"🚪 {ZONES[i]} 책장 이용하기",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.bm_zone = i
        st.rerun()

with right:
    if st.button(
        "오른쪽 ▶",
        disabled=st.session_state.bm_pos == 2,
        use_container_width=True,
    ):
        st.session_state.bm_pos += 1
        st.session_state.bm_zone = None
        st.rerun()


# -------------------------------
# 책 직접 등록
# -------------------------------

st.divider()
st.subheader("📖 활동할 책 선택")

with st.form(
    "book_form",
    clear_on_submit=True,
):
    a, b = st.columns(2)
    title = a.text_input(
        "책 제목 *",
        max_chars=100,
    )
    author = b.text_input(
        "저자",
        max_chars=70,
    )
    add_book = st.form_submit_button(
        "이 책으로 활동하기"
    )

if add_book:
    if not title.strip():
        st.warning(
            "책 제목을 입력해 주세요."
        )
    else:
        k = record_id(title, author)
        data = {
            "title": title.strip(),
            "author": author.strip(),
        }

        if save_record(
            "bookmoa_books",
            data,
            k,
        ):
            st.session_state.bm_books[k] = data
            st.session_state.bm_selected = k
            st.session_state.bm_png = None
            st.rerun()


books = st.session_state.bm_books

if books:
    all_keys = list(books)

    selected = st.selectbox(
        "등록한 책",
        all_keys,
        index=(
            all_keys.index(
                st.session_state.bm_selected
            )
            if st.session_state.bm_selected in all_keys
            else 0
        ),
        format_func=lambda key: books[key]["title"],
    )

    if selected != st.session_state.bm_selected:
        st.session_state.bm_selected = selected
        st.session_state.bm_png = None
        st.rerun()
else:
    st.info(
        "책 제목을 먼저 등록해 주세요."
    )

selected_key = st.session_state.bm_selected
book = books.get(selected_key)
zone = st.session_state.bm_zone


# -------------------------------
# 한줄평
# -------------------------------

if zone is None:
    st.info(
        "캐릭터를 이동한 뒤 원하는 책장의 "
        "'이용하기'를 눌러 주세요."
    )

elif book is None:
    st.info(
        "활동할 책을 먼저 등록해 주세요."
    )

elif zone == 0:
    st.subheader(
        f"💬 한줄평 · {book['title']}"
    )

    saved = st.session_state.bm_reviews.get(
        selected_key,
        {},
    )

    with st.form(
        f"review_{selected_key}"
    ):
        rating = st.slider(
            "별점",
            1,
            5,
            saved.get("rating", 3),
        )
        content = st.text_area(
            "한줄평 (10~100자)",
            value=saved.get("text", ""),
            max_chars=100,
        )
        save = st.form_submit_button(
            "한줄평 저장"
        )

    if save:
        if len(content.strip()) < 10:
            st.warning(
                "10자 이상 작성해 주세요."
            )
        elif save_record(
            "bookmoa_reviews",
            {
                "rating": rating,
                "content": content.strip(),
            },
            selected_key,
        ):
            st.session_state.bm_reviews[
                selected_key
            ] = {
                "rating": rating,
                "text": content.strip(),
            }
            st.rerun()

    if saved:
        st.success(
            "⭐" * saved["rating"]
            + "  "
            + saved["text"]
        )

        if st.button("한줄평 삭제"):
            if delete_record(
                "bookmoa_reviews",
                selected_key,
            ):
                st.session_state.bm_reviews.pop(
                    selected_key,
                    None,
                )
                st.rerun()


# -------------------------------
# 독후감
# -------------------------------

elif zone == 1:
    st.subheader(
        f"📝 독후감 · {book['title']}"
    )

    saved = st.session_state.bm_reports.get(
        selected_key,
        {},
    )

    with st.form(
        f"report_{selected_key}"
    ):
        reason = st.text_area(
            "1. 책을 읽게 된 이유",
            value=saved.get("reason", ""),
        )
        scene = st.text_area(
            "2. 가장 인상 깊었던 내용",
            value=saved.get("scene", ""),
        )
        thought = st.text_area(
            "3. 읽고 난 뒤의 생각",
            value=saved.get("thought", ""),
        )
        save = st.form_submit_button(
            "독후감 저장"
        )

    if save:
        if not all(
            part.strip()
            for part in (
                reason,
                scene,
                thought,
            )
        ):
            st.warning(
                "세 항목을 모두 작성해 주세요."
            )
        elif save_record(
            "bookmoa_reports",
            {
                "reason": reason.strip(),
                "scene": scene.strip(),
                "thought": thought.strip(),
            },
            selected_key,
        ):
            st.session_state.bm_reports[
                selected_key
            ] = {
                "reason": reason.strip(),
                "scene": scene.strip(),
                "thought": thought.strip(),
            }
            st.rerun()

    if saved:
        full = (
            f"[{book['title']}] 독후감\n\n"
            f"1. 읽게 된 이유\n{saved['reason']}\n\n"
            f"2. 인상 깊었던 내용\n{saved['scene']}\n\n"
            f"3. 읽고 난 뒤의 생각\n{saved['thought']}"
        )

        st.text_area(
            "독후감 미리보기",
            value=full,
            height=250,
            disabled=True,
        )

        st.download_button(
            "📥 독후감 TXT 다운로드",
            full.encode("utf-8-sig"),
            file_name="bookmoa_report.txt",
            mime="text/plain",
        )

        if st.button("독후감 삭제"):
            if delete_record(
                "bookmoa_reports",
                selected_key,
            ):
                st.session_state.bm_reports.pop(
                    selected_key,
                    None,
                )
                st.rerun()


# -------------------------------
# 책갈피
# -------------------------------

elif zone == 2:
    st.subheader(
        f"🔖 책갈피 만들기 · {book['title']}"
    )

    saved_bookmark = (
        st.session_state.bm_bookmarks.get(
            selected_key,
            {},
        )
    )

    default_text = (
        saved_bookmark.get("quote")
        or st.session_state.bm_reviews.get(
            selected_key,
            {},
        ).get("text", "")
    )

    quote = st.text_area(
        "책갈피 문장",
        value=default_text,
        max_chars=100,
        key=f"quote_{selected_key}",
    )

    themes = list(PALETTES)
    saved_palette = saved_bookmark.get(
        "palette",
        "크림",
    )

    theme = st.selectbox(
        "책갈피 디자인",
        themes,
        index=(
            themes.index(saved_palette)
            if saved_palette in themes
            else 0
        ),
        key=f"palette_{selected_key}",
    )

    if st.button(
        "책갈피 이미지 만들기",
        type="primary",
    ):
        if not quote.strip():
            st.warning(
                "책갈피 문장을 입력해 주세요."
            )
        else:
            try:
                png = make_bookmark(
                    book["title"],
                    book["author"],
                    quote.strip(),
                    theme,
                )

                if save_record(
                    "bookmoa_bookmarks",
                    {
                        "quote": quote.strip(),
                        "palette": theme,
                    },
                    selected_key,
                ):
                    st.session_state.bm_bookmarks[
                        selected_key
                    ] = {
                        "quote": quote.strip(),
                        "palette": theme,
                    }
                    st.session_state.bm_png = png
                    st.session_state.bm_png_key = (
                        selected_key
                    )
                    st.rerun()

            except (
                ValueError,
                RuntimeError,
            ) as exc:
                st.error(str(exc))

    if (
        st.session_state.bm_png
        and st.session_state.bm_png_key == selected_key
    ):
        st.image(
            st.session_state.bm_png,
            width=260,
        )

        st.download_button(
            "📥 책갈피 PNG 다운로드",
            st.session_state.bm_png,
            file_name="bookmoa_bookmark.png",
            mime="image/png",
        )


# -------------------------------
# 내 독서 기록
# -------------------------------

st.divider()

with st.expander("📒 내 독서 기록 보기"):
    if not books:
        st.write(
            "등록된 책이 없습니다."
        )

    for k, data in books.items():
        st.markdown(
            f"**📖 {data['title']}**"
        )

        review = (
            st.session_state.bm_reviews.get(k)
        )

        if review:
            st.write(
                "⭐" * review["rating"],
                review["text"],
            )

        if k in st.session_state.bm_reports:
            st.write(
                "📝 독후감 작성 완료"
            )

        if k in st.session_state.bm_bookmarks:
            st.write(
                "🔖 책갈피 문장 및 디자인 저장 완료"
            )

    if st.session_state.bm_user_id is None:
        st.caption(
            "비로그인 기록은 현재 접속에서만 유지됩니다."
        )
    else:
        st.caption(
            "이 기록은 현재 서버의 SQLite에 저장됩니다. "
            "앱 재배포 또는 서버 교체 시 사라질 수 있습니다."
        )
