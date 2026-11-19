"""책모아 PAGE 2 · 독서 집중실 (스톱워치 + 집중 사운드).

필수: Streamlit 지원 버전 (st.fragment, st.audio(loop=True))
음원: 최상위 white_noise.ogg / singing_bowl.ogg / rain.ogg

스톱워치 기록은 현재 브라우저 Streamlit 세션에만 유지됩니다.
"""
from __future__ import annotations

import time
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="책모아 | 독서 집중실",
    page_icon="⏱️",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent.parent
SOUNDS = {
    "🌫️ 부드러운 백색소음": ("white_noise.ogg", "직접 생성한 낮은 볼륨의 부드러운 노이즈"),
    "🔔 저음 싱잉볼": ("singing_bowl.ogg", "CC0 원본을 0.85배속·반복 편집한 소리"),
    "🌧️ 잔잔한 빗소리": ("rain.ogg", "CC0 빗소리를 반복 재생용으로 압축한 소리"),
}


def show_sidebar():
    with st.sidebar:
        st.title("📚 책모아")
        st.markdown("#### 페이지 이동")
        st.page_link("main.py", label="🏠 MAIN · 도서관", use_container_width=True)
        page1 = ROOT / "pages" / "1_숏폼_브레이커.py"
        if page1.exists():
            st.page_link("pages/1_숏폼_브레이커.py", label="🎮 PAGE 1 · 숏폼 브레이커", use_container_width=True)
        st.page_link(f"pages/{Path(__file__).name}", label="⏱️ PAGE 2 · 독서 집중실", use_container_width=True)
        st.divider()
        st.markdown("#### 👤 내 독서 기록")
        user_id = st.session_state.get("bm_user_id")
        if user_id is not None:
            st.success(f"{st.session_state.get('bm_username') or '사용자'}님 로그인 중")
            st.caption("독서 기록은 MAIN 도서관에서 확인할 수 있습니다.")
        else:
            st.info("MAIN 도서관에서 로그인할 수 있습니다.")


def init_timer():
    st.session_state.setdefault("bm_focus_elapsed", 0.0)
    st.session_state.setdefault("bm_focus_started_at", None)
    st.session_state.setdefault("bm_focus_running", False)


def elapsed_seconds():
    elapsed = float(st.session_state.bm_focus_elapsed)
    if st.session_state.bm_focus_running:
        started = st.session_state.bm_focus_started_at
        if started is not None:
            elapsed += max(0.0, time.monotonic() - started)
    return elapsed


def display_duration(seconds):
    total = max(0, int(seconds))
    hours, rest = divmod(total, 3600)
    minutes, sec = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{sec:02d}"


@st.fragment(run_every="1s")
def stopwatch():
    """시계만 재실행해 오디오 플레이어가 매초 다시 만들어지지 않도록 한다."""
    running = bool(st.session_state.bm_focus_running)
    st.markdown("#### ⏱️ 독서 스톱워치")
    st.markdown(
        f"<div style='text-align:center;font-size:clamp(48px,8vw,88px);"
        f"font-weight:750;letter-spacing:2px;padding:18px 0'>"
        f"{display_duration(elapsed_seconds())}</div>",
        unsafe_allow_html=True,
    )
    left, middle, right = st.columns(3)

    with left:
        if st.button("▶ 시작 / 재개" if not running else "▶ 측정 중", 
                     disabled=running, use_container_width=True, type="primary"):
            st.session_state.bm_focus_started_at = time.monotonic()
            st.session_state.bm_focus_running = True
            st.rerun(scope="fragment")

    with middle:
        if st.button("⏸ 일시정지", disabled=not running, use_container_width=True):
            st.session_state.bm_focus_elapsed = elapsed_seconds()
            st.session_state.bm_focus_started_at = None
            st.session_state.bm_focus_running = False
            st.rerun(scope="fragment")

    with right:
        if st.button("↻ 초기화", use_container_width=True):
            st.session_state.bm_focus_elapsed = 0.0
            st.session_state.bm_focus_started_at = None
            st.session_state.bm_focus_running = False
            st.rerun(scope="fragment")

    st.caption("독서 시간은 3시간이 넘어도 계속 증가합니다. 브라우저를 새로 열거나 앱 세션이 종료되면 기록이 초기화될 수 있습니다.")


def focus_sound_player():
    st.markdown("#### 🎧 집중 사운드")
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
        st.audio(filepath, format="audio/ogg", loop=True, autoplay=False)
        st.success("재생 버튼을 누르면 무한 반복됩니다. 음량과 일시정지는 플레이어에서 조절하세요.")
        st.caption("현재 사운드를 바꾸거나 다른 페이지로 이동하면 재생이 중단·재시작될 수 있습니다.")
    else:
        st.warning(f"아직 음원 파일이 없습니다: `{filename}`")
        if filename == "singing_bowl.ogg":
            st.markdown("[싱잉볼 원본 다운로드 페이지](https://freesound.org/people/Rimych/sounds/616335/)")
        elif filename == "rain.ogg":
            st.markdown("[빗소리 원본 다운로드 페이지](https://freesound.org/people/myLoop/sounds/849800/)")
        else:
            st.info("압축파일에 포함된 `white_noise.ogg`를 GitHub 최상위에 올리세요.")


def main():
    show_sidebar()
    init_timer()
    st.title("📖 독서 집중실")
    st.caption("독서 시간을 측정하고, 편안한 집중 사운드를 이어서 들어 보세요.")
    st.info("① 스톱워치 시작  →  ② 사운드 선택·재생  →  ③ 독서 마치면 일시정지")
    stopwatch()
    st.divider()
    focus_sound_player()
    st.divider()
    st.caption("음원: 싱잉볼 Rimych(CC0) · 빗소리 myLoop(CC0) · 노이즈 직접 생성. 음원 및 편집 정보는 README를 확인하세요.")


if __name__ == "__main__":
    main()
