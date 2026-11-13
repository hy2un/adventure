"""책모아 메인: 캐릭터 이동형 도서관.

실행: streamlit run main.py
pages/1_숏폼_브레이커.py를 포함한 멀티페이지 프로젝트.
HTML·CSS·JavaScript·외부 API 사용 없음.
"""
import json
from io import BytesIO
from pathlib import Path

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

st.set_page_config(page_title="책모아 | 도서관", page_icon="📚", layout="wide")

STATIONS = ["한줄평", "독후감", "책갈피"]
PALETTES = {
    "크림": ("#F7EFDE", "#78533C", "#453527"),
    "민트": ("#E1F1E9", "#3A7565", "#24473C"),
    "라벤더": ("#EEE9F7", "#725A9B", "#44375F"),
}
FONT_PATHS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
]


def korean_font(size):
    """운영체제에 있는 한글 폰트를 탐색한다."""
    for path in FONT_PATHS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_center(draw, text, center_x, y, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text((center_x - (bbox[2] - bbox[0]) / 2, y), text, font=font, fill=fill)


def wrap_pixels(draw, text, font, max_width):
    """한글과 영문을 픽셀 너비에 맞춰 줄바꿈한다."""
    lines, part = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(part)
            part = ""
        elif draw.textbbox((0, 0), part + ch, font=font)[2] <= max_width:
            part += ch
        else:
            if part:
                lines.append(part)
            part = ch
    if part:
        lines.append(part)
    return lines


@st.cache_data(show_spinner=False)
def draw_library(position):
    """배경과 캐릭터를 합친 도서관 이미지 생성(Pillow만 사용)."""
    width, height = 1170, 465
    img = Image.new("RGB", (width, height), "#F2E6D5")
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, width, 344), fill="#F0E3D1")
    d.rectangle((0, 0, width, 25), fill="#9F7659")
    d.rectangle((0, 344, width, height), fill="#D5B99A")
    for x in range(0, width, 90):
        d.line((x, 344, x + 55, height), fill="#B99D82", width=2)
    d.line((0, 344, width, 344), fill="#96735B", width=7)

    centers = [200, 585, 970]
    shelf_tints = ["#9D6E56", "#648D89", "#85709C"]
    spine_colors = ["#C69271", "#628DA6", "#B0A66D", "#997DA8", "#7B9E7D"]
    for idx, cx in enumerate(centers):
        x0, x1 = cx - 158, cx + 158
        d.rounded_rectangle((x0, 121, x1, 341), radius=10, fill="#946E50", outline="#6E4B37", width=5)
        d.rectangle((x0 + 15, 136, x1 - 15, 328), fill="#5B4537")
        for row, sy in enumerate((148, 207, 267)):
            for j in range(12):
                sx = x0 + 23 + 23 * j
                bh = 32 + (j * 5 + row * 2) % 13
                d.rectangle((sx, sy + 43 - bh, sx + 15, sy + 43), fill=spine_colors[(j + row) % len(spine_colors)])
            d.rectangle((x0 + 11, sy + 43, x1 - 11, sy + 51), fill="#B18560")
        d.rounded_rectangle((cx - 119, 57, cx + 119, 111), radius=17, fill="#FFF9ED", outline=shelf_tints[idx], width=4)
        draw_center(d, STATIONS[idx], cx, 62, korean_font(29), shelf_tints[idx])
        if position == idx:
            d.rounded_rectangle((x0 - 2, 119, x1 + 2, 342), radius=11, outline="#FFD36D", width=8)

    # 캐릭터의 위치는 서가 선택에 따라 변경된다.
    cx = centers[position]
    d.ellipse((cx - 40, 433, cx + 40, 448), fill="#B5A18D")
    d.line((cx - 14, 408, cx - 18, 438), fill="#394A5D", width=13)
    d.line((cx + 14, 408, cx + 18, 438), fill="#394A5D", width=13)
    d.rounded_rectangle((cx - 32, 361, cx + 32, 417), radius=15, fill="#5681A3")
    d.line((cx - 31, 376, cx - 51, 407), fill="#F0C6A2", width=11)
    d.line((cx + 31, 376, cx + 51, 407), fill="#F0C6A2", width=11)
    d.ellipse((cx - 29, 304, cx + 29, 365), fill="#F0C6A2")
    d.pieslice((cx - 31, 298, cx + 31, 357), 170, 365, fill="#514039")
    d.ellipse((cx - 13, 335, cx - 9, 339), fill="#34303A")
    d.ellipse((cx + 9, 335, cx + 13, 339), fill="#34303A")
    d.arc((cx - 10, 343, cx + 10, 352), 0, 180, fill="#9B6A5C", width=2)
    d.rounded_rectangle((cx - 80, 445, cx + 80, 464), radius=7, fill="#F6F0E6")
    draw_center(d, "현재 위치", cx, 446, korean_font(14), "#39546A")
    return img


def make_bookmark(title, author, quote, palette_name):
    """직접 쓴 문장으로 책갈피 PNG 파일을 만든다."""
    bg, accent, ink = PALETTES[palette_name]
    w, h = 540, 900
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((22, 22, w - 22, h - 22), radius=25, outline=accent, width=5)
    draw_center(d, "MY BOOKMARK", w // 2, 80, korean_font(27), accent)
    d.line((80, 140, w - 80, 140), fill=accent, width=3)

    title_font = korean_font(35)
    for n, line in enumerate(wrap_pixels(d, title, title_font, 410)[:3]):
        draw_center(d, line, w // 2, 186 + n * 54, title_font, ink)
    if author:
        draw_center(d, author[:25], w // 2, 352, korean_font(20), accent)

    body_font = korean_font(29)
    quote_lines = wrap_pixels(d, quote, body_font, 390)
    if len(quote_lines) > 7:
        raise ValueError("책갈피 문장이 너무 깁니다. 7줄 이내로 줄여 주세요.")
    start_y = 500 - len(quote_lines) * 24
    for n, line in enumerate(quote_lines):
        draw_center(d, line, w // 2, start_y + n * 49, body_font, ink)
    d.line((80, 797, w - 80, 797), fill=accent, width=3)
    draw_center(d, "책모아 도서관", w // 2, 822, korean_font(24), accent)

    output = BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


def book_key(title, author):
    return title.strip().casefold() + "|" + author.strip().casefold()


def init_state():
    defaults = {
        "bm_pos": 0,
        "bm_active": None,
        "bm_books": {},
        "bm_current": None,
        "bm_reviews": {},
        "bm_reports": {},
        "bm_bookmark_png": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def make_report(book, record):
    return (f"[{book['title']}] 독후감\n저자: {book['author']}\n\n"
            f"1. 읽게 된 이유\n{record['reason']}\n\n"
            f"2. 인상 깊었던 내용\n{record['scene']}\n\n"
            f"3. 읽고 난 뒤의 생각\n{record['thought']}")


def export_records():
    return json.dumps({
        "version": 1,
        "books": st.session_state.bm_books,
        "current": st.session_state.bm_current,
        "reviews": st.session_state.bm_reviews,
        "reports": st.session_state.bm_reports,
    }, ensure_ascii=False, indent=2).encode("utf-8-sig")


def import_records(data):
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("책모아 기록 파일 형식이 아닙니다.")
    books, reviews, reports = (data.get(x) for x in ("books", "reviews", "reports"))
    if not isinstance(books, dict) or not isinstance(reviews, dict) or not isinstance(reports, dict):
        raise ValueError("필수 기록 항목이 없습니다.")
    if len(books) > 100:
        raise ValueError("도서 수가 너무 많습니다.")
    valid_books = {}
    for key, value in books.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        title, author = value.get("title"), value.get("author")
        if not isinstance(title, str) or not isinstance(author, str):
            continue
        if title.strip() and len(title) <= 100 and len(author) <= 70:
            valid_books[key] = {"title": title, "author": author}
    st.session_state.bm_books = valid_books
    st.session_state.bm_reviews = {
        key: value for key, value in reviews.items()
        if key in valid_books and isinstance(value, dict)
        and isinstance(value.get("text"), str)
        and isinstance(value.get("rating"), int)
        and 1 <= value["rating"] <= 5
        and len(value["text"]) <= 100
    }
    st.session_state.bm_reports = {
        key: value for key, value in reports.items()
        if key in valid_books and isinstance(value, dict)
        and all(isinstance(value.get(f), str) and len(value[f]) <= 5000
                for f in ("reason", "scene", "thought"))
    }
    current = data.get("current")
    st.session_state.bm_current = current if current in valid_books else None
    st.session_state.bm_bookmark_png = None


# ────────────────── 화면 시작 ──────────────────
init_state()
st.title("📚 책모아 도서관")
st.caption("캐릭터를 이동해 한줄평·독후감·책갈피 공간을 체험하세요. (API 없이 실행)")

# PAGE 1은 pages 폴더에 있는 기존 코드를 Streamlit이 자동 인식합니다.
# 메인에서 별도의 page_link는 호출하지 않습니다.
st.caption("🎮 PAGE 1: 숏폼 브레이커는 기본 페이지 메뉴에서 이동하세요.")
st.image(draw_library(st.session_state.bm_pos), use_container_width=True)

left, enter, right = st.columns([1, 2, 1])
with left:
    if st.button("◀ 왼쪽", disabled=st.session_state.bm_pos == 0, use_container_width=True):
        st.session_state.bm_pos -= 1
        st.session_state.bm_active = None
        st.rerun()
with enter:
    if st.button(f"🚪 {STATIONS[st.session_state.bm_pos]} 공간 입장", type="primary", use_container_width=True):
        st.session_state.bm_active = st.session_state.bm_pos
        st.rerun()
with right:
    if st.button("오른쪽 ▶", disabled=st.session_state.bm_pos == 2, use_container_width=True):
        st.session_state.bm_pos += 1
        st.session_state.bm_active = None
        st.rerun()

st.divider()
st.subheader("📖 활동할 책 선택")
with st.form("add_book", clear_on_submit=True):
    col1, col2 = st.columns(2)
    title = col1.text_input("책 제목 *", max_chars=100)
    author = col2.text_input("저자(선택)", max_chars=70)
    add_book = st.form_submit_button("이 책으로 활동하기")
if add_book:
    if not title.strip():
        st.warning("책 제목을 입력해 주세요.")
    else:
        key = book_key(title, author)
        st.session_state.bm_books[key] = {"title": title.strip(), "author": author.strip()}
        st.session_state.bm_current = key
        st.session_state.bm_bookmark_png = None
        st.rerun()

if st.session_state.bm_books:
    ids = list(st.session_state.bm_books)
    current_id = st.session_state.bm_current
    selected_id = st.selectbox(
        "이전에 등록한 책 선택",
        ids,
        index=ids.index(current_id) if current_id in ids else 0,
        format_func=lambda k: st.session_state.bm_books[k]["title"],
    )
    if selected_id != current_id:
        if st.button("선택한 책으로 변경하기"):
            st.session_state.bm_current = selected_id
            st.session_state.bm_bookmark_png = None
            st.rerun()
else:
    st.info("책 제목을 먼저 등록해 주세요. 고정된 테마별 도서 목록과 API 검색은 없습니다.")

current_id = st.session_state.bm_current
book = st.session_state.bm_books.get(current_id) if current_id else None
if st.session_state.bm_active is None:
    st.info("캐릭터를 이동한 뒤 '공간 입장'을 눌러 활동을 시작하세요.")
elif book is None:
    st.info("위에서 활동할 책을 등록하면 선택한 공간을 이용할 수 있습니다.")
else:
    st.divider()
    st.subheader(f"✏️ {STATIONS[st.session_state.bm_active]} · {book['title']}")
    if st.session_state.bm_active == 0:
        saved = st.session_state.bm_reviews.get(current_id, {})
        with st.form(f"review_{current_id}"):
            rating = st.slider("별점", 1, 5, int(saved.get("rating", 3)))
            review_text = st.text_area("한줄평 (10~100자)", value=saved.get("text", ""), height=100)
            save_review = st.form_submit_button("한줄평 저장", type="primary")
        if save_review:
            clean = review_text.strip()
            if not 10 <= len(clean) <= 100:
                st.warning("한줄평은 10~100자 사이로 작성해 주세요.")
            else:
                st.session_state.bm_reviews[current_id] = {"rating": rating, "text": clean}
                st.success("한줄평을 저장했습니다.")
                st.rerun()
        if saved:
            st.success("⭐" * saved["rating"] + "  " + saved["text"])
            if st.button("한줄평 삭제"):
                st.session_state.bm_reviews.pop(current_id, None)
                st.rerun()

    elif st.session_state.bm_active == 1:
        saved = st.session_state.bm_reports.get(current_id, {})
        with st.form(f"report_{current_id}"):
            reason = st.text_area("1. 책을 읽게 된 이유", value=saved.get("reason", ""), height=95)
            scene = st.text_area("2. 인상 깊었던 내용", value=saved.get("scene", ""), height=100)
            thought = st.text_area("3. 읽고 난 뒤의 생각", value=saved.get("thought", ""), height=100)
            save_report = st.form_submit_button("독후감 저장", type="primary")
        if save_report:
            if not all(x.strip() for x in (reason, scene, thought)):
                st.warning("세 항목을 모두 작성해 주세요.")
            else:
                st.session_state.bm_reports[current_id] = {
                    "reason": reason.strip(), "scene": scene.strip(), "thought": thought.strip()
                }
                st.success("독후감을 저장했습니다.")
                st.rerun()
        if saved:
            full_text = make_report(book, saved)
            st.text_area("저장된 독후감 미리보기", full_text, height=260, disabled=True)
            st.download_button("독후감 TXT 다운로드", full_text.encode("utf-8-sig"),
                               file_name="bookmoa_report.txt", mime="text/plain")
            if st.button("독후감 삭제"):
                st.session_state.bm_reports.pop(current_id, None)
                st.rerun()

    elif st.session_state.bm_active == 2:
        review = st.session_state.bm_reviews.get(current_id, {}).get("text", "")
        quote = st.text_area("책갈피 문장 (직접 작성 가능)", value=review,
                             max_chars=100, key=f"quote_{current_id}")
        design = st.selectbox("디자인 색상", list(PALETTES), key="bm_palette")
        if st.button("책갈피 PNG 만들기", type="primary"):
            if not quote.strip():
                st.warning("책갈피에 넣을 문장을 작성해 주세요.")
            else:
                try:
                    st.session_state.bm_bookmark_png = make_bookmark(
                        book["title"], book["author"], quote.strip(), design
                    )
                    st.rerun()
                except ValueError as exc:
                    st.warning(str(exc))
        if st.session_state.bm_bookmark_png is not None:
            st.image(st.session_state.bm_bookmark_png, width=260)
            st.download_button("📥 PNG 다운로드", data=st.session_state.bm_bookmark_png,
                               file_name="bookmoa_bookmark.png", mime="image/png")

st.divider()
with st.expander("💾 내 기록 저장 / 불러오기 (로그인 없음)"):
    st.caption("작성 내용은 현재 세션에서 유지됩니다. 나중에 이어 하려면 JSON을 다운로드하고 다음에 다시 불러오세요.")
    st.download_button("기록 JSON 다운로드", export_records(),
                       file_name="bookmoa_records.json", mime="application/json")
    uploaded = st.file_uploader("기록 파일 선택", type=["json"])
    if uploaded is not None and st.button("저장된 기록 불러오기"):
        try:
            if len(uploaded.getvalue()) > 500_000:
                raise ValueError("500KB 이하의 파일을 선택해 주세요.")
            raw = uploaded.getvalue().decode("utf-8-sig")
            import_records(json.loads(raw))
            st.success("기록을 불러왔습니다.")
            st.rerun()
        except (ValueError, UnicodeError, json.JSONDecodeError, TypeError) as exc:
            st.error(f"기록 파일을 확인해 주세요: {exc}")

st.caption("MAIN 도서관 | PAGE 1 숏폼 브레이커")
