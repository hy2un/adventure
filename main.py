"""북플래닛 | 도서 활동 및 Neon PostgreSQL 로그인."""

from __future__ import annotations

import hashlib
import html
import json
import hmac
import os
import re
import math
import unicodedata
import socket
import ssl
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, HTTPRedirectHandler, build_opener

import psycopg
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

from bookplanet_db import (
    connect as db_connect,
    check_database,
    reset_legacy_session,
)

st.set_page_config(
    page_title="북플래닛 | 도서 활동",
    page_icon="🪐",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent
CHARACTER_PATH = ROOT / "reader_character.png"

ZONES = ["한줄평", "독후감", "책갈피"]
EMOJIS = ["💬", "📝", "🔖"]

PALETTES = {
    "크림": ("#FFF4E4", "#91644C", "#49372C"),
    "민트": ("#E2F4EC", "#3D8577", "#29473E"),
    "라벤더": ("#F1E9FA", "#7862A6", "#4C3D62"),
    "밤하늘": ("#1C2B49", "#D9BB83", "#F6EDD6"),
    "벚꽃": ("#FFF0F4", "#C47791", "#724359"),
    "바다": ("#E7F4FA", "#3685A3", "#264D67"),
}


# 세션 초기화
def init_state():
    defaults = {
        "bm_pos": 0,
        "bm_zone": None,
        "bm_user_id": None,
        "bm_username": None,
        "bm_books": {},
        "bm_selected": None,
        "bm_library_books": {},
        "bm_reviews": {},
        "bm_reports": {},
        "bm_bookmarks": {},
        "bm_png": None,
        "bm_png_key": None,
        "bm_search_results": None,
        "bm_last_query": "",
        "bm_popular_results": None,
        "bm_popular_dates": None,
        "bm_catalog_error": None,
        "bm_search_mode": "제목",
        "rg_events": [],
        "rg_progress": {},
        "rg_goals": {},
    }

    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def record_id(title, author):
    return (
        title.strip().casefold()
        + "|"
        + author.strip().casefold()
    )


def reset_session():
    st.session_state.clear()
    st.session_state["bm_neon_session_v1"] = True


# 비밀번호 해시
def password_hash(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        200_000,
    )


# 회원가입
def register_user(username, password):
    if not re.fullmatch(
        r"[A-Za-z0-9_]{3,20}", username
    ):
        return (
            "아이디는 영문·숫자·밑줄로 "
            "3~20자 입력해 주세요."
        )

    if len(password) < 8:
        return "비밀번호는 8자 이상 입력해 주세요."

    if len(password) > 128:
        return "비밀번호는 128자 이하로 입력해 주세요."

    salt = os.urandom(16)

    try:
        with db_connect() as db:
            db.execute(
                "INSERT INTO users "
                "(username,salt,pw_hash) "
                "VALUES(?,?,?)",
                (
                    username,
                    salt,
                    password_hash(password, salt),
                ),
            )

        return None

    except psycopg.errors.UniqueViolation:
        return "이미 사용 중인 아이디입니다."

    except (OSError, psycopg.Error):
        return "계정 저장소에 연결하지 못했습니다."


# 로그인 인증
def authenticate(username, password):
    try:
        with db_connect() as db:
            row = db.execute(
                "SELECT id,salt,pw_hash "
                "FROM users WHERE username=?",
                (username,),
            ).fetchone()

        if row and hmac.compare_digest(
            password_hash(password, bytes(row[1])),
            bytes(row[2]),
        ):
            return row[0]

    except (OSError, psycopg.Error):
        return None

    return None


# 사용자별 독서 기록 불러오기
def load_records(user_id):
    try:
        with db_connect() as db:
            book_rows = db.execute(
                "SELECT book_key,title,author "
                "FROM books WHERE user_id=?",
                (user_id,),
            ).fetchall()

            review_rows = db.execute(
                "SELECT book_key,rating,content "
                "FROM reviews WHERE user_id=?",
                (user_id,),
            ).fetchall()

            report_rows = db.execute(
                "SELECT book_key,reason,scene,thought "
                "FROM reports WHERE user_id=?",
                (user_id,),
            ).fetchall()

            bookmark_rows = db.execute(
                "SELECT book_key,quote,palette,design_json "
                "FROM bookmarks WHERE user_id=?",
                (user_id,),
            ).fetchall()

            library_rows = db.execute(
                "SELECT book_key,title,author,publisher,image_url "
                "FROM library_books WHERE user_id=?",
                (user_id,),
            ).fetchall()

    except (OSError, psycopg.Error):
        return False

    st.session_state.bm_books = {
        key: {"title": title, "author": author}
        for key, title, author in book_rows
    }

    st.session_state.bm_reviews = {
        key: {"rating": rating, "text": content}
        for key, rating, content in review_rows
    }

    st.session_state.bm_reports = {
        key: {
            "reason": reason,
            "scene": scene,
            "thought": thought,
        }
        for key, reason, scene, thought in report_rows
    }

    st.session_state.bm_bookmarks = {}

    for key, quote, palette, design_json in bookmark_rows:
        try:
            options = json.loads(design_json or "{}")
            if not isinstance(options, dict):
                options = {}
        except (ValueError, TypeError):
            options = {}

        st.session_state.bm_bookmarks[key] = {
            "quote": quote,
            "palette": palette,
            "layout": options.get("layout", "클래식 세로"),
            "motif": options.get("motif", "별"),
            "signature": options.get("signature", ""),
        }

    st.session_state.bm_library_books = {
        key: {
            "title": title,
            "author": author,
            "publisher": publisher,
            "image_url": image_url,
        }
        for key, title, author, publisher, image_url in library_rows
    }

    st.session_state.bm_selected = next(
        iter(st.session_state.bm_books), None
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


# 독서 활동 날짜 기록
def make_event(key, kind):
    now = datetime.now(ZoneInfo("Asia/Seoul"))

    return {
        "book_key": key,
        "kind": kind,
        "event_date": now.date().isoformat(),
        "created_at": now.isoformat(timespec="seconds"),
    }


def insert_event(db, uid, event):
    db.execute(
        "INSERT INTO reading_events "
        "(user_id,book_key,kind,event_date,created_at) "
        "VALUES(?,?,?,?,?)",
        (
            uid,
            event["book_key"],
            event["kind"],
            event["event_date"],
            event["created_at"],
        ),
    )


# 독서 활동 저장
def save_record(table, data, key):
    if table not in TABLES:
        return False

    uid = st.session_state.bm_user_id

    event_type = {
        "bookmoa_reviews": "한줄평",
        "bookmoa_reports": "독후감",
    }.get(table)

    event = make_event(key, event_type)

    # 저장된 독후감은 수정하거나 덮어쓸 수 없음
    if table == "bookmoa_reports":
        if key in st.session_state.bm_reports:
            st.warning("이미 저장된 독후감은 열람만 가능합니다.")
            return False

    # 비로그인 체험 기록
    if uid is None:
        if event_type:
            st.session_state.rg_events.append(event)
        return True

    sql_table, fields = TABLES[table]

    columns = ",".join(
        ("user_id", "book_key", *fields)
    )

    placeholders = ",".join(
        "?" for _ in range(len(fields) + 2)
    )

    values = (
        uid,
        key,
        *(data[field] for field in fields),
    )

    try:
        with db_connect() as db:

            # 독후감 최초 저장만 허용
            if table == "bookmoa_reports":
                cursor = db.execute(
                    f"INSERT INTO {sql_table} "
                    f"({columns}) VALUES ({placeholders}) "
                    "ON CONFLICT (user_id,book_key) "
                    "DO NOTHING",
                    values,
                )

                if cursor.rowcount == 0:
                    row = db.execute(
                        "SELECT reason,scene,thought "
                        "FROM reports "
                        "WHERE user_id=? AND book_key=?",
                        (uid, key),
                    ).fetchone()

                    if row:
                        st.session_state.bm_reports[key] = {
                            "reason": row[0],
                            "scene": row[1],
                            "thought": row[2],
                        }

                    st.warning(
                        "이미 저장된 독후감은 "
                        "열람만 가능합니다."
                    )
                    return False

            else:
                db.execute(
                    f"INSERT OR REPLACE INTO {sql_table} "
                    f"({columns}) VALUES ({placeholders})",
                    values,
                )

            if event_type:
                insert_event(db, uid, event)

        return True

    except (OSError, psycopg.Error):
        st.error("기록을 저장하지 못했습니다.")
        return False


# 한줄평 삭제만 허용
def delete_record(table, key):
    if table != "bookmoa_reviews":
        return False

    uid = st.session_state.bm_user_id

    if uid is None:
        return True

    try:
        with db_connect() as db:
            db.execute(
                "DELETE FROM reviews "
                "WHERE user_id=? AND book_key=?",
                (uid, key),
            )

        return True

    except (OSError, psycopg.Error):
        st.error("한줄평을 삭제하지 못했습니다.")
        return False


# 활동 도서 선택
def choose_activity_book(book):
    title = str(book.get("title", "")).strip()
    author = str(book.get("author", "")).strip()

    if not title:
        st.warning("책 제목을 확인해 주세요.")
        return

    key = record_id(title, author)

    data = {
        "title": title,
        "author": author,
    }

    if save_record("bookmoa_books", data, key):
        st.session_state.bm_books[key] = data
        st.session_state.bm_selected = key
        st.session_state.bm_png = None
        st.session_state.bm_png_key = None
        st.rerun()


# 책갈피 저장
def save_bookmark_design(
    key, quote, palette, layout, motif, signature
):
    uid = st.session_state.bm_user_id

    options = json.dumps(
        {
            "layout": layout,
            "motif": motif,
            "signature": signature,
        },
        ensure_ascii=False,
    )

    event = make_event(key, "책갈피")

    if uid is not None:
        try:
            with db_connect() as db:
                db.execute(
                    "INSERT OR REPLACE INTO bookmarks "
                    "(user_id,book_key,quote,palette,design_json) "
                    "VALUES(?,?,?,?,?)",
                    (uid, key, quote, palette, options),
                )

                insert_event(db, uid, event)

        except (OSError, psycopg.Error):
            st.error("책갈피를 저장하지 못했습니다.")
            return False

    else:
        st.session_state.rg_events.append(event)

    st.session_state.bm_bookmarks[key] = {
        "quote": quote,
        "palette": palette,
        "layout": layout,
        "motif": motif,
        "signature": signature,
    }

    return True


# 캐릭터 및 책장 이미지
@st.cache_data(show_spinner=False)
def shelf_image(index, character_here, zone_selected):
    w, h = 440, 370

    base = Image.new(
        "RGBA", (w, h),
        ["#FFF1E4", "#E4F2EB", "#F1E9F8"][index],
    )

    d = ImageDraw.Draw(base)

    trim = ["#A17658", "#5F9387", "#8B74AA"][index]
    inner = ["#F7E0C4", "#CFEADF", "#E5D9F4"][index]

    d.rectangle((0, 294, w, h), fill="#DCC6AB")

    if index == 0:
        d.rounded_rectangle(
            (30, 30, 410, 294), radius=17, fill=trim
        )
        d.rounded_rectangle(
            (49, 51, 391, 283), radius=7, fill=inner
        )

    elif index == 1:
        d.rounded_rectangle(
            (26, 26, 414, 294), radius=72, fill=trim
        )
        d.rounded_rectangle(
            (46, 47, 394, 283), radius=52, fill=inner
        )

    else:
        d.polygon(
            [(32, 72), (110, 18), (330, 18), (408, 72)],
            fill="#B29ACA",
        )
        d.rounded_rectangle(
            (32, 66, 408, 294), radius=7, fill=trim
        )
        d.rectangle((51, 82, 389, 282), fill=inner)

    book_colors = [
        "#DFA58C", "#7EB5CB", "#D6BE73",
        "#B49CD1", "#7EB8A1",
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

        d.rectangle((49, y, 391, y + 11), fill=trim)

    if character_here:
        if CHARACTER_PATH.exists():
            with Image.open(CHARACTER_PATH) as raw:
                character = raw.convert("RGBA")
                character.thumbnail(
                    (215, 245),
                    Image.Resampling.LANCZOS,
                )

                x = (w - character.width) // 2
                y = h - character.height - 5

                base.alpha_composite(character, (x, y))
        else:
            d.ellipse(
                (174, 208, 266, 300), fill="#FFD8C2"
            )
            d.ellipse(
                (197, 240, 204, 249), fill="#403134"
            )
            d.ellipse(
                (235, 240, 242, 249), fill="#403134"
            )

    if zone_selected:
        d.rounded_rectangle(
            (5, 5, w - 5, h - 5),
            radius=20, outline="#16845D", width=11,
        )

        d.ellipse((354, 8, 423, 77), fill="#16845D")
        d.line(
            (371, 41, 386, 56, 410, 27),
            fill="#FFFFFF",
            width=8,
            joint="curve",
        )

    elif character_here:
        d.rounded_rectangle(
            (5, 5, w - 5, h - 5),
            radius=20, outline="#F6C34E", width=7,
        )

    return base.convert("RGB")


# 한글 글꼴
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
        "책갈피에 사용할 한글 글꼴이 없습니다."
    )


def word_lines(draw, text, font, max_width):
    result = []
    current = ""

    for char in text:
        if char == "\n":
            result.append(current)
            current = ""
            continue

        if draw.textbbox(
            (0, 0), current + char, font=font
        )[2] <= max_width:
            current += char

        else:
            result.append(current)
            current = char

    if current:
        result.append(current)

    return result


# 책갈피 장식
def draw_motif(draw, motif, cx, cy, color, scale=1.0):
    r = int(27 * scale)

    if motif == "별":
        points = []

        for i in range(10):
            rad = (i * 36 - 90) * math.pi / 180
            size = r if i % 2 == 0 else r * 0.45

            points.append((
                cx + size * math.cos(rad),
                cy + size * math.sin(rad),
            ))

        draw.polygon(points, fill=color)

    elif motif == "달":
        draw.ellipse(
            (cx-r, cy-r, cx+r, cy+r), fill=color
        )
        draw.arc(
            (cx-r*0.15, cy-r, cx+r*1.3, cy+r),
            75, 285, fill=color, width=4,
        )

    elif motif == "꽃":
        for dx, dy in (
            (-r//2, 0), (r//2, 0),
            (0, -r//2), (0, r//2),
        ):
            draw.ellipse(
                (
                    cx+dx-r//2, cy+dy-r//2,
                    cx+dx+r//2, cy+dy+r//2,
                ),
                fill=color,
            )

        draw.ellipse(
            (cx-r//3, cy-r//3, cx+r//3, cy+r//3),
            fill="#FFF7EB",
        )

    else:
        draw.rounded_rectangle(
            (cx-r, cy-r//2, cx, cy+r//2),
            radius=5, outline=color, width=4,
        )

        draw.rounded_rectangle(
            (cx, cy-r//2, cx+r, cy+r//2),
            radius=5, outline=color, width=4,
        )

        draw.line(
            (cx, cy-r//2, cx, cy+r//2),
            fill=color,
            width=3,
        )


# 책갈피 이미지 생성
def make_bookmark(
    title, author, quote, palette,
    layout="클래식 세로",
    motif="별",
    signature="",
):
    if layout == "가로 문장 카드":
        w, h = 1000, 600
    elif layout == "미니 책갈피":
        w, h = 520, 850
    else:
        w, h = 640, 1060

    bg, accent, ink = PALETTES[palette]

    image = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(image)

    pad = int(w * 0.06)

    d.rounded_rectangle(
        (pad, pad, w-pad, h-pad),
        radius=24, outline=accent, width=5,
    )

    d.rounded_rectangle(
        (pad+12, pad+12, w-pad-12, h-pad-12),
        radius=20, outline=accent, width=1,
    )

    cx = w // 2

    draw_motif(
        d, motif, cx, int(h * 0.16), accent, 1.2
    )

    label_font = ko_font(21 if w < 700 else 24)
    title_font = ko_font(29 if w < 700 else 34)

    d.text(
        (cx, int(h*0.25)),
        "책 속의 한 문장",
        font=label_font,
        fill=accent,
        anchor="mm",
    )

    titles = word_lines(
        d, title, title_font, w-2*pad-60
    )[:2]

    for i, line in enumerate(titles):
        d.text(
            (cx, int(h*0.32) + i*35),
            line, font=title_font,
            fill=ink, anchor="mm",
        )

    if author:
        author_y = int(
            h * (0.43 if layout == "가로 문장 카드" else 0.41)
        )

        d.text(
            (cx, author_y), author[:36],
            font=label_font, fill=accent, anchor="mm",
        )

    area_top = int(
        h * (0.44 if layout == "가로 문장 카드" else 0.48)
    )

    area_bottom = int(
        h * (0.73 if layout == "가로 문장 카드" else 0.79)
    )

    for fontsize in (42, 38, 34, 30, 27, 24, 21, 18):
        f = ko_font(fontsize)

        lines = word_lines(
            d, quote.strip(), f, w-2*pad-80
        )

        line_h = int(fontsize * 1.5)

        if len(lines) * line_h <= area_bottom - area_top:
            break

    else:
        raise ValueError("문장이 너무 길어요. 조금 줄여주세요.")

    if not lines:
        raise ValueError("책갈피에 넣을 문장을 입력해 주세요.")

    first_y = (
        area_top + area_bottom - len(lines)*line_h
    ) // 2 + line_h//2

    for i, line in enumerate(lines):
        d.text(
            (cx, first_y + i*line_h),
            line, font=f, fill=ink, anchor="mm",
        )

    divider_y = int(
        h * (0.78 if layout == "가로 문장 카드" else 0.85)
    )

    d.line(
        (int(w*0.24), divider_y, int(w*0.76), divider_y),
        fill=accent,
        width=3,
    )

    footer = signature.strip()[:30] or "북플래닛"

    d.text(
        (
            cx,
            int(h * (
                0.835 if layout == "가로 문장 카드" else 0.91
            )),
        ),
        footer,
        font=label_font,
        fill=accent,
        anchor="mm",
    )

    output = BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


# 도서관 정보나루 API
API_BASES = (
    ("기본 주소", "https://data4library.kr/api"),
    ("www 주소", "https://www.data4library.kr/api"),
)


class BookApiError(Exception):
    pass


def api_key_from_secrets():
    try:
        return str(
            st.secrets.get("DATA4LIBRARY_API_KEY", "")
        ).strip()
    except (FileNotFoundError, KeyError, OSError):
        return ""


def clean_api_text(value, limit=160):
    if value is None:
        return ""

    raw = html.unescape(str(value))
    plain = re.sub(r"<[^>]*>", "", raw)

    return re.sub(r"\s+", " ", plain).strip()[:limit]


def api_book_from_doc(raw):
    if not isinstance(raw, dict):
        return None

    doc = raw.get("doc", raw)

    if not isinstance(doc, dict):
        return None

    title = clean_api_text(
        doc.get("bookname") or doc.get("title"), 110
    )

    if not title:
        return None

    image_url = str(
        doc.get("bookImageURL") or ""
    ).strip()

    if not image_url.startswith(("https://", "http://")):
        image_url = ""

    return {
        "title": title,
        "author": clean_api_text(
            doc.get("authors") or doc.get("author"), 100
        ),
        "publisher": clean_api_text(
            doc.get("publisher"), 70
        ),
        "isbn": clean_api_text(
            doc.get("isbn13") or doc.get("isbn"), 25
        ),
        "image_url": image_url,
        "ranking": clean_api_text(doc.get("ranking"), 10),
        "loan_count": clean_api_text(doc.get("loan_count"), 20),
    }


def network_reason(exc):
    reason = exc.reason if isinstance(exc, URLError) else exc

    if isinstance(reason, (ssl.SSLError, ssl.CertificateError)):
        return "SSL/TLS 인증서 오류"

    if isinstance(reason, socket.gaierror):
        return "DNS 주소 확인 실패"

    if isinstance(reason, (TimeoutError, socket.timeout)):
        return "응답 시간 초과"

    return "네트워크 연결 오류"


class HTTPSOnlyRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req, fp, code, msg, headers, newurl
    ):
        if not newurl.lower().startswith("https://"):
            raise URLError("insecure redirect blocked")

        return super().redirect_request(
            req, fp, code, msg, headers, newurl
        )


API_OPENER = build_opener(HTTPSOnlyRedirect)


@st.cache_data(ttl=3600, show_spinner=False)
def request_book_api(endpoint, parameters, api_key):
    query = dict(parameters)

    query.update({
        "authKey": api_key,
        "format": "json",
    })

    issues = []

    for host_label, base in API_BASES:
        url = base + "/" + endpoint + "?" + urlencode(query)

        request = Request(
            url,
            headers={
                "Accept": "application/json, */*;q=0.7",
                "User-Agent": "Mozilla/5.0 (BookPlanet/1.0)",
            },
        )

        try:
            with API_OPENER.open(request, timeout=8) as response:
                payload = response.read(1_500_001)

        except HTTPError as exc:
            issues.append(f"{host_label}: HTTP {exc.code}")
            continue

        except (URLError, TimeoutError, OSError) as exc:
            issues.append(
                f"{host_label}: {network_reason(exc)}"
            )
            continue

        if len(payload) > 1_500_000:
            issues.append(f"{host_label}: 응답 크기 초과")
            continue

        try:
            parsed = json.loads(payload.decode("utf-8-sig"))
        except (ValueError, UnicodeDecodeError):
            issues.append(f"{host_label}: JSON 응답 오류")
            continue

        body = (
            parsed.get("response")
            if isinstance(parsed, dict) else None
        )

        if not isinstance(body, dict):
            issues.append(f"{host_label}: 응답 구조 오류")
            continue

        if (
            body.get("error")
            or body.get("errorMsg")
            or body.get("errorMessage")
        ):
            issues.append(
                f"{host_label}: API 인증 또는 요청 조건 오류"
            )
            continue

        docs = body.get("docs", [])

        if isinstance(docs, dict):
            docs = [docs]

        if not isinstance(docs, list):
            docs = []

        books = []

        for entry in docs:
            book = api_book_from_doc(entry)
            if book:
                books.append(book)

        return books

    raise BookApiError(
        "도서관 정보나루 API 요청이 실패했습니다. "
        + " / ".join(issues)
        + " · Secrets 인증키를 확인해 주세요."
    )


def normalized_title(text):
    value = unicodedata.normalize(
        "NFKC", str(text)
    ).casefold()

    return "".join(
        char for char in value if char.isalnum()
    )


def find_books(keyword, api_key, mode="제목"):
    if mode == "주제·키워드":
        return request_book_api(
            "srchBooks",
            {
                "keyword": keyword,
                "pageNo": 1,
                "pageSize": 9,
            },
            api_key,
        )

    term = normalized_title(keyword)

    if not term:
        return []

    matches = []
    seen = set()

    for page in (1, 2, 3):
        chunk = request_book_api(
            "srchBooks",
            {
                "keyword": keyword,
                "pageNo": page,
                "pageSize": 30,
            },
            api_key,
        )

        for book in chunk:
            title = normalized_title(book["title"])

            marker = (
                title,
                normalized_title(book.get("author", "")),
                book.get("isbn", ""),
            )

            if term in title and marker not in seen:
                seen.add(marker)
                matches.append(book)

        if len(matches) >= 9 or len(chunk) < 30:
            break

    def priority(book):
        title = normalized_title(book["title"])

        return (
            0 if title == term
            else 1 if title.startswith(term)
            else 2,
            title,
        )

    return sorted(matches, key=priority)[:9]


def find_popular_books(api_key):
    end = date.today() - timedelta(days=7)
    start = end - timedelta(days=89)

    books = request_book_api(
        "loanItemSrch",
        {
            "startDt": start.isoformat(),
            "endDt": end.isoformat(),
            "pageNo": 1,
            "pageSize": 5,
        },
        api_key,
    )

    return books, (start.isoformat(), end.isoformat())


def display_catalog_books(books, prefix, columns=3):
    if not books:
        st.info("검색 결과가 없습니다. 다른 키워드를 입력하세요.")
        return

    for i in range(0, len(books), columns):
        group = st.columns(columns, gap="small")

        for j, book in enumerate(books[i:i+columns]):
            index = i + j

            key = record_id(
                book["title"], book.get("author", "")
            )

            selected = st.session_state.bm_selected == key

            with group[j]:
                with st.container(border=True):
                    image_url = book.get("image_url", "")

                    if image_url:
                        try:
                            st.image(image_url, width=100)
                        except Exception:
                            st.caption("📖 표지 없음")
                    else:
                        st.caption("📖 표지 없음")

                    st.markdown("**" + book["title"] + "**")

                    details = " · ".join(
                        value for value in (
                            book.get("author", ""),
                            book.get("publisher", ""),
                        ) if value
                    )

                    if details:
                        st.caption(details)

                    if prefix == "popular":
                        rank = book.get("ranking") or index + 1
                        st.caption(f"대출 순위 {rank}위")

                    if st.button(
                        "✅ 활동 도서 선택됨"
                        if selected else "📖 이 책으로 활동",
                        key=f"choose_{prefix}_{index}",
                        disabled=selected,
                        use_container_width=True,
                        type="secondary" if selected else "primary",
                    ):
                        choose_activity_book(book)


def show_book_catalog():
    st.markdown("#### 🔎 책 검색과 인기 도서 추천")

    st.caption(
        "도서관 정보나루의 실제 도서·대출 정보를 활용합니다."
    )

    api_key = api_key_from_secrets()

    if not api_key:
        st.info(
            "Streamlit Secrets에 DATA4LIBRARY_API_KEY를 "
            "등록하면 도서 검색을 이용할 수 있습니다."
        )
        return

    tab_search, tab_popular = st.tabs([
        "🔎 책 검색",
        "🏆 인기 대출도서 5권",
    ])

    with tab_search:
        with st.form("bm_book_search_form"):
            mode = st.radio(
                "검색 방식",
                ("제목", "주제·키워드"),
                horizontal=True,
                index=(
                    0 if st.session_state.bm_search_mode == "제목"
                    else 1
                ),
            )

            keyword = st.text_input(
                "책 제목 또는 키워드",
                placeholder="예: 변신, 어린 왕자",
                max_chars=70,
            )

            submitted = st.form_submit_button(
                "도서 검색", type="primary"
            )

        if submitted:
            if not keyword.strip():
                st.warning("검색어를 입력해 주세요.")

            else:
                try:
                    results = find_books(
                        keyword.strip(), api_key, mode
                    )

                    st.session_state.bm_search_results = results
                    st.session_state.bm_last_query = keyword
                    st.session_state.bm_search_mode = mode
                    st.session_state.bm_catalog_error = None

                except BookApiError as exc:
                    st.session_state.bm_catalog_error = str(exc)
                    st.session_state.bm_search_results = None

        if st.session_state.bm_catalog_error:
            st.warning(st.session_state.bm_catalog_error)

        if st.session_state.bm_search_results is not None:
            st.caption(
                f"'{st.session_state.bm_last_query}' "
                f"· {st.session_state.bm_search_mode} 검색 결과"
            )

            display_catalog_books(
                st.session_state.bm_search_results, "search"
            )

    with tab_popular:
        st.caption(
            "전국 공공도서관 대출 통계를 바탕으로 선정한 도서입니다."
        )

        if st.button(
            "🏆 인기 도서 5권 불러오기",
            use_container_width=True,
        ):
            try:
                results, dates = find_popular_books(api_key)

                st.session_state.bm_popular_results = results
                st.session_state.bm_popular_dates = dates
                st.session_state.bm_popular_error = None

            except BookApiError as exc:
                st.session_state.bm_popular_results = None
                st.session_state.bm_popular_error = str(exc)

        if st.session_state.get("bm_popular_error"):
            st.warning(st.session_state.bm_popular_error)

        if st.session_state.bm_popular_results is not None:
            dates = st.session_state.bm_popular_dates

            if dates:
                st.caption(
                    f"집계 요청 기간: {dates[0]} ~ {dates[1]}"
                )

            display_catalog_books(
                st.session_state.bm_popular_results,
                "popular",
                columns=3,
            )


# 기존 SQLite 로그인 세션 제거
reset_legacy_session()
init_state()
db_ready = check_database()


# 사이드바 및 로그인
with st.sidebar:
    st.title("🪐 북플래닛")

    links = [
        ("main.py", "📖 도서 활동"),
        ("pages/0_독서_성장_기록.py", "📊 독서 성장 기록"),
        ("pages/1_독서_집중실.py", "⏱️ 독서 집중실"),
        ("pages/2_숏폼_브레이커.py", "🎮 숏폼 브레이커"),
    ]

    for path, label in links:
        if (ROOT / path).is_file():
            st.page_link(
                path, label=label, use_container_width=True
            )

    st.divider()
    st.markdown("#### 👤 내 계정")

    if st.session_state.bm_user_id is not None:
        st.success(
            f"{st.session_state.bm_username}님 로그인 중"
        )

        if st.button("로그아웃", use_container_width=True):
            reset_session()
            st.rerun()

    elif not db_ready:
        st.warning(
            "로그인 저장소에 연결하지 못했습니다. "
            "현재는 체험만 가능합니다."
        )

    else:
        login_tab, signup_tab = st.tabs([
            "로그인", "회원가입"
        ])

        with login_tab:
            with st.form("login_form", clear_on_submit=True):
                username = st.text_input(
                    "아이디", key="login_username"
                )

                password = st.text_input(
                    "비밀번호",
                    type="password",
                    key="login_password",
                )

                submitted = st.form_submit_button("로그인")

            if submitted:
                uid = authenticate(username.strip(), password)

                if uid is None:
                    st.error("아이디 또는 비밀번호를 확인해 주세요.")

                else:
                    reset_session()
                    init_state()

                    if load_records(uid):
                        st.session_state.bm_user_id = uid
                        st.session_state.bm_username = username.strip()
                        st.rerun()

                    else:
                        st.error("계정 기록을 불러올 수 없습니다.")

        with signup_tab:
            with st.form("signup_form", clear_on_submit=True):
                new_username = st.text_input("새 아이디")

                new_password = st.text_input(
                    "새 비밀번호 (8자 이상)",
                    type="password",
                )

                confirm = st.text_input(
                    "비밀번호 확인",
                    type="password",
                )

                submitted = st.form_submit_button("회원가입")

            if submitted:
                if new_password != confirm:
                    st.error("비밀번호가 일치하지 않습니다.")

                else:
                    error = register_user(
                        new_username.strip(), new_password
                    )

                    if error:
                        st.error(error)
                    else:
                        st.success(
                            "가입되었습니다. "
                            "로그인 탭에서 로그인해 주세요."
                        )

    st.caption(
        "로그인한 사용자의 독서 기록은 "
        "외부 데이터베이스에 저장됩니다."
    )


# 메인 화면
st.title("🪐 북플래닛")
st.caption("읽고, 기록하고, 즐기는 나만의 독서 행성")
st.header("📖 도서 활동")

st.caption(
    "책을 선택하고 한줄평·독후감·책갈피 활동을 시작해 보세요."
)

current_key = st.session_state.bm_selected
current_book = st.session_state.bm_books.get(current_key)

if current_book:
    current_text = (
        f"📖 지금 활동할 책: **{current_book['title']}**"
    )

    if current_book.get("author"):
        current_text += f" · {current_book['author']}"

    st.success(current_text)

else:
    st.info(
        "아직 활동할 책이 없습니다. "
        "아래에서 검색하거나 책 제목을 입력하세요."
    )


# 활동 도서 선택
st.markdown("### ① 활동할 책 고르기")

with st.expander(
    "🔎 책 검색·인기 도서·직접 입력",
    expanded=not current_book,
):
    show_book_catalog()

    st.markdown("#### ✏️ 검색되지 않는 책은 직접 입력")

    with st.form("manual_activity_book", clear_on_submit=True):
        title_col, author_col = st.columns([2, 1])

        title = title_col.text_input(
            "책 제목 *", max_chars=100
        )

        author = author_col.text_input(
            "저자 (선택)", max_chars=70
        )

        submitted = st.form_submit_button(
            "📖 이 책으로 바로 활동",
            type="primary",
        )

    if submitted:
        if not title.strip():
            st.warning("책 제목을 입력해 주세요.")
        else:
            choose_activity_book({
                "title": title,
                "author": author,
            })

    if st.session_state.bm_books:
        st.markdown("#### 🕘 이전에 활동한 책")

        keys = list(st.session_state.bm_books)

        chosen = st.selectbox(
            "기존 활동 도서",
            keys,
            format_func=lambda key: (
                st.session_state.bm_books[key]["title"]
            ),
            index=(
                keys.index(st.session_state.bm_selected)
                if st.session_state.bm_selected in keys
                else 0
            ),
        )

        if st.button(
            "선택한 책으로 활동",
            key="bm_resume_activity",
        ):
            st.session_state.bm_selected = chosen
            st.rerun()


# 활동 종류 선택
st.markdown("### ② 원하는 활동 바로 시작")

activity_cols = st.columns(3, gap="small")

for i, col in enumerate(activity_cols):
    with col:
        with st.container(border=True):
            st.markdown(f"**{EMOJIS[i]} {ZONES[i]}**")

            is_selected = st.session_state.bm_zone == i

            st.image(
                shelf_image(
                    i,
                    character_here=is_selected,
                    zone_selected=is_selected,
                ),
                width=190,
            )

            if st.button(
                f"✅ {ZONES[i]} 선택됨"
                if is_selected else f"{ZONES[i]} 시작하기",
                key=f"bm_direct_zone_{i}",
                use_container_width=True,
                disabled=is_selected,
                type="secondary" if is_selected else "primary",
            ):
                st.session_state.bm_zone = i
                st.rerun()


if not current_book:
    st.caption(
        "활동 종류는 미리 선택할 수 있습니다. "
        "책을 고르면 곧바로 작성할 수 있어요."
    )

zone = st.session_state.bm_zone


# 독서 활동 실행
if current_book and zone is not None:
    st.markdown(
        f"### ✍️ {current_book['title']} · {ZONES[zone]}"
    )

    key = current_key
    book = current_book

    # 한줄평
    if zone == 0:
        saved = st.session_state.bm_reviews.get(key, {})

        with st.form(f"review_{key}"):
            rating = st.slider(
                "별점", 1, 5, int(saved.get("rating", 3))
            )

            content = st.text_area(
                "나의 한줄평",
                value=saved.get("text", ""),
                max_chars=150,
                placeholder="책을 읽고 어떤 생각이 들었나요?",
            )

            submitted = st.form_submit_button(
                "💾 한줄평 저장",
                type="primary",
            )

        if submitted:
            if len(content.strip()) < 5:
                st.warning("한줄평을 5자 이상 적어 주세요.")

            elif save_record(
                "bookmoa_reviews",
                {"rating": rating, "content": content.strip()},
                key,
            ):
                st.session_state.bm_reviews[key] = {
                    "rating": rating,
                    "text": content.strip(),
                }
                st.rerun()

        if saved:
            st.success(
                f"{'⭐' * saved['rating']} {saved['text']}"
            )

            if st.button(
                "한줄평 삭제",
                key=f"delete_review_{key}",
            ):
                if delete_record("bookmoa_reviews", key):
                    st.session_state.bm_reviews.pop(key, None)
                    st.rerun()

    # 독후감: 최초 작성 이후 열람 전용
    elif zone == 1:
        saved = st.session_state.bm_reports.get(key)

        if saved:
            st.success("저장된 독후감입니다.")

            with st.container(border=True):
                st.markdown("#### 1. 이 책을 읽게 된 이유")
                st.write(saved["reason"])

                st.divider()

                st.markdown("#### 2. 기억에 남는 장면이나 내용")
                st.write(saved["scene"])

                st.divider()

                st.markdown("#### 3. 읽은 뒤의 생각과 배운 점")
                st.write(saved["thought"])

            st.caption(
                "저장된 독후감은 독서 성장 기록에서도 "
                "열람할 수 있습니다. 수정 및 삭제는 불가능합니다."
            )

        else:
            st.info(
                "독후감을 저장하면 이후에는 "
                "수정하거나 삭제할 수 없습니다."
            )

            with st.form(f"report_{key}"):
                reason = st.text_area(
                    "1. 이 책을 읽게 된 이유"
                )

                scene = st.text_area(
                    "2. 기억에 남는 장면이나 내용"
                )

                thought = st.text_area(
                    "3. 읽은 뒤의 생각과 배운 점"
                )

                confirmed = st.checkbox(
                    "작성한 내용을 확인했으며 독후감을 저장합니다."
                )

                submitted = st.form_submit_button(
                    "💾 독후감 저장",
                    type="primary",
                )

            if submitted:
                if not all(
                    value.strip()
                    for value in (reason, scene, thought)
                ):
                    st.warning("세 항목을 모두 작성해 주세요.")

                elif not confirmed:
                    st.warning("저장 확인 항목을 체크해 주세요.")

                else:
                    report = {
                        "reason": reason.strip(),
                        "scene": scene.strip(),
                        "thought": thought.strip(),
                    }

                    if save_record(
                        "bookmoa_reports", report, key
                    ):
                        st.session_state.bm_reports[key] = report
                        st.rerun()

    # 책갈피 제작
    else:
        saved = st.session_state.bm_bookmarks.get(key, {})

        default_quote = (
            saved.get("quote")
            or st.session_state.bm_reviews.get(
                key, {}
            ).get("text", "")
        )

        st.caption(
            "문장·디자인·장식을 골라 "
            "나만의 책갈피를 만들고 PNG로 저장하세요."
        )

        quote = st.text_area(
            "책갈피에 넣을 문장",
            value=default_quote,
            max_chars=200,
            key=f"bm_q_{key}",
            placeholder="기억하고 싶은 문장이나 직접 쓴 감상",
        )

        design_cols = st.columns(3)

        layouts = [
            "클래식 세로",
            "미니 책갈피",
            "가로 문장 카드",
        ]

        motifs = ["별", "달", "꽃", "책"]
        palettes = list(PALETTES)

        def option_index(options, value):
            return options.index(value) if value in options else 0

        with design_cols[0]:
            palette = st.selectbox(
                "배경 색상",
                palettes,
                index=option_index(
                    palettes, saved.get("palette", "크림")
                ),
                key=f"bm_pal_{key}",
            )

        with design_cols[1]:
            layout = st.selectbox(
                "책갈피 크기",
                layouts,
                index=option_index(
                    layouts, saved.get("layout", "클래식 세로")
                ),
                key=f"bm_layout_{key}",
            )

        with design_cols[2]:
            motif = st.selectbox(
                "장식",
                motifs,
                index=option_index(
                    motifs, saved.get("motif", "별")
                ),
                key=f"bm_motif_{key}",
            )

        signature = st.text_input(
            "하단에 넣을 이름 또는 문구 (선택)",
            value=saved.get("signature", ""),
            max_chars=30,
            key=f"bm_sign_{key}",
        )

        if quote.strip():
            try:
                png = make_bookmark(
                    book["title"],
                    book.get("author", ""),
                    quote,
                    palette,
                    layout,
                    motif,
                    signature,
                )

            except (ValueError, RuntimeError) as exc:
                st.warning(str(exc))
                png = None

            if png:
                with st.container(border=True):
                    st.markdown("**🖼️ 미리보기**")
                    st.image(png, width=350)

                save_col, download_col = st.columns(2)

                with save_col:
                    if st.button(
                        "💾 내 책갈피 저장",
                        type="primary",
                        use_container_width=True,
                    ):
                        if save_bookmark_design(
                            key,
                            quote.strip(),
                            palette,
                            layout,
                            motif,
                            signature,
                        ):
                            st.success(
                                "책갈피의 문장과 디자인을 저장했어요."
                            )

                with download_col:
                    st.download_button(
                        "📥 PNG 다운로드",
                        png,
                        file_name="bookplanet_bookmark.png",
                        mime="image/png",
                        use_container_width=True,
                    )

        else:
            st.info(
                "문장을 입력하면 책갈피 미리보기가 나타납니다."
            )

else:
    if zone is None:
        st.caption("위의 세 활동 가운데 원하는 것을 누르세요.")
    elif current_book is None:
        st.caption("책을 선택하면 작성 화면이 열립니다.")


st.divider()

st.caption(
    "이곳에서 한줄평·독후감·책갈피를 작성하고, "
    "'독서 성장 기록'에서 내용을 확인할 수 있습니다."
)

st.caption(
    "로그인한 사용자의 기록은 Neon 외부 데이터베이스에 "
    "저장됩니다. 비로그인 체험 기록은 임시로 유지됩니다."
)
