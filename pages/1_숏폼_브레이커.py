"""책모아 PAGE 1 - 숏폼 브레이커: 책의 반격."""

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

GOAL = 12
MAX_FOCUS = 3
LANES = 3
BOARD_W, BOARD_H = 1400, 760
LANE_Y = (314, 453, 592)
DEFENSE_X = 371


# ------------------------------------
# 1. 게임 데이터 및 규칙
# ------------------------------------

def new_enemy():
    """방어선까지 4~6턴 떨어진 숏폼 생성."""
    return {
        "distance": random.randint(4, 6),
        "color": random.choice(
            ("pink", "purple", "orange")
        ),
    }


def new_game():
    return {
        "status": "ready",
        "score": 0,
        "focus": MAX_FOCUS,
        "turn": 0,
        "enemies": [
            new_enemy()
            for _ in range(LANES)
        ],
        "last_hit": None,
        "message": "게임 시작 버튼을 눌러 주세요.",
    }


def start_game(game):
    game.clear()
    game.update(new_game())

    game["status"] = "playing"
    game["message"] = (
        "가장 가까이 다가온 숏폼부터 막아 보세요."
    )


def attack(game, lane):
    """선택 통로 공격 후 다른 통로의 숏폼을 전진."""

    if game["status"] != "playing":
        return

    if lane not in range(LANES):
        return

    game["turn"] += 1

    old_distance = (
        game["enemies"][lane]["distance"]
    )

    game["last_hit"] = (
        lane,
        old_distance
    )

    game["score"] += 1

    # 공격한 통로의 숏폼 제거 및 재등장
    game["enemies"][lane] = new_enemy()

    reached = 0

    # 공격하지 않은 통로의 숏폼 이동
    for index, enemy in enumerate(game["enemies"]):
        if index == lane:
            continue

        enemy["distance"] -= 1

        # 방어선에 도착했을 때
        if enemy["distance"] <= 0:
            reached += 1

            game["focus"] = max(
                0,
                game["focus"] - 1
            )

            game["enemies"][index] = new_enemy()

    # 승패 판정
    if game["focus"] == 0:
        game["status"] = "lost"
        game["message"] = (
            "숏폼이 독서 공간에 3번 도착했습니다. "
            "다시 도전해 보세요!"
        )

    elif game["score"] >= GOAL:
        game["status"] = "won"
        game["message"] = (
            "승리! 책이 숏폼 12개를 막아 "
            "독서 공간을 지켰습니다!"
        )

    elif reached:
        game["message"] = (
            f"숏폼 {reached}개가 방어선을 넘었습니다. "
            f"집중력 {game['focus']}/{MAX_FOCUS}"
        )

    else:
        game["message"] = (
            f"{lane + 1}번 통로 방어 성공! "
            "다른 통로의 숏폼이 한 칸 접근했습니다."
        )


# ------------------------------------
# 2. 글꼴과 그림 도구
# ------------------------------------

def font(size, bold=False):
    candidates = [
        (
            "/usr/share/fonts/opentype/noto/"
            "NotoSansCJK-Bold.ttc"
            if bold else
            "/usr/share/fonts/opentype/noto/"
            "NotoSansCJK-Regular.ttc"
        ),
        (
            "/usr/share/fonts/truetype/nanum/"
            "NanumGothicBold.ttf"
            if bold else
            "/usr/share/fonts/truetype/nanum/"
            "NanumGothic.ttf"
        ),
        (
            "C:/Windows/Fonts/malgunbd.ttf"
            if bold else
            "C:/Windows/Fonts/malgun.ttf"
        ),
    ]

    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def pill(draw, box, fill, outline=None,
         width=2, radius=20):
    draw.rounded_rectangle(
        box,
        radius=radius,
        fill=fill,
        outline=outline,
        width=width,
    )


def draw_phone(draw, x, y, color):
    """숏폼 아이콘을 그린다."""

    palette = {
        "pink": ("#F6467B", "#FF8DAD"),
        "purple": ("#8762F2", "#B09BFF"),
        "orange": ("#FF8B4A", "#FFD08A"),
    }

    base, glow = palette[color]

    # 그림자
    pill(
        draw,
        (x - 42, y - 43, x + 46, y + 49),
        "#162645",
        radius=18,
    )

    # 흰 테두리
    pill(
        draw,
        (x - 45, y - 49, x + 42, y + 41),
        "#FCFCFF",
        radius=18,
    )

    # 숏폼 카드
    pill(
        draw,
        (x - 39, y - 43, x + 36, y + 35),
        base,
        radius=14,
    )

    draw.ellipse(
        (x - 21, y - 34, x + 8, y - 27),
        fill=glow,
    )

    # 재생 버튼
    draw.polygon(
        (
            (x - 10, y - 20),
            (x - 10, y + 20),
            (x + 23, y),
        ),
        fill="#FFFFFF",
    )

    # 움직임 표현
    for i, length in enumerate((25, 17, 10)):
        draw.line(
            (
                x + 52,
                y - 14 + i * 14,
                x + 52 + length,
                y - 14 + i * 14,
            ),
            fill="#99B2E1",
            width=5,
        )


# ------------------------------------
# 3. 책 캐릭터
# ------------------------------------

def draw_book_hero(image):
    draw = ImageDraw.Draw(image)

    cx = 185
    bottom = 565

    # 몸통
    pill(
        draw,
        (
            cx - 56,
            bottom - 122,
            cx + 56,
            bottom - 35,
        ),
        "#67C2D3",
        radius=30,
    )

    # 다리
    draw.line(
        (
            (cx - 27, bottom - 49),
            (cx - 41, bottom - 13),
        ),
        fill="#FFBD47",
        width=22,
    )

    draw.line(
        (
            (cx + 27, bottom - 49),
            (cx + 42, bottom - 13),
        ),
        fill="#FFBD47",
        width=22,
    )

    # 신발
    pill(
        draw,
        (
            cx - 58,
            bottom - 14,
            cx - 18,
            bottom,
        ),
        "#204877",
        radius=9,
    )

    pill(
        draw,
        (
            cx + 19,
            bottom - 14,
            cx + 60,
            bottom,
        ),
        "#204877",
        radius=9,
    )

    # 팔
    draw.line(
        (
            (cx - 49, bottom - 98),
            (cx - 81, bottom - 70),
        ),
        fill="#FFBD47",
        width=22,
    )

    draw.line(
        (
            (cx + 49, bottom - 98),
            (cx + 82, bottom - 70),
        ),
        fill="#FFBD47",
        width=22,
    )

    draw.ellipse(
        (
            cx - 94,
            bottom - 84,
            cx - 66,
            bottom - 53,
        ),
        fill="#FFD069",
    )

    draw.ellipse(
        (
            cx + 67,
            bottom - 84,
            cx + 94,
            bottom - 53,
        ),
        fill="#FFD069",
    )

    # 별도로 업로드한 책 캐릭터 PNG
    if HERO_PATH.is_file():
        with Image.open(HERO_PATH) as raw:
            sprite = raw.convert("RGBA")

            sprite.thumbnail(
                (225, 185),
                Image.Resampling.LANCZOS,
            )

            image.alpha_composite(
                sprite,
                (
                    cx - sprite.width // 2,
                    bottom - 266,
                ),
            )

    else:
        # 이미지 누락 시 대체 캐릭터
        pill(
            draw,
            (
                cx - 74,
                bottom - 286,
                cx + 74,
                bottom - 116,
            ),
            "#FFFFFF",
            "#247FAD",
            6,
            20,
        )

        draw.ellipse(
            (
                cx - 31,
                bottom - 218,
                cx - 16,
                bottom - 198,
            ),
            fill="#27456C",
        )

        draw.ellipse(
            (
                cx + 15,
                bottom - 218,
                cx + 30,
                bottom - 198,
            ),
            fill="#27456C",
        )

    # 책 캐릭터 이름표
    pill(
        draw,
        (64, 577, 305, 634),
        "#FFF1B3",
        "#F6C75A",
        radius=26,
    )

    draw.text(
        (99, 589),
        "책의 수호자",
        font=font(30, True),
        fill="#344563",
    )


# ------------------------------------
# 4. 게임 보드 그리기
# ------------------------------------

def draw_board(game):
    image = Image.new(
        "RGBA",
        (BOARD_W, BOARD_H),
        "#19335B",
    )

    draw = ImageDraw.Draw(image)

    # 배경
    for y in range(BOARD_H):
        r = int(21 + 19 * y / BOARD_H)
        g = int(44 + 17 * y / BOARD_H)
        b = int(86 + 14 * y / BOARD_H)

        draw.line(
            (0, y, BOARD_W, y),
            fill=(r, g, b, 255),
        )

    pill(
        draw,
        (17, 17, 1383, 742),
        None,
        "#6A86B4",
        3,
        28,
    )

    # 양쪽 장식 책장
    for bx in (35, 1295):
        pill(
            draw,
            (bx, 194, bx + 70, 670),
            "#263B60",
            "#54749B",
            radius=12,
        )

        colors = (
            "#DDBF85",
            "#72A8BA",
            "#C594A9",
            "#91BD9E",
        )

        for row in range(6):
            for j in range(4):
                x = bx + 9 + j * 14
                by = 225 + row * 70

                draw.rectangle(
                    (
                        x,
                        by,
                        x + 11,
                        by + 38,
                    ),
                    fill=colors[(j + row) % 4],
                )

            draw.line(
                (
                    bx + 6,
                    by + 43,
                    bx + 64,
                    by + 43,
                ),
                fill="#B58B69",
                width=6,
            )

    # 제목
    draw.text(
        (56, 42),
        "BOOK  VS  SHORTS",
        font=font(54, True),
        fill="#FFFBF1",
    )

    draw.text(
        (59, 115),
        "책의 반격! 다가오는 숏폼을 막아 "
        "독서 공간을 지켜요",
        font=font(28),
        fill="#C8DFFF",
    )

    # 이동 방향
    pill(
        draw,
        (905, 39, 1342, 115),
        "#F2F8FF",
        radius=24,
    )

    draw.text(
        (930, 56),
        "숏폼 이동 방향   ← ← ←",
        font=font(26, True),
        fill="#24416D",
    )

    # 책이 지키는 공간
    pill(
        draw,
        (54, 209, 313, 669),
        "#24456E",
        "#5C85B6",
        radius=32,
    )

    draw_book_hero(image)
    draw = ImageDraw.Draw(image)

    # 방어선: 실제 실패 판정과 대응
    draw.line(
        (
            DEFENSE_X,
            224,
            DEFENSE_X,
            670,
        ),
        fill="#FFCE55",
        width=12,
    )

    for y in (228, 332, 436, 540, 640):
        draw.ellipse(
            (
                DEFENSE_X - 15,
                y - 15,
                DEFENSE_X + 15,
                y + 15,
            ),
            fill="#FFF3A7",
        )

    pill(
        draw,
        (53, 683, 519, 734),
        "#FFF0BE",
        "#EDCD64",
        radius=20,
    )

    draw.text(
        (78, 693),
        "여기 도착하면 집중력 -1",
        font=font(25, True),
        fill="#6C3A47",
    )

    # 세 개의 게임 통로
    for lane, y in enumerate(LANE_Y):
        pill(
            draw,
            (
                411,
                y - 53,
                1290,
                y + 53,
            ),
            "#294C7A",
            "#7197CB",
            3,
            28,
        )

        # 통로 번호
        draw.ellipse(
            (
                426,
                y - 32,
                490,
                y + 32,
            ),
            fill="#C5E9FF",
        )

        draw.text(
            (446, y - 25),
            str(lane + 1),
            font=font(36, True),
            fill="#244879",
        )

        # 왼쪽 방향 화살표
        for x in range(562, 1220, 96):
            draw.line(
                (
                    x + 24,
                    y,
                    x - 15,
                    y,
                ),
                fill="#7FA6D3",
                width=5,
            )

            draw.polygon(
                (
                    (x - 23, y),
                    (x - 8, y - 10),
                    (x - 8, y + 10),
                ),
                fill="#7FA6D3",
            )

        enemy = game["enemies"][lane]

        # distance가 감소하면 왼쪽으로 이동
        enemy_x = (
            410 + enemy["distance"] * 135
        )

        draw_phone(
            draw,
            enemy_x,
            y,
            enemy["color"],
        )

        # 방어선 바로 앞에 있는 숏폼
        if enemy["distance"] == 1:
            pill(
                draw,
                (
                    enemy_x - 51,
                    y - 57,
                    enemy_x + 51,
                    y + 53,
                ),
                None,
                "#FFBD68",
                5,
                19,
            )

            draw.text(
                (enemy_x - 43, y - 88),
                "위험!",
                font=font(23, True),
                fill="#FFDD98",
            )

    # 마지막 공격 표시
    if game["last_hit"] is not None:
        lane, distance = game["last_hit"]

        hit_x = 410 + distance * 135
        y = LANE_Y[lane]

        draw.line(
            (
                DEFENSE_X + 7,
                y,
                hit_x - 58,
                y,
            ),
            fill="#FFE06B",
            width=10,
        )

        draw.polygon(
            (
                (hit_x - 60, y),
                (hit_x - 81, y - 16),
                (hit_x - 81, y + 16),
            ),
            fill="#FFF8C7",
        )

        pill(
            draw,
            (
                hit_x - 33,
                y - 78,
                hit_x + 47,
                y - 44,
            ),
            "#FFF4B2",
            radius=12,
        )

        draw.text(
            (hit_x - 20, y - 74),
            "HIT!",
            font=font(23, True),
            fill="#B65F4C",
        )

    return image.convert("RGB")


# ------------------------------------
# 5. 공통 사이드바
# ------------------------------------

def show_sidebar():
    with st.sidebar:
        st.title("📚 책모아")
        st.markdown("#### 페이지 이동")

        st.page_link(
            "main.py",
            label="🏠 MAIN · 도서관",
            use_container_width=True,
        )

        st.page_link(
            f"pages/{Path(__file__).name}",
            label="🎮 PAGE 1 · 숏폼 브레이커",
            use_container_width=True,
        )

        st.divider()
        st.markdown("#### 👤 내 독서 기록")

        if (
            st.session_state.get("bm_user_id")
            is not None
        ):
            name = (
                st.session_state.get("bm_username")
                or "사용자"
            )

            st.success(
                f"{name}님 로그인 중"
            )

            st.caption(
                "독서 기록은 MAIN 도서관에서 "
                "확인할 수 있습니다."
            )

        else:
            st.info(
                "MAIN 도서관에서 로그인할 수 있습니다."
            )


# ------------------------------------
# 6. 게임 화면
# ------------------------------------

def main():
    show_sidebar()

    # 이전 게임 버전의 상태가 남아 있어도 오류 방지
    if (
        "shortform_game" not in st.session_state
        or not isinstance(
            st.session_state.shortform_game,
            dict,
        )
        or "focus"
        not in st.session_state.shortform_game
    ):
        st.session_state.shortform_game = new_game()

    game = st.session_state.shortform_game

    st.title("📖 숏폼 브레이커 | 책의 반격")

    st.caption(
        "책은 왼쪽 독서 공간을 지키고, "
        "숏폼은 오른쪽에서 왼쪽으로 다가옵니다."
    )

    a, b, c = st.columns(3)

    a.metric(
        "🛡️ 막아낸 숏폼",
        f"{game['score']} / {GOAL}",
    )

    b.metric(
        "❤️ 독서 집중력",
        f"{game['focus']} / {MAX_FOCUS}",
    )

    c.metric(
        "🎮 진행 턴",
        str(game["turn"]),
    )

    st.progress(
        min(game["score"] / GOAL, 1.0)
    )

    st.image(
        draw_board(game),
        use_container_width=True,
    )

    # 게임 시작 전
    if game["status"] == "ready":
        st.info(
            "📌 게임 방법: 오른쪽 숏폼은 "
            "매 턴 왼쪽으로 이동합니다. "
            "1·2·3번 통로 중 하나를 공격하세요. "
            "숏폼 12개를 막으면 승리, "
            "왼쪽 노란 방어선에 숏폼이 "
            "3번 닿으면 패배합니다."
        )

        if st.button(
            "▶ 게임 시작",
            type="primary",
            use_container_width=True,
        ):
            start_game(game)
            st.rerun()

    # 진행 중
    elif game["status"] == "playing":
        st.info(game["message"])

        st.markdown(
            "**어느 통로에 책장 공격을 할까요?**"
        )

        cols = st.columns(3)

        for lane, col in enumerate(cols):
            if col.button(
                f"📖 {lane + 1}번 통로 공격",
                key=f"bm_sf_hit_{lane}",
                use_container_width=True,
            ):
                attack(game, lane)
                st.rerun()

        st.caption(
            "한 번 공격할 때 다른 두 통로의 "
            "숏폼만 한 칸씩 왼쪽으로 이동합니다. "
            "실시간으로 자동 이동하지 않습니다."
        )

    # 승리
    elif game["status"] == "won":
        st.success(
            "🏆 " + game["message"]
        )

    # 패배
    else:
        st.error(
            "💔 " + game["message"]
        )

    # 재시작
    if game["status"] != "ready":
        if st.button(
            "↻ 처음부터 다시 시작",
            use_container_width=True,
        ):
            start_game(game)
            st.rerun()


if __name__ == "__main__":
    main()
