"""북플래닛 집중 사운드 변환기.

원본 파일:
    singing_bowl_original.wav
    rain_original.wav

생성 파일:
    singing_bowl.ogg
    rain.ogg

빗소리는 최대 90초로 잘라 용량을 줄입니다.
싱잉볼은 0.85배속으로 약 3분 분량을 만듭니다.
"""
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
SR = 32000


def load_wav(path, max_seconds=None):
    if not path.is_file():
        raise FileNotFoundError(
            f"원본 파일 없음: {path.name}"
        )

    with sf.SoundFile(path) as wav:
        original_sr = wav.samplerate

        frames = (
            wav.frames
            if max_seconds is None
            else min(
                wav.frames,
                int(max_seconds * original_sr),
            )
        )

        audio = wav.read(
            frames=frames,
            dtype="float32",
            always_2d=True,
        )

    if audio.size == 0:
        raise ValueError("빈 WAV 파일입니다.")

    # 스테레오보다 채널이 많으면 모노로 변환
    if audio.shape[1] > 2:
        audio = audio.mean(
            axis=1,
            keepdims=True,
        )

    # 32kHz로 변환
    if original_sr != SR:
        count = max(
            1,
            round(
                len(audio) * SR / original_sr
            ),
        )

        old = np.arange(len(audio))
        new = (
            np.arange(count) * original_sr / SR
        )

        audio = np.column_stack([
            np.interp(
                new, old, audio[:, i]
            ).astype(np.float32)
            for i in range(audio.shape[1])
        ])

    return audio


def save_ogg(filename, audio):
    path = ROOT / filename

    peak = float(
        np.max(np.abs(audio))
    )

    if peak > 0.85:
        audio = audio * (0.85 / peak)

    with sf.SoundFile(
        path,
        mode="w",
        samplerate=SR,
        channels=audio.shape[1],
        format="OGG",
        subtype="VORBIS",
    ) as out:
        for start in range(
            0, len(audio), 16000
        ):
            out.write(
                audio[start:start + 16000]
            )

    print(
        f"완료: {filename} "
        f"({path.stat().st_size / 1024 / 1024:.2f}MB)"
    )


def make_singing_bowl():
    audio = load_wav(
        ROOT / "singing_bowl_original.wav"
    )

    # 재생 속도 0.85배, 음높이도 낮아짐
    speed = 0.85
    new_count = round(
        len(audio) / speed
    )

    old = np.arange(len(audio))
    new = np.arange(new_count) * speed

    audio = np.column_stack([
        np.interp(
            new, old, audio[:, i]
        ).astype(np.float32)
        for i in range(audio.shape[1])
    ])

    # 시작과 끝 페이드
    fade_in = min(
        len(audio) // 4,
        int(0.25 * SR),
    )

    audio[:fade_in] *= np.linspace(
        0, 1, fade_in,
        dtype=np.float32,
    )[:, None]

    fade_out = min(
        len(audio) // 3,
        4 * SR,
    )

    audio[-fade_out:] *= np.linspace(
        1, 0, fade_out,
        dtype=np.float32,
    )[:, None]

    # 3분 길이의 싱잉볼 배경음 제작
    duration = 180
    overlap = 4

    output = np.zeros(
        ((duration + overlap) * SR, audio.shape[1]),
        dtype=np.float32,
    )

    rng = np.random.default_rng(616335)

    position = 6.0
    count = 0

    while position < duration + overlap:
        start = round(position * SR)
        end = min(
            len(output),
            start + len(audio),
        )

        if end > start:
            volume = (
                0.68, 0.77, 0.63, 0.72
            )[count % 4]

            output[start:end] += (
                audio[:end-start] * volume
            )

        position += float(
            rng.uniform(21.5, 24.5)
        )
        count += 1

    n = duration * SR
    cross = overlap * SR

    result = output[:n].copy()

    blend = np.linspace(
        0, 1, cross,
        dtype=np.float32,
    )[:, None]

    result[:cross] = (
        output[n:n+cross] * (1-blend)
        + result[:cross] * blend
    )

    save_ogg(
        "singing_bowl.ogg",
        result,
    )


def make_rain():
    # WAV 전체가 아니라 최대 93초만 읽음
    audio = load_wav(
        ROOT / "rain_original.wav",
        max_seconds=93,
    )

    length_seconds = len(audio) / SR

    if length_seconds >= 93:
        # 첫 90초를 사용하고
        # 뒤 3초를 반복 연결부에 활용
        seconds = 90
        overlap = 3

        n = seconds * SR
        cross = overlap * SR

        result = audio[:n].copy()

        blend = np.linspace(
            0, 1, cross,
            dtype=np.float32,
        )[:, None]

        result[:cross] = (
            audio[n:n+cross] * (1-blend)
            + result[:cross] * blend
        )

    else:
        # 원본이 짧으면 있는 부분만 사용
        result = audio

        # 짧은 페이드로 반복 경계의
        # 급격한 변화를 완화
        fade = min(
            len(result) // 4,
            int(0.5 * SR),
        )

        if fade > 0:
            envelope = np.linspace(
                0, 1, fade,
                dtype=np.float32,
            )[:, None]

            result[:fade] *= envelope
            result[-fade:] *= envelope[::-1]

    save_ogg(
        "rain.ogg",
        result,
    )


if __name__ == "__main__":
    make_singing_bowl()
    make_rain()

    print("음원 변환이 완료되었습니다.")
