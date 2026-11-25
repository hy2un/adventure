"""북플래닛 | 독서 집중실.

독서 스톱워치와 집중 사운드 3종.
음원은 GitHub 최상위 폴더에 배치합니다.

white_noise.ogg
singing_bowl.ogg
rain.ogg
"""
from __future__ import annotations

import time
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="북플래닛 | 독서 집중실",
    page_icon="⏱️",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent.parent

SOUNDS = {
    "🌫️ 부드러운 백색소음": (
        "white_noise.ogg",
        "직접 생성한 부드러운 노이즈"
    ),
    "🔔 저음 싱잉볼": (
        "singing_bowl.ogg",
        "WAV 원본을 0.85배속으로 편집한 소리"
    ),
    "🌧️ 잔잔한 빗소리": (
        "rain.ogg",
        "WAV 원본을 OGG로 변환한 빗소리"
    ),
}


def show_sidebar():
    with st.sidebar:
        st.title("🪐 북플래닛")

        links = [
            (
                "main.py",
                "📖 도서 활동"
            ),
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

        if st.session_state.get(
            "bm_user_id"
        ) is not None:
            username = (
                st.session_state.get("bm_username")
                or "사용자"
            )
            st.success(
                f"{username}님 로그인 중"
            )

        else:
            st.info(
                "도서 활동에서 로그인할 수 있습니다."
            )


def init_timer():
    st.session_state.setdefault(
        "bm_focus_elapsed",
        0.0
    )

    st.session_state.setdefault(
        "bm_focus_started_at",
        None
    )

    st.session_state.setdefault(
        "bm_focus_running",
        False
    )


def elapsed_seconds():
    elapsed = float(
        st.session_state.bm_focus_elapsed
    )

    if st.session_state.bm_focus_running:
        started = (
            st.session_state.bm_focus_started_at
        )

        if started is not None:
            elapsed += max(
                0.0,
                time.monotonic() - started
            )

    return elapsed


def display_duration(seconds):
    total = max(
        0,
        int(seconds)
    )

    hours, rest = divmod(
        total,
        3600
    )

    minutes, sec = divmod(
        rest,
        60
    )

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{sec:02d}"
    )


@st.fragment(run_every="1s")
def stopwatch():
    running = bool(
        st.session_state.bm_focus_running
    )

    st.markdown(
        "#### ⏱️ 독서 스톱워치"
    )

    st.markdown(
        "<div style='text-align:center;"
        "font-size:clamp(48px,8vw,88px);"
        "font-weight:750;"
        "letter-spacing:2px;"
        "padding:18px 0'>"
        f"{display_duration(elapsed_seconds())}"
        "</div>",
        unsafe_allow_html=True,
    )

    left, middle, right = st.columns(3)

    with left:
        if st.button(
            "▶ 시작 / 재개"
            if not running
            else "▶ 측정 중",
            disabled=running,
            use_container_width=True,
            type="primary",
        ):
            st.session_state.bm_focus_started_at = (
                time.monotonic()
            )

            st.session_state.bm_focus_running = True

            st.rerun(
                scope="fragment"
            )

    with middle:
        if st.button(
            "⏸ 일시정지",
            disabled=not running,
            use_container_width=True,
        ):
            st.session_state.bm_focus_elapsed = (
                elapsed_seconds()
            )

            st.session_state.bm_focus_started_at = None
            st.session_state.bm_focus_running = False

            st.rerun(
                scope="fragment"
            )

    with right:
        if st.button(
            "↻ 초기화",
            use_container_width=True,
        ):
            st.session_state.bm_focus_elapsed = 0.0
            st.session_state.bm_focus_started_at = None
            st.session_state.bm_focus_running = False

            st.rerun(
                scope="fragment"
            )

    st.caption(
        "독서 시간이 3시간을 넘어도 "
        "계속 측정합니다. "
        "브라우저 세션이 종료되면 "
        "기록이 초기화될 수 있습니다."
    )


def focus_sound_player():
    st.markdown(
        "#### 🎧 집중 사운드"
    )

    selected = st.radio(
        "듣고 싶은 소리",
        list(SOUNDS.keys()),
        horizontal=True,
        key="bm_focus_sound_choice",
    )

    filename, description = SOUNDS[selected]

    st.caption(description)

    filepath = ROOT / filename

    if filepath.is_file():
        st.audio(
            filepath,
            format="audio/ogg",
            loop=True,
            autoplay=False,
        )

        st.success(
            "재생 버튼을 누르면 반복 재생됩니다. "
            "음량과 일시정지는 "
            "플레이어에서 조절하세요."
        )

        st.caption(
            "소리를 바꾸거나 다른 페이지로 이동하면 "
            "재생이 중단되거나 처음부터 시작할 수 있습니다."
        )

    else:
        st.warning(
            f"아직 음원 파일이 없습니다: `{filename}`"
        )

        st.info(
            "해당 OGG 파일을 GitHub 저장소 "
            "최상위 폴더에 업로드해 주세요."
        )


def main():
    show_sidebar()
    init_timer()

    st.title(
        "📖 독서 집중실"
    )

    st.caption(
        "독서 시간을 측정하고, "
        "집중 사운드와 함께 책을 읽어 보세요."
    )

    st.info(
        "① 스톱워치 시작 → "
        "② 사운드 선택·재생 → "
        "③ 독서를 마치면 일시정지"
    )

    stopwatch()

    st.divider()

    focus_sound_player()

    st.divider()

    st.caption(
        "집중 사운드: 백색소음 · 싱잉볼 · 빗소리"
    )


if __name__ == "__main__":
    main()
