"""책모아 게임 | 책의 반격: 숏폼 방어 게임.

실행: 프로젝트 최상위에서 `streamlit run main.py`
필요 파일: 프로젝트 최상위 book_guardian.png 및 shortform_demon.png (requirements: streamlit, Pillow).
기존 MAIN 도서관의 로그인 상태는 세션에서 읽기만 합니다.
"""
from pathlib import Path
import random

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

st.set_page_config(
    page_title="책모아 | 숏폼 브레이커",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent.parent
HERO_PATH = ROOT / "book_guardian.png"
DEMON_PATH = ROOT / "shortform_demon.png"
GOAL = 12
MAX_FOCUS = 3
LANES = 3
BOARD_W, BOARD_H = 1400, 760
LANE_Y = (314, 453, 592)
DEFENSE_X = 371


def new_enemy():
    """방어선까지 4~6턴 거리에 있는 새로운 숏폼."""
    return {"distance": random.randint(4, 6), "color": random.choice(("pink", "purple", "orange"))}


def new_game():
    return {
        "status": "ready", "score": 0, "focus": MAX_FOCUS, "turn": 0,
        "enemies": [new_enemy() for _ in range(LANES)],
        "last_hit": None,
        "message": "게임 시작을 누르면 숏폼이 책을 향해 다가옵니다.",
    }


def start_game(game):
    game.clear()
    game.update(new_game())
    game["status"] = "playing"
    game["message"] = "가장 가까이 다가온 숏폼이 있는 통로부터 막아 보세요."


def attack(game, lane):
    """선택 통로 공격 후 나머지 숏폼을 왼쪽으로 한 칸 이동."""
    if game["status"] != "playing" or lane not in range(LANES):
        return
    game["turn"] += 1
    old_distance = game["enemies"][lane]["distance"]
    game["last_hit"] = (lane, old_distance)
    game["score"] += 1
    # 막아낸 통로에는 새로운 숏폼이 오른쪽에 등장
    game["enemies"][lane] = new_enemy()
    # 다른 통로만 왼쪽으로 전진
    reached = 0
    for index, enemy in enumerate(game["enemies"]):
        if index == lane:
            continue
        enemy["distance"] -= 1
        if enemy["distance"] <= 0:
            reached += 1
            game["focus"] = max(0, game["focus"] - 1)
            game["enemies"][index] = new_enemy()
    if game["focus"] == 0:
        game["status"] = "lost"
        game["message"] = "숏폼이 독서 공간에 3번 도착했습니다. 다시 도전해 보세요!"
    elif game["score"] >= GOAL:
        game["status"] = "won"
        game["message"] = "승리! 책이 숏폼 12개를 막고 독서 공간을 지켰습니다!"
    elif reached:
        game["message"] = f"숏폼 {reached}개가 방어선을 넘었습니다. 집중력 {game['focus']}/{MAX_FOCUS}"
    else:
        game["message"] = f"{lane + 1}번 통로 방어 성공! 나머지 숏폼은 한 칸 가까워졌습니다."


def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf" if bold else "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "C:/Windows/Fonts/malgunbd.ttf" if bold else "C:/Windows/Fonts/malgun.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def pill(d, box, fill, outline=None, width=2, radius=20):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def load_sprite(path, max_width, max_height):
    """투명 PNG를 비율 유지한 채로 축소한다. 완전히 보이도록 크기를 제한한다."""
    if not path.is_file():
        return None
    try:
        with Image.open(path) as original:
            sprite = original.convert("RGBA")
            # 그림 전체가 프레임 안에 들어가도록 비율을 보존한다.
            sprite.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            return sprite
    except (OSError, ValueError):
        return None


def draw_enemy(bg, x, y, color):
    """숏폼 악마 캐릭터 PNG를 각 통로 가운데에 표시한다."""
    d = ImageDraw.Draw(bg)
    glow = {"pink": "#FF759A", "purple": "#B08AFF", "orange": "#FFBF7D"}[color]
    d.ellipse((x - 52, y - 51, x + 52, y + 51), fill=glow)
    sprite = load_sprite(DEMON_PATH, 106, 102)
    if sprite is not None:
        bg.alpha_composite(sprite, (x - sprite.width // 2, y - sprite.height // 2))
    else:
        # 파일을 못 읽어도 게임 자체는 플레이할 수 있도록 간단한 적 표시
        d.rounded_rectangle((x - 39, y - 43, x + 39, y + 43), radius=17, fill="#F6488C")
        d.polygon(((x - 10, y - 17), (x - 10, y + 17), (x + 21, y)), fill="white")
    # 이동 방향을 짧은 움직임 선으로 표현
    for i, length in enumerate((16, 23, 13)):
        yy = y - 16 + i * 16
        d.line((x + 58, yy, x + 58 + length, yy), fill="#ADC6EA", width=4)


def draw_book_hero(bg):
    """책 캐릭터 전체를 캐릭터 구역 안에 표시한다. 가짜 팔다리를 덧그리지 않는다."""
    d = ImageDraw.Draw(bg)
    center_x = 185
    d.ellipse((100, 563, 272, 581), fill="#17365C")
    sprite = load_sprite(HERO_PATH, 237, 292)
    if sprite is not None:
        # x 54~313 / y 209~669 보호 영역에 모두 들어오도록 배치
        left = center_x - sprite.width // 2
        top = 559 - sprite.height
        bg.alpha_composite(sprite, (left, top))
    else:
        d.rounded_rectangle((120, 337, 249, 559), radius=25, fill="white", outline="#1684CF", width=7)
        d.ellipse((156, 423, 167, 434), fill="#243E65")
        d.ellipse((201, 423, 212, 434), fill="#243E65")
    d.rounded_rectangle((68, 585, 302, 635), radius=18, fill="#FFF1B3", outline="#F6C75A", width=3)
    d.text((99, 592), "책의 수호자", font=font(29, True), fill="#344563")


def draw_board(game):
    """그림 속 규칙과 실제 충돌 판정이 일치하는 게임 보드."""
    im = Image.new("RGBA", (BOARD_W, BOARD_H), "#19335B")
    d = ImageDraw.Draw(im)
    # 배경: 밝고 선명한 남색 그라데이션
    for y in range(BOARD_H):
        r = int(21 + 19 * y / BOARD_H)
        g = int(44 + 17 * y / BOARD_H)
        b = int(86 + 14 * y / BOARD_H)
        d.line((0, y, BOARD_W, y), fill=(r, g, b, 255))
    pill(d, (17, 17, 1383, 742), None, "#6A86B4", 3, 28)
    # 조명·책장의 은은한 장식
    for bx in (35, 1295):
        pill(d, (bx, 194, bx + 70, 670), "#263B60", "#54749B", radius=12)
        for row in range(6):
            for j in range(4):
                x = bx + 9 + j * 14
                by = 225 + row * 70
                clr = ("#DDBF85", "#72A8BA", "#C594A9", "#91BD9E")[(j + row) % 4]
                d.rectangle((x, by, x + 11, by + 38), fill=clr)
            d.line((bx + 6, by + 43, bx + 64, by + 43), fill="#B58B69", width=6)
    # 헤더
    d.text((56, 42), "BOOK  VS  SHORTS", font=font(54, True), fill="#FFFBF1")
    d.text((59, 115), "책의 반격! 다가오는 숏폼을 막아 독서 공간을 지켜요", font=font(28), fill="#C8DFFF")
    pill(d, (905, 39, 1342, 115), "#F2F8FF", radius=24)
    d.text((930, 56), "숏폼 이동 방향   ← ← ←", font=font(26, True), fill="#24416D")
    # 방어 공간 표시
    pill(d, (54, 209, 313, 669), "#24456E", "#5C85B6", radius=32)
    draw_book_hero(im)
    d = ImageDraw.Draw(im)
    # 최종 도착 지점: 실제 충돌 위치
    d.line((DEFENSE_X, 224, DEFENSE_X, 670), fill="#FFCE55", width=12)
    for y in (228, 332, 436, 540, 640):
        d.ellipse((DEFENSE_X - 15, y - 15, DEFENSE_X + 15, y + 15), fill="#FFF3A7")
    pill(d, (53, 683, 519, 734), "#FFF0BE", "#EDCD64", radius=20)
    d.text((78, 693), "여기 도착하면 집중력 -1", font=font(25, True), fill="#6C3A47")
    # 세 통로와 각각의 접근 방향
    for lane, y in enumerate(LANE_Y):
        pill(d, (411, y - 53, 1290, y + 53), "#294C7A", "#7197CB", 3, 28)
        d.ellipse((426, y - 32, 490, y + 32), fill="#C5E9FF")
        d.text((446, y - 25), str(lane + 1), font=font(36, True), fill="#244879")
        for x in range(562, 1220, 96):
            d.line((x + 24, y, x - 15, y), fill="#7FA6D3", width=5)
            d.polygon(((x - 23, y), (x - 8, y - 10), (x - 8, y + 10)), fill="#7FA6D3")
        enemy = game["enemies"][lane]
        enemy_x = 410 + enemy["distance"] * 135
        draw_enemy(im, enemy_x, y, enemy["color"])
        d = ImageDraw.Draw(im)
        if enemy["distance"] == 1:
            pill(d, (enemy_x - 51, y - 57, enemy_x + 51, y + 53), None, "#FFBD68", 5, 19)
            d.text((enemy_x - 43, y - 88), "위험!", font=font(23, True), fill="#FFDD98")
    # 공격 효과. 이전에 맞힌 적의 위치에만 표시
    if game["last_hit"] is not None:
        lane, dist = game["last_hit"]
        hit_x = 410 + dist * 135
        y = LANE_Y[lane]
        d.line((DEFENSE_X + 7, y, hit_x - 58, y), fill="#FFE06B", width=10)
        d.polygon(((hit_x - 60, y), (hit_x - 81, y - 16), (hit_x - 81, y + 16)), fill="#FFF8C7")
        pill(d, (hit_x - 33, y - 78, hit_x + 47, y - 44), "#FFF4B2", radius=12)
        d.text((hit_x - 20, y - 74), "HIT!", font=font(23, True), fill="#B65F4C")
    return im.convert("RGB")


def show_sidebar():
    with st.sidebar:
        st.title("📚 책모아")
        st.markdown("#### 이동하기")
        st.page_link("main.py", label="🏠 도서관", use_container_width=True)
        for path, label in (
            ("pages/0_나의_서재.py", "📚 나의 서재"),
            ("pages/1_독서_집중실.py", "⏱️ 독서 집중실"),
            ("pages/2_숏폼_브레이커.py", "🎮 숏폼 브레이커"),
        ):
            if (ROOT / path).is_file():
                st.page_link(path, label=label, use_container_width=True)
        st.divider()
        st.markdown("#### 👤 내 계정")
        if st.session_state.get("bm_user_id") is not None:
            user = st.session_state.get("bm_username") or "사용자"
            st.success(f"{user}님 로그인 중")
        else:
            st.info("도서관에서 로그인할 수 있습니다.")


def main():
    show_sidebar()
    if ("shortform_game" not in st.session_state
            or not isinstance(st.session_state.shortform_game, dict)
            or "focus" not in st.session_state.shortform_game):
        # 기존 PAGE 1의 lives 키를 쓰던 게임 상태는 새 규칙으로 초기화
        st.session_state.shortform_game = new_game()
    game = st.session_state.shortform_game
    st.title("📖 숏폼 브레이커 | 책의 반격")
    st.caption("책은 왼쪽 독서 공간을 지키고, 숏폼은 오른쪽에서 왼쪽으로 다가옵니다.")
    a, b, c = st.columns(3)
    a.metric("🛡️ 막아낸 숏폼", f"{game['score']} / {GOAL}")
    b.metric("❤️ 독서 집중력", f"{game['focus']} / {MAX_FOCUS}")
    c.metric("🎮 진행 턴", str(game["turn"]))
    st.progress(min(game["score"] / GOAL, 1.0))
    st.image(draw_board(game), use_container_width=True)
    if game["status"] == "ready":
        st.info("📌 게임 방법: 오른쪽에서 출발하는 숏폼 악마가 매 턴 왼쪽으로 이동합니다. 1·2·3번 통로 중 하나를 공격하세요. "
                "숏폼 12개를 막으면 승리, 왼쪽 노란 방어선에 숏폼이 3번 닿으면 패배합니다.")
        if st.button("▶ 게임 시작", type="primary", use_container_width=True):
            start_game(game)
            st.rerun()
    elif game["status"] == "playing":
        st.info(game["message"])
        st.markdown("**어느 통로에 책장 공격을 할까요?**")
        cols = st.columns(3)
        for lane, col in enumerate(cols):
            if col.button(f"📖 {lane+1}번 통로 공격", key=f"bm_sf_hit_{lane}", use_container_width=True):
                attack(game, lane)
                st.rerun()
        st.caption("한 번 공격할 때 다른 두 통로의 숏폼만 한 칸씩 왼쪽으로 이동합니다. 실시간으로 자동 이동하지 않습니다.")
    elif game["status"] == "won":
        st.success("🏆 " + game["message"])
    else:
        st.error("💔 " + game["message"])
    if game["status"] != "ready":
        if st.button("↻ 처음부터 다시 시작", use_container_width=True):
            start_game(game)
            st.rerun()


if __name__ == "__main__":
    main()
