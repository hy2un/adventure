"""책모아 멀티페이지 PAGE 1 — 숏폼 브레이커 (Python + Streamlit + Pillow).

게임 규칙: 책이 3개 통로로 다가오는 숏폼을 페이지 공격으로 막는다.
버튼 1번 = 게임 1턴. 적이 책에 닿으면 집중력(하트)이 1 줄어든다.
"""
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TARGET = 12          # 물리쳐야 하는 숏폼 수
MAX_LIVES = 3        # 집중력
LANES = 3            # 공격 통로 수
WIDTH, HEIGHT = 1160, 495
FONT_PATHS = [
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",  # Linux/Colab
    "C:/Windows/Fonts/malgun.ttf",                    # Windows
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",       # macOS
]


def font(size):
    """설치된 한국어 글꼴을 찾고, 없으면 기본 글꼴을 사용한다."""
    for path in FONT_PATHS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def new_enemy():
    return {"distance": random.randint(4, 6), "color": random.choice(["red", "pink"])}


def new_game():
    return {
        "status": "ready",  # ready / playing / won / lost
        "score": 0,
        "lives": MAX_LIVES,
        "turn": 0,
        "enemies": [new_enemy() for _ in range(LANES)],
        "last_lane": None,
        "last_hit_distance": None,
        "message": "책이 주인공! 다가오는 숏폼을 막아 주세요.",
    }


def start_game(game):
    game.update(new_game())
    game["status"] = "playing"
    game["message"] = "가장 가까이 다가온 숏폼부터 막아 보세요!"


def attack(game, lane):
    """버튼을 누른 통로의 숏폼을 제거하고 나머지를 한 칸 전진시킨다."""
    if game["status"] != "playing" or not 0 <= lane < LANES:
        return

    game["turn"] += 1
    game["last_lane"] = lane
    game["last_hit_distance"] = game["enemies"][lane]["distance"]
    game["score"] += 1
    game["message"] = f"{lane + 1}번 통로에 책장 공격 성공!"

    if game["score"] >= TARGET:
        game["status"] = "won"
        game["message"] = "승리! 책이 숏폼을 물리치고 독서 시간을 지켰습니다."
        return

    # 공격한 통로에는 새로운 숏폼이 먼 거리에서 나타난다.
    game["enemies"][lane] = new_enemy()

    # 공격하지 않은 두 통로의 숏폼은 한 칸씩 다가온다.
    for i, enemy in enumerate(game["enemies"]):
        if i == lane:
            continue
        enemy["distance"] -= 1
        if enemy["distance"] <= 0:
            game["lives"] -= 1
            game["enemies"][i] = new_enemy()
            game["message"] = "숏폼 하나가 도착했습니다! 집중력이 1 감소했어요."

    if game["lives"] <= 0:
        game["status"] = "lost"
        game["message"] = "집중력이 모두 소진됐습니다. 다시 도전해 보세요!"


def draw_book(draw, x, y):
    """책 주인공(그림)을 Pillow로 직접 그린다."""
    # 팔과 다리
    draw.line([(x - 29, y + 59), (x - 44, y + 83)], fill="#F5CF92", width=11)
    draw.line([(x + 37, y + 59), (x + 51, y + 82)], fill="#F5CF92", width=11)
    draw.line([(x - 12, y + 98), (x - 19, y + 123)], fill="#F5CF92", width=12)
    draw.line([(x + 20, y + 98), (x + 27, y + 123)], fill="#F5CF92", width=12)
    # 펼친 책 + 책장
    draw.rounded_rectangle((x - 58, y - 20, x + 59, y + 102), radius=12, fill="#236A9C", outline="#A6DFF6", width=4)
    draw.polygon([(x, y - 7), (x - 43, y - 17), (x - 43, y + 84), (x, y + 96)], fill="#F4E7C9")
    draw.polygon([(x, y - 7), (x + 43, y - 17), (x + 43, y + 84), (x, y + 96)], fill="#FFFAEC")
    draw.line([(x, y - 6), (x, y + 92)], fill="#D0BDA1", width=3)
    for j in range(3):
        draw.line([(x - 34, y + 15 + j * 13), (x - 10, y + 18 + j * 13)], fill="#BDAA8D", width=2)
        draw.line([(x + 10, y + 18 + j * 13), (x + 34, y + 15 + j * 13)], fill="#BDAA8D", width=2)
    # 표정
    draw.ellipse((x - 20, y + 48, x - 13, y + 55), fill="#274458")
    draw.ellipse((x + 13, y + 48, x + 20, y + 55), fill="#274458")
    draw.arc((x - 13, y + 53, x + 13, y + 73), 10, 165, fill="#274458", width=3)


def draw_enemy(draw, x, y, color):
    """실제 플랫폼 로고 대신 일반적인 숏폼 재생 아이콘을 그린다."""
    fill = "#E55074" if color == "red" else "#A25CE3"
    draw.rounded_rectangle((x - 41, y - 39, x + 41, y + 39), radius=18, fill=fill, outline="#FFD9E5", width=3)
    draw.polygon([(x - 10, y - 19), (x - 10, y + 19), (x + 19, y)], fill="#FFFFFF")


def render_board(game):
    """게임 보드를 이미지로 생성한다. HTML/CSS는 사용하지 않는다."""
    image = Image.new("RGB", (WIDTH, HEIGHT), "#17263A")
    draw = ImageDraw.Draw(image)

    # 도서관 실내 분위기의 배경
    for y in range(HEIGHT):
        r = int(20 + 17 * y / HEIGHT)
        g = int(36 + 11 * y / HEIGHT)
        b = int(57 + 8 * y / HEIGHT)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))
    draw.rounded_rectangle((16, 15, WIDTH - 16, HEIGHT - 14), radius=25, outline="#52627B", width=2)
    for bx in (25, 72, 1065, 1111):
        for row in range(5):
            for j in range(3):
                xx = bx + j * 13
                yy = 62 + row * 75
                draw.rectangle((xx, yy, xx + 8, yy + 42), fill=["#9A7554", "#466E8F", "#729283"][(row+j)%3])

    draw.text((88, 27), "BOOK  VS  SHORTS", font=font(34), fill="#FAF6E9")
    draw.text((91, 74), "책의 반격 — 숏폼이 도착하기 전에 막아라!", font=font(20), fill="#A8BBD1")

    ys = [184, 296, 408]
    for lane, y in enumerate(ys):
        draw.rounded_rectangle((255, y - 42, 990, y + 42), radius=16, fill="#27384D", outline="#3E5773", width=2)
        for x in (330, 440, 550, 660, 770, 880):
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill="#64788E")
        draw.text((282, y - 18), str(lane + 1), font=font(26), fill="#DFEAF8")

        enemy = game["enemies"][lane]
        x = 300 + 100 * enemy["distance"]
        draw_enemy(draw, x, y, enemy["color"])
        if game["last_lane"] == lane:
            hit_x = 300 + 100 * game["last_hit_distance"]
            draw.line([(223, y), (hit_x - 65, y)], fill="#FFD76A", width=7)
            draw.polygon([(hit_x - 56, y - 14), (hit_x - 29, y), (hit_x - 56, y + 14)], fill="#FFD76A")

    draw_book(draw, 166, 247)
    draw.text((107, 385), "책의 수호자", font=font(23), fill="#F5E7C7")
    draw.text((1030, 453), "BOOKMOA", font=font(16), fill="#A8B9CB")
    return image


def show_page():
    import streamlit as st

    st.set_page_config(page_title="책모아 | 숏폼 브레이커", page_icon="📖", layout="wide")

    if "shortform_game" not in st.session_state:
        st.session_state.shortform_game = new_game()
    game = st.session_state.shortform_game

    st.title("📚 숏폼 브레이커 | 책의 반격")
    st.caption("책이 숏폼에 맞서 싸우는 3개 통로 방어 게임 — 클릭 1회가 게임 1턴입니다.")

    left, center, right = st.columns(3)
    left.metric("📖 막아낸 숏폼", f"{game['score']} / {TARGET}")
    center.metric("❤️ 독서 집중력", f"{game['lives']} / {MAX_LIVES}")
    right.metric("🎮 진행 턴", game["turn"])
    st.progress(min(game["score"] / TARGET, 1.0))
    st.image(render_board(game), use_container_width=True)

    if game["status"] == "ready":
        st.info("책이 세 통로로 다가오는 숏폼을 페이지 공격으로 막습니다. 먼저 가장 가까운 아이콘을 공격하세요.")
        if st.button("▶ 게임 시작", type="primary", use_container_width=True):
            start_game(game)
            st.rerun()

    elif game["status"] == "playing":
        st.info(game["message"])
        buttons = st.columns(3)
        for lane, col in enumerate(buttons):
            if col.button(f"📖 {lane + 1}번 통로 공격", key=f"sf_attack_{lane}", use_container_width=True):
                attack(game, lane)
                st.rerun()
        st.caption("공격한 통로의 숏폼은 사라지고, 나머지 두 통로의 숏폼은 한 칸씩 책을 향해 접근합니다.")

    elif game["status"] == "won":
        st.success("🎉 책의 승리! 숏폼 12개를 막아 독서 시간을 지켰습니다.")

    elif game["status"] == "lost":
        st.error("집중력이 0이 됐습니다. 공격할 통로의 순서를 바꿔 다시 도전해 보세요.")

    if game["status"] != "ready":
        if st.button("↻ 다시 시작", use_container_width=True):
            start_game(game)
            st.rerun()


show_page()  # Streamlit 멀티페이지의 pages/ 파일은 실행될 때 이 함수를 호출합니다.
