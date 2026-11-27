from __future__ import annotations

import time
import wave
import io
import base64
from pathlib import Path

import numpy as np
import streamlit as st
import streamlit.components.v1 as components

from bookplanet_db import reset_legacy_session


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
        "부드러운 백색소음",
    ),

    "🔔 저음 싱잉볼": (
        "singing_bowl_original.wav",
        "0.85배속으로 재생하는 저음 싱잉볼",
    ),

    "🌧️ 잔잔한 빗소리": (
        "rain.wav",
        "잔잔하게 내리는 빗소리",
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
                "📊 독서 성장 기록",
            ),
            (
                "pages/1_독서_집중실.py",
                "⏱️ 독서 집중실",
            ),
            (
                "pages/2_숏폼_브레이커.py",
                "🎮 숏폼 브레이커",
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
                time.monotonic() - started,
            )

    return elapsed


# 시간 표시
def display_duration(seconds):
    total = max(0, int(seconds))

    hours, rest = divmod(total, 3600)
    minutes, sec = divmod(rest, 60)

    return f"{hours:02d}:{minutes:02d}:{sec:02d}"


# 스톱워치 시작
def start_timer():
    st.session_state.bm_focus_started_at = (
        time.monotonic()
    )

    st.session_state.bm_focus_running = True


# 스톱워치 일시정지
def pause_timer():
    st.session_state.bm_focus_elapsed = (
        elapsed_seconds()
    )

    st.session_state.bm_focus_started_at = None
    st.session_state.bm_focus_running = False


# 스톱워치 초기화
def reset_timer():
    st.session_state.bm_focus_elapsed = 0.0
    st.session_state.bm_focus_started_at = None
    st.session_state.bm_focus_running = False


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
        st.button(
            "▶ 시작 / 재개"
            if not running else "▶ 측정 중",
            disabled=running,
            use_container_width=True,
            type="primary",
            on_click=start_timer,
        )

    with middle:
        st.button(
            "⏸ 일시정지",
            disabled=not running,
            use_container_width=True,
            on_click=pause_timer,
        )

    with right:
        st.button(
            "↻ 초기화",
            use_container_width=True,
            on_click=reset_timer,
        )

    st.caption(
        "5시간 이상 독서 시간을 측정할 수 있습니다. "
        "브라우저 세션 종료 시 기록이 초기화될 수 있습니다."
    )


# WAV 음원 최적화 및 캐싱
@st.cache_data(
    show_spinner=False,
    max_entries=6,
)
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

        raw = wav.readframes(
            wav.getnframes()
        )

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
            raw,
            dtype=np.uint8,
        ).reshape(-1, 3).astype(np.int32)

        values = (
            b[:, 0]
            | (b[:, 1] << 8)
            | (b[:, 2] << 16)
        )

        values = (
            values ^ 0x800000
        ) - 0x800000

        data = (
            values.astype(np.float32)
            / 8388608
        )

    elif width == 4:
        data = (
            np.frombuffer(raw, dtype="<i4")
            .astype(np.float32) / 2147483648
        )

    else:
        raise ValueError(
            "지원하지 않는 WAV 형식입니다."
        )

    if data.size == 0:
        raise ValueError("비어 있는 음원입니다.")

    data = data.reshape(-1, channels)

    # 음원 용량 최적화
    new_rate = min(rate, 24000)

    if new_rate != rate:
        old_length = len(data)

        new_length = max(
            1,
            round(
                old_length * new_rate / rate
            ),
        )

        old_positions = np.arange(old_length)

        new_positions = (
            np.arange(new_length)
            * rate / new_rate
        )

        data = np.column_stack([
            np.interp(
                new_positions,
                old_positions,
                data[:, channel],
            )
            for channel in range(channels)
        ]).astype(np.float32)

    # 음량 증폭
    rms = float(
        np.sqrt(np.mean(data ** 2))
    )

    if rms > 0.000001:
        gain = min(
            max_gain,
            max(1.0, target_rms / rms),
        )

        data *= gain

    # 과도한 음량 왜곡 완화
    magnitude = np.abs(data)

    data = np.sign(data) * np.where(
        magnitude > 0.75,
        0.75 + 0.20 * np.tanh(
            (magnitude - 0.75) / 0.20
        ),
        magnitude,
    )

    samples = (
        np.clip(data, -1, 1) * 32767
    ).astype("<i2")

    output = io.BytesIO()

    with wave.open(output, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)

        wav.setframerate(
            round(new_rate * speed)
        )

        wav.writeframes(
            samples.tobytes()
        )

    return output.getvalue()


# 음원 데이터 인코딩 및 캐싱
@st.cache_data(
    show_spinner=False,
    max_entries=6,
)
def encode_audio(audio_data):
    return base64.b64encode(
        audio_data
    ).decode("ascii")


# 누적 재생 시간 표시 전용 플레이어
def continuous_player(audio_data, audio_format):
    encoded = encode_audio(audio_data)

    audio_source = (
        f"data:{audio_format};base64,{encoded}"
    )

    player = """
    <!DOCTYPE html>
    <html lang="ko">

    <head>
        <meta charset="UTF-8">

        <style>
            * {
                box-sizing: border-box;
            }

            body {
                margin: 0;
                font-family: sans-serif;
                color: #294638;
            }

            .player {
                background: #f1f7f3;
                border: 1px solid #d7e7dc;
                border-radius: 16px;
                padding: 20px;
                text-align: center;
            }

            .repeat {
                font-size: 14px;
                font-weight: 600;
                color: #397b57;
            }

            .timer-label {
                font-size: 13px;
                color: #668173;
                margin-top: 12px;
            }

            #timer {
                font-size: 44px;
                font-weight: 750;
                margin: 8px 0;
                letter-spacing: 2px;
                font-variant-numeric: tabular-nums;
            }

            #status {
                font-size: 14px;
                color: #668173;
                min-height: 20px;
            }

            .buttons {
                margin-top: 14px;
            }

            button {
                background: #397b57;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 22px;
                margin: 4px;
                font-size: 15px;
                cursor: pointer;
                min-width: 100px;
            }

            button:hover {
                background: #2e6849;
            }

            button:disabled {
                opacity: 0.6;
                cursor: wait;
            }

            #stop {
                background: #e0ebe3;
                color: #294638;
            }

            .volume {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 12px;
                margin-top: 18px;
                font-size: 14px;
            }

            input {
                width: 55%;
                accent-color: #397b57;
                cursor: pointer;
            }

            #level {
                min-width: 45px;
            }

            .guide {
                margin-top: 14px;
                font-size: 12px;
                color: #668173;
            }

            @media (max-width: 450px) {
                #timer {
                    font-size: 34px;
                }

                button {
                    min-width: 85px;
                    padding: 10px 14px;
                }
            }
        </style>
    </head>

    <body>

        <div class="player">

            <div class="repeat">
                🔁 무한 반복 재생
            </div>

            <div class="timer-label">
                누적 재생 시간
            </div>

            <div id="timer">
                00:00:00
            </div>

            <div id="status">
                재생 대기 중
            </div>

            <div class="buttons">

                <button id="play">
                    ▶ 재생
                </button>

                <button id="stop">
                    ■ 정지
                </button>

            </div>

            <div class="volume">

                <span>🔊 음량</span>

                <input
                    id="volume"
                    type="range"
                    min="0"
                    max="100"
                    value="100"
                >

                <span id="level">
                    100%
                </span>

            </div>

            <div class="guide">
                정지할 때까지 음원이 계속 반복됩니다.
            </div>

        </div>

        <audio
            id="audio"
            preload="none"
            loop
            src="AUDIO_DATA"
        ></audio>

        <script>

            const audio =
                document.getElementById("audio");

            const timer =
                document.getElementById("timer");

            const play =
                document.getElementById("play");

            const stop =
                document.getElementById("stop");

            const status =
                document.getElementById("status");

            const volume =
                document.getElementById("volume");

            const level =
                document.getElementById("level");

            let elapsed = 0;
            let started = null;
            let stopped = true;
            let requestId = 0;

            audio.loop = true;
            audio.volume = 1.0;


            // 누적 재생 시간 저장
            function freezeTime() {

                if (started !== null) {

                    elapsed +=
                        performance.now() - started;

                    started = null;
                }
            }


            // 시간 표시
            function updateTimer() {

                let total = elapsed;

                if (started !== null) {

                    total +=
                        performance.now() - started;
                }

                const seconds =
                    Math.floor(total / 1000);

                const h =
                    Math.floor(seconds / 3600);

                const m =
                    Math.floor(seconds / 60) % 60;

                const s =
                    seconds % 60;

                timer.textContent = [h, m, s]
                    .map(
                        v => String(v).padStart(2, "0")
                    )
                    .join(":");
            }


            // 재생 및 일시정지
            play.onclick = async () => {

                if (!audio.paused) {

                    audio.pause();

                    return;
                }

                stopped = false;

                const currentRequest =
                    ++requestId;

                play.disabled = true;

                status.textContent =
                    "음원 불러오는 중";

                try {

                    await audio.play();

                } catch (error) {

                    if (
                        currentRequest === requestId
                        && !stopped
                    ) {

                        freezeTime();
                        updateTimer();

                        status.textContent =
                            "재생 오류: " + error.name;

                        play.textContent =
                            "▶ 재생";
                    }

                } finally {

                    if (
                        currentRequest === requestId
                    ) {

                        play.disabled = false;
                    }
                }
            };


            // 실제 음원 재생 시작
            audio.onplaying = () => {

                if (stopped) {

                    audio.pause();

                    return;
                }

                if (started === null) {

                    started = performance.now();
                }

                play.disabled = false;

                play.textContent =
                    "⏸ 일시정지";

                status.textContent =
                    "집중 사운드 재생 중";
            };


            // 일시정지
            audio.onpause = () => {

                freezeTime();
                updateTimer();

                play.disabled = false;

                play.textContent =
                    "▶ 재생";

                status.textContent =
                    stopped
                    ? "재생 대기 중"
                    : "일시정지";
            };


            // 음원 로딩 중
            audio.onwaiting = () => {

                freezeTime();
                updateTimer();

                if (!stopped) {

                    status.textContent =
                        "음원 불러오는 중";
                }
            };


            // 정지 및 초기화
            stop.onclick = () => {

                stopped = true;
                requestId++;

                audio.pause();

                if (audio.readyState > 0) {

                    audio.currentTime = 0;
                }

                elapsed = 0;
                started = null;

                updateTimer();

                play.disabled = false;

                play.textContent =
                    "▶ 재생";

                status.textContent =
                    "재생 대기 중";
            };


            // 음량 조절
            volume.oninput = () => {

                audio.volume =
                    Number(volume.value) / 100;

                level.textContent =
                    Math.round(audio.volume * 100) + "%";
            };


            // 음원 오류 확인
            audio.onerror = () => {

                freezeTime();
                updateTimer();

                play.disabled = false;

                play.textContent =
                    "▶ 재생";

                const code = audio.error
                    ? audio.error.code
                    : "unknown";

                status.textContent =
                    "음원 오류 (" + code + ")";
            };


            // 누적 시간 갱신
            setInterval(updateTimer, 250);

        </script>

    </body>

    </html>
    """

    player = player.replace(
        "AUDIO_DATA",
        audio_source,
    )

    components.html(
        player,
        height=330,
        scrolling=False,
    )


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
            f"음원 파일이 없습니다: {filename}"
        )
        return

    # 백색소음은 기존 음원 유지
    if filename == "white_noise.ogg":
        audio = filepath.read_bytes()
        audio_format = "audio/ogg"

    else:
        audio_format = "audio/wav"

        try:
            # 싱잉볼 0.85배속 및 음량 증폭
            if filename == "singing_bowl_original.wav":
                audio = prepare_wav(
                    str(filepath),
                    filepath.stat().st_mtime,
                    speed=0.85,
                    target_rms=0.15,
                    max_gain=5.0,
                )

            # 빗소리 음량 증폭
            else:
                audio = prepare_wav(
                    str(filepath),
                    filepath.stat().st_mtime,
                    speed=1.0,
                    target_rms=0.17,
                    max_gain=5.0,
                )

        except Exception:
            st.warning(
                "음원 최적화에 실패하여 "
                "원본 음원을 사용합니다."
            )

            audio = filepath.read_bytes()

    # 재생 오류 발생 시 대체 플레이어
    basic_player = st.checkbox(
        "기본 플레이어 사용 (재생 오류 발생 시)",
        value=False,
        key="bm_basic_audio_player",
    )

    if basic_player:
        st.audio(
            audio,
            format=audio_format,
            loop=True,
            autoplay=False,
        )

        st.caption(
            "기본 플레이어에서는 "
            "원본 음원 길이가 표시됩니다."
        )

    else:
        continuous_player(
            audio,
            audio_format,
        )

    st.caption(
        "누적 재생 시간은 일시정지 시 유지됩니다. "
        "정지하거나 다른 음원을 선택하면 초기화됩니다. "
        "다른 페이지로 이동하면 재생이 중단될 수 있습니다."
    )


# 메인 화면
def main():
    reset_legacy_session()

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
