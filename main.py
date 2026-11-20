"""책모아 메인 도서관 - 정보나루 도서 검색·추천 연동.

기존 책장·한줄평·독후감·책갈피·로컬 로그인 기능과
PAGE 1 숏폼 브레이커 / PAGE 2 독서 집중실 메뉴를 유지합니다.
"""
from __future__ import annotations

import hashlib
import html
import json
import hmac
import os
import re
import sqlite3
import tempfile
from datetime import date, timedelta
import unicodedata
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
import socket
import ssl
from urllib.parse import urlencode
from urllib.request import Request, HTTPRedirectHandler, build_opener

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

st.set_page_config(
    page_title="책모아 도서관", page_icon="📚", layout="wide",
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
    "밤하늘": ("#1C2B49", "#D9BB83", "#F6EDD6"),
    "벚꽃": ("#FFF0F4", "#C47791", "#724359"),
    "바다": ("#E7F4FA", "#3685A3", "#264D67"),
}


def init_state():
    defaults = {
        "bm_pos": 0, "bm_zone": None, "bm_user_id": None,
        "bm_username": None, "bm_books": {}, "bm_selected": None,
        "bm_library_books": {},
        "bm_reviews": {}, "bm_reports": {}, "bm_bookmarks": {},
        "bm_png": None, "bm_png_key": None,
        "bm_search_results": None, "bm_last_query": "",
        "bm_popular_results": None, "bm_popular_dates": None,
        "bm_catalog_error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def record_id(title, author):
    return title.strip().casefold() + "|" + author.strip().casefold()


def db_connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(DB_PATH), timeout=5)


def init_database():
    """SQLite 연결이 실패해도 비로그인 체험은 계속할 수 있도록 한다."""
    try:
        with db_connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                salt BLOB NOT NULL, pw_hash BLOB NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS books (
                user_id INTEGER NOT NULL, book_key TEXT NOT NULL,
                title TEXT NOT NULL, author TEXT NOT NULL,
                PRIMARY KEY(user_id, book_key)
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS reviews (
                user_id INTEGER NOT NULL, book_key TEXT NOT NULL,
                rating INTEGER NOT NULL, content TEXT NOT NULL,
                PRIMARY KEY(user_id, book_key)
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS reports (
                user_id INTEGER NOT NULL, book_key TEXT NOT NULL,
                reason TEXT NOT NULL, scene TEXT NOT NULL, thought TEXT NOT NULL,
                PRIMARY KEY(user_id, book_key)
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS bookmarks (
                user_id INTEGER NOT NULL, book_key TEXT NOT NULL,
                quote TEXT NOT NULL, palette TEXT NOT NULL,
                PRIMARY KEY(user_id, book_key)
            )""")
            # 기존 기록을 유지하며 새 서재를 독립적으로 생성합니다.
            db.execute("""CREATE TABLE IF NOT EXISTS library_books (
                user_id INTEGER NOT NULL, book_key TEXT NOT NULL,
                title TEXT NOT NULL, author TEXT NOT NULL,
                publisher TEXT NOT NULL DEFAULT '',
                image_url TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(user_id, book_key)
            )""")
            columns = {
                row[1] for row in db.execute("PRAGMA table_info(bookmarks)")
            }
            if "design_json" not in columns:
                db.execute(
                    "ALTER TABLE bookmarks ADD COLUMN "
                    "design_json TEXT NOT NULL DEFAULT '{}'"
                )
        return True
    except (OSError, sqlite3.Error):
        return False


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)


def register_user(username, password):
    if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", username):
        return "아이디는 영문·숫자·밑줄로 3~20자 입력해 주세요."
    if len(password) < 8:
        return "비밀번호는 8자 이상 입력해 주세요."
    salt = os.urandom(16)
    try:
        with db_connect() as db:
            db.execute("INSERT INTO users(username,salt,pw_hash) VALUES(?,?,?)",
                       (username, salt, password_hash(password, salt)))
        return None
    except sqlite3.IntegrityError:
        return "이미 사용 중인 아이디입니다."
    except (OSError, sqlite3.Error):
        return "계정 저장소에 연결하지 못했습니다."


def authenticate(username, password):
    try:
        with db_connect() as db:
            row = db.execute("SELECT id,salt,pw_hash FROM users WHERE username=?",
                             (username,)).fetchone()
        if row and hmac.compare_digest(password_hash(password, row[1]), row[2]):
            return row[0]
    except (OSError, sqlite3.Error):
        return None
    return None


def reset_session():
    for name in ("bm_books", "bm_library_books", "bm_reviews", "bm_reports", "bm_bookmarks"):
        st.session_state[name] = {}
    st.session_state.bm_selected = None
    st.session_state.bm_png = None
    st.session_state.bm_png_key = None
    st.session_state.bm_user_id = None
    st.session_state.bm_username = None
    for key in list(st.session_state):
        if str(key).startswith("quote_") or str(key).startswith("palette_"):
            del st.session_state[key]


def load_records(user_id):
    """로그인한 계정의 기록만 로컬 DB에서 읽는다."""
    try:
        with db_connect() as db:
            book_rows = db.execute("SELECT book_key,title,author FROM books WHERE user_id=?", (user_id,)).fetchall()
            review_rows = db.execute("SELECT book_key,rating,content FROM reviews WHERE user_id=?", (user_id,)).fetchall()
            report_rows = db.execute("SELECT book_key,reason,scene,thought FROM reports WHERE user_id=?", (user_id,)).fetchall()
            bookmark_rows = db.execute(
                "SELECT book_key,quote,palette,design_json "
                "FROM bookmarks WHERE user_id=?", (user_id,)
            ).fetchall()
            library_rows = db.execute(
                "SELECT book_key,title,author,publisher,image_url "
                "FROM library_books WHERE user_id=?", (user_id,)
            ).fetchall()
    except (OSError, sqlite3.Error):
        return False
    st.session_state.bm_books = {k: {"title": t, "author": a} for k, t, a in book_rows}
    st.session_state.bm_reviews = {k: {"rating": r, "text": c} for k, r, c in review_rows}
    st.session_state.bm_reports = {k: {"reason": a, "scene": b, "thought": c} for k, a, b, c in report_rows}
    st.session_state.bm_bookmarks = {}
    for key, quote, palette, design_json in bookmark_rows:
        try:
            options = json.loads(design_json or "{}")
            if not isinstance(options, dict):
                options = {}
        except (ValueError, TypeError):
            options = {}
        st.session_state.bm_bookmarks[key] = {
            "quote": quote, "palette": palette,
            "layout": options.get("layout", "클래식 세로"),
            "motif": options.get("motif", "별"),
            "signature": options.get("signature", ""),
        }
    st.session_state.bm_library_books = {
        k: {"title": title, "author": author,
            "publisher": publisher, "image_url": image_url}
        for k, title, author, publisher, image_url in library_rows
    }
    st.session_state.bm_selected = next(iter(st.session_state.bm_books), None)
    st.session_state.bm_png = None
    st.session_state.bm_png_key = None
    return True


TABLES = {
    "bookmoa_books": ("books", ("title", "author")),
    "bookmoa_reviews": ("reviews", ("rating", "content")),
    "bookmoa_reports": ("reports", ("reason", "scene", "thought")),
    "bookmoa_bookmarks": ("bookmarks", ("quote", "palette")),
}


def save_record(table, data, key):
    """로그인하면 SQLite에 저장, 비로그인 시 현재 세션에만 저장."""
    uid = st.session_state.bm_user_id
    if uid is None:
        return True
    if table not in TABLES:
        return False
    sql_table, fields = TABLES[table]
    sql_columns = ",".join(("user_id", "book_key", *fields))
    placeholders = ",".join("?" for _ in range(len(fields) + 2))
    vals = (uid, key, *(data[field] for field in fields))
    try:
        with db_connect() as db:
            db.execute(f"INSERT OR REPLACE INTO {sql_table} ({sql_columns}) VALUES ({placeholders})", vals)
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
            db.execute(f"DELETE FROM {sql_table} WHERE user_id=? AND book_key=?", (uid, key))
        return True
    except (OSError, sqlite3.Error) as exc:
        st.error(f"기록을 삭제하지 못했습니다: {exc}")
        return False


def choose_activity_book(book):
    """검색 선택은 즉시 활동 도서로만 설정하며, 서재에는 추가하지 않습니다."""
    title = str(book.get("title", "")).strip()
    author = str(book.get("author", "")).strip()
    if not title:
        st.warning("책 제목을 확인해 주세요.")
        return
    key = record_id(title, author)
    data = {"title": title, "author": author}
    if save_record("bookmoa_books", data, key):
        st.session_state.bm_books[key] = data
        st.session_state.bm_selected = key
        st.session_state.bm_png = None
        st.session_state.bm_png_key = None
        st.rerun()


def save_library_book(book):
    """독립 서재로 저장하며 현재 활동 도서는 변경하지 않습니다."""
    title = str(book.get("title", "")).strip()
    author = str(book.get("author", "")).strip()
    if not title:
        return False
    key = record_id(title, author)
    value = {
        "title": title, "author": author,
        "publisher": str(book.get("publisher", "")),
        "image_url": str(book.get("image_url", "")),
    }
    uid = st.session_state.bm_user_id
    if uid is not None:
        try:
            with db_connect() as db:
                db.execute(
                    "INSERT OR REPLACE INTO library_books "
                    "(user_id,book_key,title,author,publisher,image_url) "
                    "VALUES(?,?,?,?,?,?)",
                    (uid, key, value["title"], value["author"],
                     value["publisher"], value["image_url"]),
                )
        except (sqlite3.Error, OSError):
            st.error("나의 서재에 저장하지 못했습니다.")
            return False
    st.session_state.bm_library_books[key] = value
    st.rerun()


def save_bookmark_design(key, quote, palette, layout, motif, signature):
    """기존 bookmarks 테이블에 디자인 옵션만 추가로 보관합니다."""
    uid = st.session_state.bm_user_id
    if uid is not None:
        options = json.dumps(
            {"layout": layout, "motif": motif, "signature": signature},
            ensure_ascii=False,
        )
        try:
            with db_connect() as db:
                db.execute(
                    "INSERT OR REPLACE INTO bookmarks "
                    "(user_id,book_key,quote,palette,design_json) "
                    "VALUES(?,?,?,?,?)", (uid, key, quote, palette, options)
                )
        except (sqlite3.Error, OSError):
            st.error("책갈피를 저장하지 못했습니다.")
            return False
    st.session_state.bm_bookmarks[key] = {
        "quote": quote, "palette": palette, "layout": layout,
        "motif": motif, "signature": signature,
    }
    return True


# ── 그림 ──
@st.cache_data(show_spinner=False)
def shelf_image(index, character_here, zone_selected):
    w, h = 440, 370
    base = Image.new("RGBA", (w, h), ["#FFF1E4", "#E4F2EB", "#F1E9F8"][index])
    d = ImageDraw.Draw(base)
    trim = ["#A17658", "#5F9387", "#8B74AA"][index]
    inner = ["#F7E0C4", "#CFEADF", "#E5D9F4"][index]
    d.rectangle((0, 294, w, h), fill="#DCC6AB")
    if index == 0:
        d.rounded_rectangle((30, 30, 410, 294), radius=17, fill=trim)
        d.rounded_rectangle((49, 51, 391, 283), radius=7, fill=inner)
    elif index == 1:
        d.rounded_rectangle((26, 26, 414, 294), radius=72, fill=trim)
        d.rounded_rectangle((46, 47, 394, 283), radius=52, fill=inner)
    else:
        d.polygon([(32, 72), (110, 18), (330, 18), (408, 72)], fill="#B29ACA")
        d.rounded_rectangle((32, 66, 408, 294), radius=7, fill=trim)
        d.rectangle((51, 82, 389, 282), fill=inner)

    book_colors = ["#DFA58C", "#7EB5CB", "#D6BE73", "#B49CD1", "#7EB8A1"]
    for row, y in enumerate((116, 189, 259)):
        for j in range(12):
            x = 56 + j * 27
            top = y - 30 - (j * 4 + row * 5) % 15
            d.rounded_rectangle((x, top, x + 19, y), radius=2,
                                fill=book_colors[(row + j + index) % len(book_colors)])
            d.line((x + 5, top + 5, x + 5, top + 13), fill="#FFF4E9", width=2)
        d.rectangle((49, y, 391, y + 11), fill=trim)

    if character_here:
        # 수제 도형 대신 별도로 준비한 고화질 캐릭터 PNG를 합성한다.
        if CHARACTER_PATH.exists():
            with Image.open(CHARACTER_PATH) as raw:
                character = raw.convert("RGBA")
                character.thumbnail((215, 245), Image.Resampling.LANCZOS)
                x = (w - character.width) // 2
                y = h - character.height - 5
                base.alpha_composite(character, (x, y))
        else:
            d.ellipse((174, 208, 266, 300), fill="#FFD8C2")
            d.ellipse((197, 240, 204, 249), fill="#403134")
            d.ellipse((235, 240, 242, 249), fill="#403134")
    # 캐릭터 위치와 실제 책장 선택을 서로 다른 색으로 구분한다.
    # 노란색: 캐릭터가 도착함 / 초록색: 이용할 책장을 확정함.
    if zone_selected:
        d.rounded_rectangle(
            (5, 5, w - 5, h - 5), radius=20,
            outline="#16845D", width=11,
        )
        d.ellipse((354, 8, 423, 77), fill="#16845D")
        d.line((371, 41, 386, 56, 410, 27),
               fill="#FFFFFF", width=8, joint="curve")
    elif character_here:
        d.rounded_rectangle(
            (5, 5, w - 5, h - 5), radius=20,
            outline="#F6C34E", width=7,
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
    raise RuntimeError("책갈피에 사용할 한글 글꼴이 없습니다. packages.txt를 확인해 주세요.")


def word_lines(draw, text, font, max_width):
    result, cur = [], ""
    for char in text:
        if char == "\n":
            result.append(cur)
            cur = ""
            continue
        if draw.textbbox((0, 0), cur + char, font=font)[2] <= max_width:
            cur += char
        else:
            result.append(cur)
            cur = char
    if cur:
        result.append(cur)
    return result


def draw_motif(draw, motif, cx, cy, color, scale=1.0):
    """한글 글꼴만으로 표시 가능한 심플 도형 장식."""
    r = int(27 * scale)
    if motif == "별":
        import math
        points = []
        for i in range(10):
            rad = (i * 36 - 90) * math.pi / 180
            size = r if i % 2 == 0 else r * 0.45
            points.append((cx + size * math.cos(rad),
                           cy + size * math.sin(rad)))
        draw.polygon(points, fill=color)
    elif motif == "달":
        draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=color)
        # 원호를 이용해 밝기 차이와 관계 없이 형태를 유지합니다.
        draw.arc((cx-r*0.15, cy-r, cx+r*1.3, cy+r),
                 75, 285, fill=color, width=4)
    elif motif == "꽃":
        for dx, dy in ((-r//2,0),(r//2,0),(0,-r//2),(0,r//2)):
            draw.ellipse((cx+dx-r//2,cy+dy-r//2,
                          cx+dx+r//2,cy+dy+r//2), fill=color)
        draw.ellipse((cx-r//3,cy-r//3,cx+r//3,cy+r//3),fill="#FFF7EB")
    else:  # 책
        draw.rounded_rectangle((cx-r,cy-r//2,cx,cy+r//2),
                               radius=5, outline=color, width=4)
        draw.rounded_rectangle((cx,cy-r//2,cx+r,cy+r//2),
                               radius=5, outline=color, width=4)
        draw.line((cx,cy-r//2,cx,cy+r//2), fill=color,width=3)


def make_bookmark(title, author, quote, palette,
                  layout="클래식 세로", motif="별", signature=""):
    """세 가지 레이아웃의 고해상도 책갈피를 생성합니다."""
    if layout == "가로 문장 카드":
        w, h = 1000, 600
    elif layout == "미니 책갈피":
        w, h = 520, 850
    else:
        w, h = 640, 1060
    bg, accent, ink = PALETTES[palette]
    image = Image.new("RGB", (w,h), bg)
    d = ImageDraw.Draw(image)
    pad = int(w*0.06)
    d.rounded_rectangle((pad,pad,w-pad,h-pad), radius=24,
                        outline=accent, width=5)
    d.rounded_rectangle((pad+12,pad+12,w-pad-12,h-pad-12),
                        radius=20, outline=accent, width=1)
    cx = w//2
    draw_motif(d, motif, cx, int(h*0.16), accent, 1.2)
    label_font = ko_font(21 if w < 700 else 24)
    title_font = ko_font(29 if w < 700 else 34)
    d.text((cx,int(h*0.25)), "책 속의 한 문장", font=label_font,
           fill=accent, anchor="mm")
    # 제목과 저자는 영역을 초과하지 않도록 적절히 줄바꿈합니다.
    titles = word_lines(d, title, title_font, w-2*pad-60)[:2]
    for i, line in enumerate(titles):
        d.text((cx,int(h*0.32)+i*35),line,font=title_font,
               fill=ink,anchor="mm")
    if author:
        author_y = int(h*0.41) if layout != "가로 문장 카드" else int(h*0.43)
        d.text((cx,author_y),author[:36],font=label_font,
               fill=accent,anchor="mm")
    # 문장 크기는 줄 수와 너비를 기준으로 자동 조절합니다.
    area_top = int(h*(0.44 if layout == "가로 문장 카드" else 0.48))
    area_bottom = int(h*(0.73 if layout == "가로 문장 카드" else 0.79))
    for fontsize in (42,38,34,30,27,24,21,18):
        f = ko_font(fontsize)
        lines = word_lines(d, quote.strip(), f, w-2*pad-80)
        line_h = int(fontsize*1.5)
        if len(lines)*line_h <= area_bottom-area_top:
            break
    else:
        raise ValueError("문장이 너무 길어요. 조금 줄여주세요.")
    if not lines:
        raise ValueError("책갈피에 넣을 문장을 입력해 주세요.")
    line_h = int(fontsize*1.5)
    first_y = (area_top+area_bottom-len(lines)*line_h)//2+line_h//2
    for i,line in enumerate(lines):
        d.text((cx,first_y+i*line_h),line,font=f,
               fill=ink,anchor="mm")
    divider_y = int(h*(0.78 if layout == "가로 문장 카드" else 0.85))
    d.line((int(w*0.24),divider_y,int(w*0.76),divider_y),
           fill=accent,width=3)
    footer = signature.strip()[:30] or "책모아 도서관"
    d.text((cx,int(h*(0.835 if layout == "가로 문장 카드" else 0.91))),
           footer, font=label_font,
           fill=accent,anchor="mm")
    out = BytesIO()
    image.save(out,"PNG")
    return out.getvalue()


# ──────────────────────────────────────────────
# 정보나루 API: 메인 도서 검색 / 인기 대출도서
# 키는 Streamlit Cloud > Settings > Secrets에 등록
# ──────────────────────────────────────────────

# 정보나루 공식 도메인 2개를 HTTPS로 확인합니다.
# 인증키를 안전하게 전송하기 위해 HTTP(암호화되지 않은 연결)는 사용하지 않습니다.
API_BASES = (
    ("기본 주소", "https://data4library.kr/api"),
    ("www 주소", "https://www.data4library.kr/api"),
)


class BookApiError(Exception):
    """API 서버 상태를 인증키 노출 없이 안내합니다."""


def api_key_from_secrets():
    try:
        key = st.secrets.get("DATA4LIBRARY_API_KEY", "")
    except (FileNotFoundError, KeyError, OSError):
        return ""
    return str(key).strip()


def clean_api_text(value, limit=160):
    """도서 데이터의 HTML 태그·공백 제거."""
    if value is None:
        return ""
    raw = html.unescape(str(value))
    plain = re.sub(r"<[^>]*>", "", raw)
    return re.sub(r"\s+", " ", plain).strip()[:limit]


def api_book_from_doc(raw):
    """정보나루 {doc: {...}} 형식을 책모아 데이터로 변환합니다."""
    if not isinstance(raw, dict):
        return None
    doc = raw.get("doc", raw)
    if not isinstance(doc, dict):
        return None
    title = clean_api_text(doc.get("bookname") or doc.get("title"), 110)
    if not title:
        return None
    author = clean_api_text(doc.get("authors") or doc.get("author"), 100)
    publisher = clean_api_text(doc.get("publisher"), 70)
    isbn = clean_api_text(doc.get("isbn13") or doc.get("isbn"), 25)
    image_url = str(doc.get("bookImageURL") or "").strip()
    if not image_url.startswith(("https://", "http://")):
        image_url = ""
    return {
        "title": title,
        "author": author,
        "publisher": publisher,
        "isbn": isbn,
        "image_url": image_url,
        "ranking": clean_api_text(doc.get("ranking"), 10),
        "loan_count": clean_api_text(doc.get("loan_count"), 20),
    }


def _network_reason(exc):
    """URL·인증키가 포함될 수 있는 예외 원문은 표시하지 않습니다."""
    reason = exc.reason if isinstance(exc, URLError) else exc
    if isinstance(reason, (ssl.SSLError, ssl.CertificateError)):
        return "SSL/TLS 인증서 오류"
    if isinstance(reason, socket.gaierror):
        return "DNS 주소 확인 실패"
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return "응답 시간 초과"
    safe_name = type(reason).__name__.lower()
    if "ssl" in safe_name or "certificate" in safe_name:
        return "SSL/TLS 연결 오류"
    if "timeout" in safe_name:
        return "응답 시간 초과"
    if "connectionrefused" in safe_name:
        return "서버 연결 거부"
    return "네트워크 연결 오류"


class HTTPSOnlyRedirect(HTTPRedirectHandler):
    """인증키를 담은 요청이 HTTP로 내려가는 리다이렉트 차단."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.lower().startswith("https://"):
            raise URLError("insecure redirect blocked")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


API_OPENER = build_opener(HTTPSOnlyRedirect)


def _http_reason(code):
    if code in (401, 403):
        return f"HTTP {code} (접근 또는 인증 제한)"
    if code == 404:
        return "HTTP 404 (API 경로를 찾지 못함)"
    if code == 429:
        return "HTTP 429 (요청 횟수 제한)"
    if code >= 500:
        return f"HTTP {code} (서버 내부 오류)"
    return f"HTTP {code}"


@st.cache_data(ttl=3600, show_spinner=False)
def request_book_api(endpoint, parameters, api_key):
    """두 공식 HTTPS 주소에 순서대로 요청하고 실패 이유를 안내합니다.

    성공한 응답만 캐시합니다. 인증키 및 인증키를 포함한 URL은
    오류 메시지에 절대 출력하지 않습니다.
    """
    query = dict(parameters)
    query.update({"authKey": api_key, "format": "json"})
    issues = []

    for host_label, base in API_BASES:
        # 인증키는 서버로만 전송하며 화면·로그에 URL 자체를 출력하지 않습니다.
        url = base + "/" + endpoint + "?" + urlencode(query)
        request = Request(url, headers={
            "Accept": "application/json, */*;q=0.7",
            "User-Agent": "Mozilla/5.0 (compatible; Bookmoa/1.0)",
        })
        try:
            with API_OPENER.open(request, timeout=8) as response:
                payload = response.read(1_500_001)
        except HTTPError as exc:
            issues.append(f"{host_label}: {_http_reason(exc.code)}")
            continue
        except (URLError, TimeoutError, OSError) as exc:
            issues.append(f"{host_label}: {_network_reason(exc)}")
            continue

        if len(payload) > 1_500_000:
            issues.append(f"{host_label}: 응답 크기 초과")
            continue
        try:
            parsed = json.loads(payload.decode("utf-8-sig"))
        except (ValueError, UnicodeDecodeError):
            issues.append(f"{host_label}: JSON이 아닌 응답")
            continue

        body = parsed.get("response") if isinstance(parsed, dict) else None
        if not isinstance(body, dict):
            issues.append(f"{host_label}: 예상하지 못한 응답 구조")
            continue

        if body.get("error") or body.get("errorMsg") or body.get("errorMessage"):
            # API 반환 문자열에 인증키·URL이 포함될 수 있으므로 원문은 숨깁니다.
            issues.append(f"{host_label}: API 인증 또는 요청 조건 오류")
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
        + " · Streamlit Secrets 인증키를 다시 확인하고, "
          "계속 실패하면 표시된 HTTP 코드로 정보나루에 문의해 주세요."
    )


def find_books(keyword, api_key):
    return request_book_api(
        "srchBooks",
        {"keyword": keyword, "pageNo": 1, "pageSize": 9},
        api_key,
    )


def find_popular_books(api_key):
    # 집계 지연을 고려해 최근 7일을 제외한 과거 90일을 조회한다.
    end = date.today() - timedelta(days=7)
    start = end - timedelta(days=89)
    books = request_book_api(
        "loanItemSrch",
        {"startDt": start.isoformat(), "endDt": end.isoformat(),
         "pageNo": 1, "pageSize": 5},
        api_key,
    )
    return books, (start.isoformat(), end.isoformat())


def display_catalog_books(books, prefix, columns=3):
    """검색에서 책을 선택하면 바로 활동 도서, 서재 저장은 별개."""
    if not books:
        st.info("검색 결과가 없습니다. 다른 키워드로 검색하거나 직접 입력하세요.")
        return
    library = st.session_state.bm_library_books
    for i in range(0,len(books),columns):
        group = st.columns(columns, gap="small")
        for j, book in enumerate(books[i:i+columns]):
            index = i+j
            key = record_id(book["title"],book.get("author", ""))
            selected = st.session_state.bm_selected == key
            with group[j]:
                with st.container(border=True):
                    image_url = book.get("image_url","")
                    if image_url:
                        try:
                            st.image(image_url, width=100)
                        except Exception:
                            st.caption("📖 표지 없음")
                    else:
                        st.caption("📖 표지 없음")
                    st.markdown("**"+book["title"]+"**")
                    details = " · ".join(
                        x for x in (book.get("author",""),
                                    book.get("publisher","")) if x
                    )
                    if details:
                        st.caption(details)
                    if prefix == "popular":
                        st.caption(f"대출 순위 {book.get('ranking') or index+1}위")
                    if st.button(
                        "✅ 활동 도서 선택됨" if selected else "📖 이 책으로 활동",
                        key=f"choose_{prefix}_{index}",
                        disabled=selected, use_container_width=True,
                        type="secondary" if selected else "primary",
                    ):
                        choose_activity_book(book)
                    if st.button(
                        "✅ 서재에 담김" if key in library else "＋ 나의 서재에 담기",
                        key=f"keep_{prefix}_{index}",
                        disabled=key in library, use_container_width=True,
                    ):
                        save_library_book(book)


def show_book_catalog():
    st.markdown("#### 🔎 책 검색과 인기 도서 추천")
    st.caption("도서관 정보나루의 실제 도서·대출 정보를 활용합니다.")

    api_key = api_key_from_secrets()
    if not api_key:
        st.info(
            "도서 검색과 추천은 정보나루 API 인증키 등록 후 이용할 수 있습니다. "
            "Streamlit Cloud의 Settings → Secrets에 "
            "DATA4LIBRARY_API_KEY를 등록해 주세요. "
            "기존 도서관 기능은 그대로 이용 가능합니다."
        )
        return

    tab_search, tab_popular = st.tabs(["🔎 책 검색", "🏆 인기 대출도서 5권"])

    with tab_search:
        with st.form("bm_book_search_form"):
            keyword = st.text_input(
                "책 제목 또는 키워드", placeholder="예: 어린 왕자, 과학, 역사",
                max_chars=70,
            )
            submitted = st.form_submit_button("도서 검색", type="primary")
        if submitted:
            keyword = keyword.strip()
            if not keyword:
                st.warning("검색어를 입력해 주세요.")
            else:
                try:
                    st.session_state.bm_search_results = find_books(keyword, api_key)
                    st.session_state.bm_last_query = keyword
                    st.session_state.bm_catalog_error = None
                except BookApiError as exc:
                    st.session_state.bm_catalog_error = str(exc)
                    st.session_state.bm_search_results = None
        if st.session_state.bm_catalog_error:
            st.warning(st.session_state.bm_catalog_error)
        if st.session_state.bm_search_results is not None:
            st.caption(f"'{st.session_state.bm_last_query}' 검색 결과")
            display_catalog_books(st.session_state.bm_search_results, "search")

    with tab_popular:
        st.caption("전국 공공도서관 대출 통계를 바탕으로 선정한 도서입니다.")
        if st.button("🏆 인기 도서 5권 불러오기", use_container_width=True):
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
                st.caption(f"집계 요청 기간: {dates[0]} ~ {dates[1]}")
            display_catalog_books(
                st.session_state.bm_popular_results, "popular", columns=3,
            )


# ---------------------------------------------------------
# 메인 화면: 책을 먼저 고르고, 활동은 한 번의 클릭으로 시작합니다.
# ---------------------------------------------------------
init_state()
db_ready = init_database()

with st.sidebar:
    st.title("📚 책모아")
    st.markdown("#### 이동하기")
    st.page_link("main.py", label="🏠 도서관", use_container_width=True)
    links = [
        ("pages/0_나의_서재.py", "📚 나의 서재"),
        ("pages/1_독서_집중실.py", "⏱️ 독서 집중실"),
        ("pages/2_숏폼_브레이커.py", "🎮 숏폼 브레이커"),
    ]
    for path, label in links:
        if (ROOT / path).is_file():
            st.page_link(path, label=label, use_container_width=True)
    st.divider()
    st.markdown("#### 👤 내 계정")
    if not db_ready:
        st.warning("로그인 저장소에 연결하지 못했습니다. 현재는 체험만 가능합니다.")
    elif st.session_state.bm_user_id is None:
        t_login, t_signup = st.tabs(["로그인", "회원가입"])
        with t_login:
            with st.form("login_form"):
                username = st.text_input("아이디",key="login_username")
                password = st.text_input("비밀번호",type="password",key="login_password")
                submitted = st.form_submit_button("로그인")
            if submitted:
                uid = authenticate(username.strip(), password)
                if uid is None:
                    st.error("아이디 또는 비밀번호를 확인해 주세요.")
                elif load_records(uid):
                    st.session_state.bm_user_id = uid
                    st.session_state.bm_username = username.strip()
                    st.rerun()
                else:
                    st.error("계정 기록을 불러올 수 없습니다.")
        with t_signup:
            with st.form("signup_form"):
                new_username = st.text_input("새 아이디",key="signup_username")
                new_password = st.text_input("새 비밀번호 (8자 이상)",type="password",key="signup_password")
                confirm = st.text_input("비밀번호 확인",type="password",key="signup_confirm")
                submitted_new = st.form_submit_button("회원가입")
            if submitted_new:
                if new_password != confirm:
                    st.error("비밀번호가 일치하지 않습니다.")
                else:
                    error = register_user(new_username.strip(), new_password)
                    if error:
                        st.error(error)
                    else:
                        st.success("가입되었습니다. 로그인 탭에서 로그인해 주세요.")
    else:
        st.success(f"{st.session_state.bm_username}님 로그인 중")
        if st.button("로그아웃",use_container_width=True):
            reset_session()
            st.rerun()
    st.caption("로컬 SQLite는 서버 재시작·재배포 시 기록 유지가 보장되지 않습니다.")

st.title("📚 책모아 도서관")
st.caption("책을 선택하고 한줄평·독후감·책갈피 중 원하는 활동을 바로 시작하세요.")

# 첫 화면에서 지금 활동할 책을 항상 명확히 표시합니다.
current_key = st.session_state.bm_selected
current_book = st.session_state.bm_books.get(current_key)
if current_book:
    status_col, library_col = st.columns([3, 1])
    with status_col:
        text = f"📖 지금 활동할 책: **{current_book['title']}**"
        if current_book.get("author"):
            text += f" · {current_book['author']}"
        st.success(text)
    with library_col:
        in_library = current_key in st.session_state.bm_library_books
        if st.button(
            "✅ 서재에 있음" if in_library else "＋ 서재에 담기",
            disabled=in_library,
            use_container_width=True,
            key="bm_save_active_to_library",
        ):
            save_library_book(current_book)
else:
    st.info("아직 활동할 책이 없습니다. 아래에서 검색하거나 책 제목을 입력하세요.")

# 책장 이동 과정 없이 바로 활동을 선택할 수 있습니다.
st.markdown("### ① 활동할 책 고르기")
with st.expander("🔎 책 검색·인기 도서·직접 입력", expanded=not current_book):
    show_book_catalog()
    st.markdown("#### ✏️ 검색되지 않는 책은 직접 입력")
    with st.form("manual_activity_book",clear_on_submit=True):
        ca,cb = st.columns([2,1])
        title = ca.text_input("책 제목 *",max_chars=100)
        author = cb.text_input("저자 (선택)",max_chars=70)
        submitted = st.form_submit_button("📖 이 책으로 바로 활동",type="primary")
    if submitted:
        if not title.strip():
            st.warning("책 제목을 입력해 주세요.")
        else:
            choose_activity_book({"title":title,"author":author})

    if st.session_state.bm_books:
        st.markdown("#### 🕘 이전에 활동한 책")
        keys = list(st.session_state.bm_books)
        chosen = st.selectbox("기존 활동 도서",keys,
            format_func=lambda k: st.session_state.bm_books[k]["title"],
            index=keys.index(st.session_state.bm_selected)
                  if st.session_state.bm_selected in keys else 0)
        if st.button("선택한 책으로 활동",key="bm_resume_activity"):
            st.session_state.bm_selected = chosen
            st.rerun()


st.markdown("### ② 원하는 활동 바로 시작")
cols = st.columns(3, gap="small")
for i, col in enumerate(cols):
    with col:
        with st.container(border=True):
            st.markdown(f"**{EMOJIS[i]} {ZONES[i]}**")
            st.image(
                shelf_image(i, character_here=(st.session_state.bm_zone==i),
                            zone_selected=(st.session_state.bm_zone==i)),
                width=190,
            )
            is_selected = st.session_state.bm_zone == i
            if st.button(
                f"✅ {ZONES[i]} 선택됨" if is_selected else f"{ZONES[i]} 시작하기",
                key=f"bm_direct_zone_{i}", use_container_width=True,
                disabled=is_selected,
                type="secondary" if is_selected else "primary",
            ):
                st.session_state.bm_zone = i
                st.rerun()

if not current_book:
    st.caption("활동 종류는 미리 선택할 수 있습니다. 책을 고르면 곧바로 작성할 수 있어요.")

# 선택한 활동 영역을 활동 카드 바로 아래에 표시합니다.
zone = st.session_state.bm_zone
if current_book and zone is not None:
    st.markdown(f"### ✍️ {current_book['title']} · {ZONES[zone]}")
    key = current_key
    book = current_book
    if zone == 0:
        saved = st.session_state.bm_reviews.get(key,{})
        with st.form(f"review_{key}"):
            rating = st.slider("별점",1,5,int(saved.get("rating",3)))
            content = st.text_area("나의 한줄평",value=saved.get("text",""),max_chars=150,
                                   placeholder="책을 읽고 어떤 생각이 들었나요?")
            submitted = st.form_submit_button("💾 한줄평 저장",type="primary")
        if submitted:
            if len(content.strip()) < 5:
                st.warning("한줄평을 5자 이상 적어 주세요.")
            elif save_record("bookmoa_reviews",{"rating":rating,"content":content.strip()},key):
                st.session_state.bm_reviews[key] = {"rating":rating,"text":content.strip()}
                st.rerun()
        if saved:
            st.success(f"{'⭐'*saved['rating']}  {saved['text']}")
            if st.button("한줄평 삭제",key=f"delete_review_{key}"):
                if delete_record("bookmoa_reviews",key):
                    st.session_state.bm_reviews.pop(key,None)
                    st.rerun()

    elif zone == 1:
        saved = st.session_state.bm_reports.get(key,{})
        with st.form(f"report_{key}"):
            reason = st.text_area("1. 이 책을 읽게 된 이유",value=saved.get("reason",""))
            scene = st.text_area("2. 기억에 남는 장면이나 내용",value=saved.get("scene",""))
            thought = st.text_area("3. 읽은 뒤의 생각과 배운 점",value=saved.get("thought",""))
            submitted = st.form_submit_button("💾 독후감 저장",type="primary")
        if submitted:
            if not all(x.strip() for x in (reason,scene,thought)):
                st.warning("세 항목을 모두 작성해 주세요.")
            elif save_record("bookmoa_reports",{
                "reason":reason.strip(),"scene":scene.strip(),"thought":thought.strip()
            },key):
                st.session_state.bm_reports[key] = {
                    "reason":reason.strip(),"scene":scene.strip(),"thought":thought.strip()
                }
                st.rerun()
        if saved:
            output = (f"[{book['title']}] 독후감\n\n"
                      f"1. 읽게 된 이유\n{saved['reason']}\n\n"
                      f"2. 기억에 남는 내용\n{saved['scene']}\n\n"
                      f"3. 읽고 난 생각\n{saved['thought']}")
            st.download_button("📥 독후감 TXT 다운로드",output.encode("utf-8-sig"),
                               file_name="bookmoa_report.txt",mime="text/plain")
            if st.button("독후감 삭제",key=f"delete_report_{key}"):
                if delete_record("bookmoa_reports",key):
                    st.session_state.bm_reports.pop(key,None)
                    st.rerun()

    else:
        saved = st.session_state.bm_bookmarks.get(key,{})
        default_quote = saved.get("quote") or st.session_state.bm_reviews.get(key,{}).get("text","")
        st.caption("문장·디자인·장식을 골라 나만의 책갈피를 만들고 PNG로 저장하세요.")
        quote = st.text_area("책갈피에 넣을 문장",value=default_quote,
                             max_chars=200,key=f"bm_q_{key}",
                             placeholder="기억하고 싶은 문장이나 직접 쓴 감상을 입력하세요")
        cols = st.columns(3)
        layouts = ["클래식 세로","미니 책갈피","가로 문장 카드"]
        motifs = ["별","달","꽃","책"]
        palettes = list(PALETTES)
        def idx(options,value):
            return options.index(value) if value in options else 0
        with cols[0]:
            palette = st.selectbox("배경 색상",palettes,
                                   index=idx(palettes,saved.get("palette","크림")),
                                   key=f"bm_pal_{key}")
        with cols[1]:
            layout = st.selectbox("책갈피 크기",layouts,
                                  index=idx(layouts,saved.get("layout","클래식 세로")),
                                  key=f"bm_layout_{key}")
        with cols[2]:
            motif = st.selectbox("장식",motifs,
                                 index=idx(motifs,saved.get("motif","별")),
                                 key=f"bm_motif_{key}")
        signature = st.text_input("하단에 넣을 이름 또는 문구 (선택)",
                                  value=saved.get("signature",""),max_chars=30,
                                  key=f"bm_sign_{key}")
        if quote.strip():
            try:
                png = make_bookmark(book["title"],book.get("author",""),quote,
                                    palette,layout,motif,signature)
            except (ValueError,RuntimeError) as exc:
                st.warning(str(exc))
                png = None
            if png:
                with st.container(border=True):
                    st.markdown("**🖼️ 미리보기**")
                    st.image(png,width=350)
                b1,b2 = st.columns(2)
                with b1:
                    if st.button("💾 내 책갈피 저장",type="primary",use_container_width=True):
                        if save_bookmark_design(key,quote.strip(),palette,layout,motif,signature):
                            st.success("책갈피의 문장과 디자인을 저장했어요.")
                with b2:
                    st.download_button("📥 PNG 다운로드",png,
                                       file_name="bookmoa_bookmark.png",mime="image/png",
                                       use_container_width=True)
        else:
            st.info("문장을 입력하면 책갈피 미리보기가 나타납니다.")
else:
    if zone is None:
        st.caption("위의 세 활동 가운데 원하는 것을 누르세요.")
    elif current_book is None:
        st.caption("아래에서 책을 선택하면 작성 화면이 열립니다.")

st.divider()
st.caption("책 검색에서 '이 책으로 활동'은 활동 도서만 정합니다. "
           "'나의 서재에 담기'를 별도로 누른 책만 서재에 저장됩니다.")
st.caption("로그인 기록은 현재 서버의 SQLite에 저장되며, 서버 재시작·재배포 시 사라질 수 있습니다.")
