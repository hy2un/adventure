from __future__ import annotations

import time
import wave
import io
from pathlib import Path

import numpy as np
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
        "부드러운 백색소음"
    ),
    "🔔 저음 싱잉볼": (
        "singing_bowl_original.wav",
        "0.85배속으로 재생하는 저음 싱잉볼"
    ),
    "🌧️ 잔잔한 빗소리": (
        "rain.wav",
        "잔잔하게 내리는 빗소리"
    ),
}


# 사이드바
def show_sidebar():
    with st.sidebar:
        st.title("🪐 북플래닛")

        links = [
            ("main.py", "📖 도서 활동"),
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

        if st.session_state.get("bm_user_id") is not None:
            username = (
                st.session_state.get("bm_username")
                or "사용자"
            )
            st.success(f"{username}님 로그인 중")
        else:
            st.info(
                "도서 활동에서 로그인할 수 있습니다."
            )


# 스톱워치 초기화
def init_timer():
    st.session_state.setdefault(
        "bm_focus_elapsed", 0.0
    )
    st.session_state.setdefault(
        "bm_focus_started_at", None
    )
    st.session_state.setdefault(
        "bm_focus_running", False
    )


# 독서 시간 계산
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
    total = max(0, int(seconds))
    hours, rest = divmod(total, 3600)
    minutes, sec = divmod(rest, 60)

    return f"{hours:02d}:{minutes:02d}:{sec:02d}"


# 스톱워치 영역만 1초마다 갱신
@st.fragment(run_every="1s")
def stopwatch():
    running = st.session_state.bm_focus_running

    st.markdown("#### ⏱️ 독서 스톱워치")

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
            "▶ 시작 / 재개" if not running else "▶ 측정 중",
            disabled=running,
            use_container_width=True,
            type="primary",
        ):
            st.session_state.bm_focus_started_at = (
                time.monotonic()
            )
            st.session_state.bm_focus_running = True
            st.rerun(scope="fragment")

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
            st.rerun(scope="fragment")

    with right:
        if st.button(
            "↻ 초기화",
            use_container_width=True,
        ):
            st.session_state.bm_focus_elapsed = 0.0
            st.session_state.bm_focus_started_at = None
            st.session_state.bm_focus_running = False
            st.rerun(scope="fragment")

    st.caption(
        "5시간 이상 독서 시간을 측정할 수 있습니다. "
        "브라우저 세션 종료 시 기록이 초기화될 수 있습니다."
    )


# WAV 음원 최적화 및 음량 증폭
# 처리한 음원은 캐시에 저장하여 재사용
@st.cache_data(show_spinner=False)
def prepare_wav(
    filename,
    modified,
    speed=1.0,
    target_rms=0.15,
    max_gain=5.0,
):

    with wave.open(filename, "rb") as wav:
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        rate = wav.getframerate()
        raw = wav.readframes(wav.getnframes())

    # WAV 데이터를 실수형으로 변환
    if width == 1:
        data = (
            np.frombuffer(raw, dtype=np.uint8)
            .astype(np.float32) - 128
        ) / 128

    elif width == 2:
        data = (
            np.frombuffer(raw, dtype="<i2")
            .astype(np.float32) / 32768
        )

    elif width == 3:
        b = np.frombuffer(
            raw, dtype=np.uint8
        ).reshape(-1, 3).astype(np.int32)

        values = (
            b[:, 0]
            | (b[:, 1] << 8)
            | (b[:, 2] << 16)
        )

        values = (
            values ^ 0x800000
        ) - 0x800000

        data = values.astype(np.float32) / 8388608

    elif width == 4:
        data = (
            np.frombuffer(raw, dtype="<i4")
            .astype(np.float32) / 2147483648
        )

    else:
        raise ValueError("지원하지 않는 WAV 형식입니다.")

    if data.size == 0:
        raise ValueError("비어 있는 음원입니다.")

    data = data.reshape(-1, channels)

    # 재생 데이터 경량화
    new_rate = min(rate, 24000)

    if new_rate != rate:
        old_length = len(data)
        new_length = max(
            1,
            round(old_length * new_rate / rate)
        )

        old_positions = np.arange(old_length)
        new_positions = (
            np.arange(new_length) * rate / new_rate
        )

        data = np.column_stack([
            np.interp(
                new_positions,
                old_positions,
                data[:, channel]
            )
            for channel in range(channels)
        ]).astype(np.float32)

    # 원본 음량에 따라 자동 증폭
    rms = float(np.sqrt(np.mean(data ** 2)))

    if rms > 0.000001:
        gain = min(
            max_gain,
            max(1.0, target_rms / rms)
        )
        data *= gain

    # 지나치게 큰 신호의 왜곡 방지
    magnitude = np.abs(data)

    data = np.sign(data) * np.where(
        magnitude > 0.75,
        0.75 + 0.20 * np.tanh(
            (magnitude - 0.75) / 0.20
        ),
        magnitude
    )

    # 16비트 WAV 생성
    samples = (
        np.clip(data, -1, 1) * 32767
    ).astype("<i2")

    output = io.BytesIO()

    with wave.open(output, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)

        # 샘플링 주파수를 조절하여
        # 싱잉볼 재생 속도와 음높이 변경
        wav.setframerate(
            round(new_rate * speed)
        )

        wav.writeframes(samples.tobytes())

    return output.getvalue()


# 집중 사운드 선택 및 재생
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

    if not filepath.is_file():
        st.warning(
            f"아직 음원 파일이 없습니다: {filename}"
        )
        return

    # 백색소음은 원본 그대로 재생
    if filename == "white_noise.ogg":
        st.audio(
            filepath,
            format="audio/ogg",
            loop=True,
            autoplay=False,
        )

    else:
        try:
            if filename == "singing_bowl_original.wav":

                # 싱잉볼 음량 증폭 및 0.85배속
                audio = prepare_wav(
                    str(filepath),
                    filepath.stat().st_mtime,
                    speed=0.85,
                    target_rms=0.15,
                    max_gain=5.0,
                )

            else:

                # 빗소리 음량 증폭
                audio = prepare_wav(
                    str(filepath),
                    filepath.stat().st_mtime,
                    speed=1.0,
                    target_rms=0.17,
                    max_gain=5.0,
                )

            st.audio(
                audio,
                format="audio/wav",
                loop=True,
                autoplay=False,
            )

        except Exception:
            st.warning(
                "음원 최적화에 실패하여 원본을 재생합니다."
            )

            st.audio(
                filepath,
                format="audio/wav",
                loop=True,
                autoplay=False,
            )

    st.success(
        "재생 버튼을 누르면 음원이 반복 재생됩니다."
    )

    st.caption(
        "음량과 일시정지는 플레이어에서 조절하세요. "
        "다른 페이지로 이동하면 재생이 중단될 수 있습니다."
    )


# 메인 화면
def main():
    show_sidebar()
    init_timer()

    st.title("📖 독서 집중실")

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
