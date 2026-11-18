"""책모아 PAGE 1 - 숏폼 브레이커.

책이 3개 통로로 다가오는 숏폼을 페이지 공격으로 막는 게임.
기존 게임 기능을 유지하면서 메인과 같은 사이드바를 추가함.
"""

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TARGET = 12
MAX_LIVES = 3
LANES = 3

WIDTH, HEIGHT = 1160, 495

FONT_PATHS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
]


# ---------------------------------------
# 1. 기본 함수
# ---------------------------------------

def font(size):
    """한글 글꼴을 찾는다."""
    for path in FONT_PATHS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def new_enemy():
    """새로운 숏폼 적을 생성한다."""
    return {
        "distance": random.randint(4, 6),
        "color": random.choice(["red", "pink"]),
    }


def new_game():
    """게임 초기 상태를 만든다."""
    return {
        "status": "ready",
        "score": 0,
        "lives": MAX_LIVES,
        "turn": 0,
        "enemies": [
            new_enemy()
            for _ in range(LANES)
        ],
        "last_lane": None,
        "last_hit_distance": None,
        "message": (
            "책이 주인공! "
            "다가오는 숏폼을 막아 주세요."
        ),
    }


def start_game(game):
    """게임을 시작하거나 다시 시작한다."""
    game.update(new_game())

    game["status"] = "playing"

    game["message"] = (
        "가장 가까이 다가온 "
        "숏폼부터 막아 보세요!"
    )


# ---------------------------------------
# 2. 공격 및 승패 처리
# ---------------------------------------

def attack(game, lane):
    """선택한 통로를 공격하고 나머지 적을 전진시킨다."""

    if (
        game["status"] != "playing"
        or not 0 <= lane < LANES
    ):
        return

    game["turn"] += 1

    game["last_lane"] = lane

    game["last_hit_distance"] = (
        game["enemies"][lane]["distance"]
    )

    game["score"] += 1

    game["message"] = (
        f"{lane + 1}번 통로에 "
        "책장 공격 성공!"
    )

    # 목표 달성
    if game["score"] >= TARGET:
        game["status"] = "won"

        game["message"] = (
            "승리! 책이 숏폼을 물리치고 "
            "독서 시간을 지켰습니다."
        )
        return

    # 공격한 통로에 새로운 숏폼 등장
    game["enemies"][lane] = new_enemy()

    # 나머지 통로의 숏폼 접근
    for i, enemy in enumerate(game["enemies"]):
        if i == lane:
            continue

        enemy["distance"] -= 1

        # 숏폼이 책에 도착한 경우
        if enemy["distance"] <= 0:
            game["lives"] -= 1

            game["enemies"][i] = new_enemy()

            game["message"] = (
                "숏폼 하나가 도착했습니다! "
                "집중력이 1 감소했어요."
            )

    # 패배 판정
    if game["lives"] <= 0:
        game["status"] = "lost"

        game["message"] = (
            "집중력이 모두 소진됐습니다. "
            "다시 도전해 보세요!"
        )


# ---------------------------------------
# 3. 책 캐릭터 그리기
# ---------------------------------------

def draw_book(draw, x, y):
    """책 주인공을 Pillow로 그린다."""

    # 팔
    draw.line(
        [
            (x - 29, y + 59),
            (x - 44, y + 83)
        ],
        fill="#F5CF92",
        width=11
    )

    draw.line(
        [
            (x + 37, y + 59),
            (x + 51, y + 82)
        ],
        fill="#F5CF92",
        width=11
    )

    # 다리
    draw.line(
        [
            (x - 12, y + 98),
            (x - 19, y + 123)
        ],
        fill="#F5CF92",
        width=12
    )

    draw.line(
        [
            (x + 20, y + 98),
            (x + 27, y + 123)
        ],
        fill="#F5CF92",
        width=12
    )

    # 책 표지
    draw.rounded_rectangle(
        (
            x - 58,
            y - 20,
            x + 59,
            y + 102
        ),
        radius=12,
        fill="#236A9C",
        outline="#A6DFF6",
        width=4
    )

    # 왼쪽 책장
    draw.polygon(
        [
            (x, y - 7),
            (x - 43, y - 17),
            (x - 43, y + 84),
            (x, y + 96)
        ],
        fill="#F4E7C9"
    )

    # 오른쪽 책장
    draw.polygon(
        [
            (x, y - 7),
            (x + 43, y - 17),
            (x + 43, y + 84),
            (x, y + 96)
        ],
        fill="#FFFAEC"
    )

    # 책 가운데 접힌 선
    draw.line(
        [
            (x, y - 6),
            (x, y + 92)
        ],
        fill="#D0BDA1",
        width=3
    )

    # 글자 모양 장식
    for j in range(3):
        draw.line(
            [
                (x - 34, y + 15 + j * 13),
                (x - 10, y + 18 + j * 13)
            ],
            fill="#BDAA8D",
            width=2
        )

        draw.line(
            [
                (x + 10, y + 18 + j * 13),
                (x + 34, y + 15 + j * 13)
            ],
            fill="#BDAA8D",
            width=2
        )

    # 눈
    draw.ellipse(
        (
            x - 20,
            y + 48,
            x - 13,
            y + 55
        ),
        fill="#274458"
    )

    draw.ellipse(
        (
            x + 13,
            y + 48,
            x + 20,
            y + 55
        ),
        fill="#274458"
    )

    # 웃는 입
    draw.arc(
        (
            x - 13,
            y + 53,
            x + 13,
            y + 73
        ),
        10,
        165,
        fill="#274458",
        width=3
    )


# ---------------------------------------
# 4. 숏폼 아이콘 그리기
# ---------------------------------------

def draw_enemy(draw, x, y, color):
    """숏폼 재생 아이콘을 그린다."""

    if color == "red":
        fill = "#E55074"
    else:
        fill = "#A25CE3"

    draw.rounded_rectangle(
        (
            x - 41,
            y - 39,
            x + 41,
            y + 39
        ),
        radius=18,
        fill=fill,
        outline="#FFD9E5",
        width=3
    )

    # 재생 삼각형
    draw.polygon(
        [
            (x - 10, y - 19),
            (x - 10, y + 19),
            (x + 19, y)
        ],
        fill="#FFFFFF"
    )


# ---------------------------------------
# 5. 게임 화면 그리기
# ---------------------------------------

def render_board(game):
    """게임 보드를 PNG 이미지처럼 그린다."""

    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        "#17263A"
    )

    draw = ImageDraw.Draw(image)

    # 배경 그라데이션
    for y in range(HEIGHT):
        r = int(20 + 17 * y / HEIGHT)
        g = int(36 + 11 * y / HEIGHT)
        b = int(57 + 8 * y / HEIGHT)

        draw.line(
            [
                (0, y),
                (WIDTH, y)
            ],
            fill=(r, g, b)
        )

    # 게임 화면 테두리
    draw.rounded_rectangle(
        (
            16,
            15,
            WIDTH - 16,
            HEIGHT - 14
        ),
        radius=25,
        outline="#52627B",
        width=2
    )

    # 도서관 장식
    for bx in (25, 72, 1065, 1111):
        for row in range(5):
            for j in range(3):
                xx = bx + j * 13
                yy = 62 + row * 75

                colors = [
                    "#9A7554",
                    "#466E8F",
                    "#729283"
                ]

                draw.rectangle(
                    (
                        xx,
                        yy,
                        xx + 8,
                        yy + 42
                    ),
                    fill=colors[(row + j) % 3]
                )

    # 게임 제목
    draw.text(
        (88, 27),
        "BOOK  VS  SHORTS",
        font=font(34),
        fill="#FAF6E9"
    )

    draw.text(
        (91, 74),
        "책의 반격 — 숏폼이 도착하기 전에 막아라!",
        font=font(20),
        fill="#A8BBD1"
    )

    # 3개의 통로
    ys = [184, 296, 408]

    for lane, y in enumerate(ys):
        draw.rounded_rectangle(
            (
                255,
                y - 42,
                990,
                y + 42
            ),
            radius=16,
            fill="#27384D",
            outline="#3E5773",
            width=2
        )

        # 통로 점 장식
        for x in (
            330,
            440,
            550,
            660,
            770,
            880
        ):
            draw.ellipse(
                (
                    x - 3,
                    y - 3,
                    x + 3,
                    y + 3
                ),
                fill="#64788E"
            )

        # 통로 번호
        draw.text(
            (282, y - 18),
            str(lane + 1),
            font=font(26),
            fill="#DFEAF8"
        )

        enemy = game["enemies"][lane]

        x = (
            300
            + 100 * enemy["distance"]
        )

        draw_enemy(
            draw,
            x,
            y,
            enemy["color"]
        )

        # 공격 효과
        if game["last_lane"] == lane:
            hit_x = (
                300
                + 100 * game["last_hit_distance"]
            )

            draw.line(
                [
                    (223, y),
                    (hit_x - 65, y)
                ],
                fill="#FFD76A",
                width=7
            )

            draw.polygon(
                [
                    (hit_x - 56, y - 14),
                    (hit_x - 29, y),
                    (hit_x - 56, y + 14)
                ],
                fill="#FFD76A"
            )

    # 책 캐릭터
    draw_book(
        draw,
        166,
        247
    )

    draw.text(
        (107, 385),
        "책의 수호자",
        font=font(23),
        fill="#F5E7C7"
    )

    draw.text(
        (1030, 453),
        "BOOKMOA",
        font=font(16),
        fill="#A8B9CB"
    )

    return image


# ---------------------------------------
# 6. Streamlit PAGE 1
# ---------------------------------------

def show_page():
    import streamlit as st

    st.set_page_config(
        page_title="책모아 | 숏폼 브레이커",
        page_icon="📖",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # -----------------------------------
    # 6-1. 공통 사이드바
    # -----------------------------------

    with st.sidebar:
        st.title("📚 책모아")
        st.markdown("#### 페이지 이동")

        st.page_link(
            "main.py",
            label="🏠 MAIN · 도서관",
            use_container_width=True
        )

        st.page_link(
            f"pages/{Path(__file__).name}",
            label="🎮 PAGE 1 · 숏폼 브레이커",
            use_container_width=True
        )

        st.divider()
        st.markdown("#### 👤 내 독서 기록")

        if (
            st.session_state.get("bm_user_id")
            is not None
        ):
            username = (
                st.session_state.get("bm_username")
                or "사용자"
            )

            st.success(
                f"{username}님 로그인 중"
            )

            st.caption(
                "독서 기록은 MAIN 도서관에서 "
                "확인할 수 있습니다."
            )

        else:
            st.info(
                "MAIN 도서관에서 로그인하고 "
                "기록을 확인하세요."
            )

    # -----------------------------------
    # 6-2. 게임 상태 불러오기
    # -----------------------------------

    if "shortform_game" not in st.session_state:
        st.session_state.shortform_game = new_game()

    game = st.session_state.shortform_game

    # -----------------------------------
    # 6-3. 게임 화면
    # -----------------------------------

    st.title(
        "📚 숏폼 브레이커 | 책의 반격"
    )

    st.caption(
        "책이 숏폼에 맞서 싸우는 "
        "3개 통로 방어 게임 — "
        "클릭 1회가 게임 1턴입니다."
    )

    left, center, right = st.columns(3)

    left.metric(
        "📖 막아낸 숏폼",
        f"{game['score']} / {TARGET}"
    )

    center.metric(
        "❤️ 독서 집중력",
        f"{game['lives']} / {MAX_LIVES}"
    )

    right.metric(
        "🎮 진행 턴",
        game["turn"]
    )

    st.progress(
        min(game["score"] / TARGET, 1.0)
    )

    st.image(
        render_board(game),
        use_container_width=True
    )

    # -----------------------------------
    # 6-4. 게임 시작
    # -----------------------------------

    if game["status"] == "ready":
        st.info(
            "책이 세 통로로 다가오는 숏폼을 "
            "페이지 공격으로 막습니다. "
            "먼저 가장 가까운 아이콘을 "
            "공격하세요."
        )

        if st.button(
            "▶ 게임 시작",
            type="primary",
            use_container_width=True
        ):
            start_game(game)
            st.rerun()

    # -----------------------------------
    # 6-5. 게임 진행
    # -----------------------------------

    elif game["status"] == "playing":
        st.info(game["message"])

        buttons = st.columns(3)

        for lane, col in enumerate(buttons):
            if col.button(
                f"📖 {lane + 1}번 통로 공격",
                key=f"sf_attack_{lane}",
                use_container_width=True
            ):
                attack(game, lane)
                st.rerun()

        st.caption(
            "공격한 통로의 숏폼은 사라지고, "
            "나머지 두 통로의 숏폼은 "
            "한 칸씩 책을 향해 접근합니다."
        )

    # -----------------------------------
    # 6-6. 승리
    # -----------------------------------

    elif game["status"] == "won":
        st.success(
            "🎉 책의 승리! 숏폼 12개를 막아 "
            "독서 시간을 지켰습니다."
        )

    # -----------------------------------
    # 6-7. 패배
    # -----------------------------------

    elif game["status"] == "lost":
        st.error(
            "집중력이 0이 됐습니다. "
            "공격할 통로의 순서를 바꿔 "
            "다시 도전해 보세요."
        )

    # -----------------------------------
    # 6-8. 다시 시작
    # -----------------------------------

    if game["status"] != "ready":
        if st.button(
            "↻ 다시 시작",
            use_container_width=True
        ):
            start_game(game)
            st.rerun()


# PAGE 1 실행
show_page()
