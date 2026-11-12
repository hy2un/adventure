"""PHARM SHIFT: 독성학·미생물 연구소 탐험 게임."""

from pathlib import Path
import streamlit as st

st.set_page_config(
    page_title="PHARM SHIFT",
    page_icon="🧪",
    layout="centered",
)

ASSETS = Path(__file__).resolve().parent / "assets"

# 두 연구소의 완료 여부는 각각 저장한다.
DEFAULT_STATE = {
    "page": "main",
    "player_name": "학생",
    "lab": None,
    "mission_index": 0,
    "selected_answer": None,
    "toxic_done": False,
    "micro_done": False,
}

LABS = {
    "toxic": {
        "name": "독성학 연구소",
        "title": "TOXIC LAB",
        "image": "toxic_lab.jpg",
        "ending_image": "toxic_end.jpg",
        "intro": "가상 연구소에 경보가 울렸다! 단서를 분석하고 안전하게 탈출하자.",
        "activities": "연구 기록 탐색 · 세포 생존율 비교 · 안전 절차 판단",
        "skills": "관찰력 · 자료 해석력 · 안전 의식",
    },
    "micro": {
        "name": "미생물 연구소",
        "title": "MICRO LAB",
        "image": "micro_lab.jpg",
        "ending_image": "micro_end.jpg",
        "intro": "연구실에서 정체불명의 오염 신호 발견! 관찰 자료를 해독하고 원인을 찾아라.",
        "activities": "미생물 특징 파악 · 관찰 결과 비교 · 오염 가능성 검토",
        "skills": "분류 능력 · 논리적 추론 · 정확한 기록",
    },
}

# 모든 문제와 정답은 프로그램 안에 저장한다.
# 외부 API는 사용하지 않는다.
MISSIONS = {
    "toxic": [
        {
            "title": "사라진 연구 기록",
            "story": (
                "밤 10시, 독성학 연구소에서 모의 경보가 울립니다. "
                "탈출 단서를 찾으려면 마지막 기록이 필요합니다."
            ),
            "clue": "단서: 공식 실험 결과는 전자 연구노트에 저장됩니다.",
            "question": "어디를 먼저 확인할까요?",
            "choices": [
                "전자 연구노트가 저장된 컴퓨터",
                "책상 서랍 속 개인 메모",
                "실험 장비의 작동 버튼",
            ],
            "correct": 0,
            "feedback": [
                "연구 기록 발견! 정확한 기록은 결과 검증에 중요합니다.",
                "공식 기록이 보관된 장소를 다시 찾아보세요.",
                "기록을 찾기 위해 장비를 임의로 조작해서는 안 됩니다.",
            ],
        },
        {
            "title": "독성 데이터의 비밀",
            "story": (
                "같은 시험 조건에서 얻은 가상 세포 생존율 "
                "데이터가 화면에 나타납니다."
            ),
            "clue": (
                "가상 데이터 (동일 조건)\n\n"
                "- 시료 A: 세포 생존율 92%\n"
                "- 시료 B: 세포 생존율 55%\n"
                "- 시료 C: 세포 생존율 81%\n\n"
                "※ 단순화한 교육용 수치이며, 이 결과만으로 "
                "인체 독성을 단정할 수 없습니다."
            ),
            "question": "세포 생존율이 가장 낮아 우선 재검토할 시료는?",
            "choices": [
                "시료 A",
                "시료 B",
                "시료 C",
            ],
            "correct": 1,
            "feedback": [
                "A보다 생존율이 낮은 시료가 있습니다.",
                "정답! B의 생존율이 가장 낮습니다. 원인 파악을 위해 추가 검토가 필요합니다.",
                "C보다 생존율이 낮은 시료가 있습니다.",
            ],
        },
        {
            "title": "마지막 탈출 절차",
            "story": (
                "출입 제한 구역에서 모의 경보가 발생하고 "
                "담당자의 대피 안내가 도착했습니다."
            ),
            "clue": "상황: 실제 사고가 아닌 가상의 안전 교육 상황입니다.",
            "question": "가장 적절한 대응은 무엇일까요?",
            "choices": [
                "경보를 무시하고 실험을 계속한다",
                "혼자 경보 구역으로 들어간다",
                "작업을 중단하고 담당자 지시에 따라 대피한다",
            ],
            "correct": 2,
            "feedback": [
                "경보를 무시하면 안 됩니다.",
                "위험이 의심되는 구역에 임의로 진입하면 안 됩니다.",
                "정답! 안전 절차에 따라 연구소를 탈출했습니다.",
            ],
        },
    ],

    "micro": [
        {
            "title": "현미경 관찰 기록",
            "story": (
                "미생물 연구소의 관찰 카드가 뒤섞였습니다. "
                "첫 번째 단서를 찾아야 합니다."
            ),
            "clue": (
                "관찰 카드: 타원형 세포 일부에서 "
                "작은 돌기가 자라나고 있습니다.\n\n"
                "단서: 일부 효모는 출아 방식으로 번식합니다."
            ),
            "question": "이 관찰 특징과 가장 잘 어울리는 미생물은?",
            "choices": [
                "효모",
                "바이러스",
                "적혈구",
            ],
            "correct": 0,
            "feedback": [
                "정답! 출아는 일부 효모에서 관찰되는 번식 방식입니다.",
                "바이러스는 이처럼 출아하는 세포 자체로 관찰되는 생물이 아닙니다.",
                "적혈구는 미생물이 아닙니다. 단서의 '출아'에 주목하세요.",
            ],
        },
        {
            "title": "오염 의심 시료 찾기",
            "story": (
                "동일한 관찰 조건에서 얻은 "
                "가상의 집락 수 기록이 나타났습니다."
            ),
            "clue": (
                "모의 판정 기준: 집락 수 2개 이하\n\n"
                "- 시료 A: 0개\n"
                "- 시료 B: 8개\n"
                "- 시료 C: 1개\n\n"
                "※ 교육용 가상 데이터이며 실제 시험 기준은 아닙니다."
            ),
            "question": "정해진 모의 기준을 초과한 시료는?",
            "choices": [
                "시료 A",
                "시료 B",
                "시료 C",
            ],
            "correct": 1,
            "feedback": [
                "A는 기준 이내입니다. 다시 비교해 보세요.",
                "정답! B는 모의 기준을 초과했습니다. 오염 가능성을 검토해야 합니다.",
                "C는 기준 이내입니다. 다시 비교해 보세요.",
            ],
        },
        {
            "title": "최종 오염 원인 조사",
            "story": (
                "미생물이 없어야 하는 음성 대조군에서도 "
                "집락이 관찰되었습니다."
            ),
            "clue": (
                "단서: 음성 대조군은 실험 과정의 "
                "오염 가능성을 확인할 때 도움을 줍니다.\n\n"
                "이번 기록에서는 대조군에서도 집락이 관찰되었습니다."
            ),
            "question": "연구 보고서에 가장 적절하게 기록할 내용은?",
            "choices": [
                "다른 시료의 결과는 모두 정확하다고 확정한다",
                "대조군 이상을 무시하고 결과만 제출한다",
                "실험 과정의 오염 가능성을 기록하고 결과 재검토를 요청한다",
            ],
            "correct": 2,
            "feedback": [
                "대조군 이상이 있으면 결과의 신뢰성을 먼저 검토해야 합니다.",
                "대조군 결과는 무시하면 안 됩니다.",
                "정답! 이상을 기록하고 재검토를 요청해 연구 보고서를 마무리했습니다.",
            ],
        },
    ],
}


# ---------------------------
# 게임 상태 관리
# ---------------------------

def initialize_state():
    """최초 실행 때에만 필요한 게임 상태를 만든다."""
    for key, value in DEFAULT_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_game():
    """메인 복귀 시 이전 진행 기록을 초기화한다."""
    for key, value in DEFAULT_STATE.items():
        st.session_state[key] = value

    st.session_state["name_input"] = ""


def move(page):
    """지정된 화면으로 이동한다."""
    st.session_state["page"] = page
    st.rerun()


def show_image(filename, description):
    """이미지 파일이 누락되어도 게임은 계속 실행된다."""
    path = ASSETS / filename

    if path.is_file():
        try:
            st.image(str(path), use_container_width=True)
            return
        except Exception:
            pass

    st.caption(f"🖼️ {description} (이미지 추가 예정)")


def show_home_button():
    """메인 외 화면에 메인 이동 버튼을 표시한다."""
    if st.session_state["page"] != "main":
        if st.button("⌂ 메인으로", key="home_button"):
            reset_game()
            st.rerun()


# ---------------------------
# 메인 화면
# ---------------------------

def show_main():
    st.title("PHARM SHIFT")
    st.subheader("선택한 하루, 서로 다른 약학의 세계")

    show_image("school.jpg", "학교 진로 체험 안내")

    st.markdown("### 교내 연구소 탐험 프로그램 참가자 모집")

    st.write(
        "독성학과 미생물 연구소에서 "
        "각각 세 가지 미션에 도전해 보세요!"
    )

    st.info("실제 실험이 아닌 교육용 가상 체험입니다.")

    if st.button(
        "체험 신청하기",
        type="primary",
        use_container_width=True,
    ):
        reset_game()
        move("register")


# ---------------------------
# 참가 신청 화면
# ---------------------------

def show_register():
    st.header("참가 신청")

    name = st.text_input(
        "참가자 이름",
        key="name_input",
        max_chars=20,
        placeholder="입력하지 않으면 '학생'으로 진행",
    )

    if st.button(
        "신청 완료",
        type="primary",
        use_container_width=True,
    ):
        st.session_state["player_name"] = name.strip() or "학생"
        move("orientation")


# ---------------------------
# 오리엔테이션 화면
# ---------------------------

def show_orientation():
    st.header("오리엔테이션")

    name = st.session_state["player_name"]

    st.write(
        f"안내 NPC: 안녕, {name}! "
        "두 연구소 중 한 곳을 선택해 탐험해 봐."
    )

    st.write(
        "독성학 연구소에서는 경보의 원인을 찾고 탈출하게 돼."
    )

    st.write(
        "미생물 연구소에서는 관찰 자료를 분석하고 "
        "오염 의심 원인을 조사해."
    )

    st.write(
        "두 연구소를 모두 완료하면 "
        "특별 엔딩과 가상 수료증이 열려!"
    )

    if st.button(
        "연구소 선택하기",
        type="primary",
        use_container_width=True,
    ):
        move("choose")


# ---------------------------
# 연구소 선택 화면
# ---------------------------

def start_lab(lab):
    """선택한 연구소의 진행 상태만 초기화한다."""
    st.session_state["lab"] = lab
    st.session_state["mission_index"] = 0
    st.session_state["selected_answer"] = None

    # 다른 연구소의 완료 기록은 유지한다.
    move("mission")


def show_choose():
    st.header("연구소 선택")

    st.write(
        f"{st.session_state['player_name']} 학생, "
        "어디부터 탐험할까요?"
    )

    for lab in ("toxic", "micro"):
        info = LABS[lab]

        st.subheader(f"{info['title']} · {info['name']}")

        show_image(info["image"], info["name"])

        st.write(info["intro"])

        if st.session_state[f"{lab}_done"]:
            st.success(
                "체험 완료! 다시 탐험할 수도 있습니다."
            )

        if st.button(
            f"{info['name']} 탐험하기",
            key=f"start_{lab}",
            use_container_width=True,
        ):
            start_lab(lab)

        st.divider()


# ---------------------------
# 연구소별 미션 화면
# ---------------------------

def show_mission():
    lab = st.session_state["lab"]
    index = st.session_state["mission_index"]

    # 잘못된 연구소 또는 미션 번호 검사
    if lab not in MISSIONS or not 0 <= index < len(MISSIONS[lab]):
        st.error(
            "미션 상태가 올바르지 않습니다. "
            "메인으로 돌아가 주세요."
        )
        return

    info = LABS[lab]
    task = MISSIONS[lab][index]
    count = len(MISSIONS[lab])

    st.header(f"{info['title']} · {info['name']}")

    st.progress(
        index / count,
        text=f"완료한 미션 {index}/{count}",
    )

    show_image(info["image"], info["name"])

    st.subheader(
        f"MISSION {index + 1}. {task['title']}"
    )

    st.write(task["story"])
    st.info(task["clue"])
    st.write(f"**{task['question']}**")

    selected = st.session_state["selected_answer"]

    # 답을 선택하기 전
    if selected is None:
        for i, choice in enumerate(task["choices"]):
            if st.button(
                f"{chr(65 + i)}. {choice}",
                key=f"answer_{lab}_{index}_{i}",
                use_container_width=True,
            ):
                st.session_state["selected_answer"] = i
                st.rerun()
        return

    # 정답 처리
    if selected == task["correct"]:
        st.success(task["feedback"][selected])

        last = index == count - 1

        if last:
            label = "연구소 엔딩 보기"
        else:
            label = "다음 미션"

        if st.button(
            label,
            type="primary",
            use_container_width=True,
        ):
            if last:
                st.session_state[f"{lab}_done"] = True
                move("ending")
            else:
                st.session_state["mission_index"] += 1
                st.session_state["selected_answer"] = None
                st.rerun()

    # 오답 처리
    else:
        st.warning(task["feedback"][selected])

        if st.button(
            "다시 선택하기",
            use_container_width=True,
        ):
            st.session_state["selected_answer"] = None
            st.rerun()


# ---------------------------
# 연구소별 엔딩 화면
# ---------------------------

def show_ending():
    lab = st.session_state["lab"]

    if lab not in LABS or not st.session_state[f"{lab}_done"]:
        st.warning(
            "모든 미션을 완료해야 엔딩을 볼 수 있습니다."
        )
        return

    info = LABS[lab]

    st.header(f"{info['title']} — CLEAR!")

    show_image(
        info["ending_image"],
        f"{info['name']} 엔딩",
    )

    if lab == "toxic":
        st.write(
            "연구 기록과 독성 데이터를 분석하고 "
            "안전 절차를 따라 탈출했습니다!"
        )

        st.write(
            "안내 NPC: 독성학은 물질이 생체에 미치는 "
            "유해한 영향을 연구하는 분야야."
        )

    else:
        st.write(
            "미생물 관찰 기록을 확인하고 오염 가능성에 대한 "
            "보고서를 완성했습니다!"
        )

        st.write(
            "안내 NPC: 미생물학은 미생물의 특징과 "
            "활동을 연구하는 분야야."
        )

    if st.button(
        "체험 결과 확인하기",
        type="primary",
        use_container_width=True,
    ):
        move("result")


# ---------------------------
# 체험 결과 화면
# ---------------------------

def show_result():
    lab = st.session_state["lab"]

    if lab not in LABS or not st.session_state[f"{lab}_done"]:
        st.warning("완료한 체험 결과가 없습니다.")
        return

    info = LABS[lab]

    st.header("체험 결과")

    st.write(
        f"참가자: {st.session_state['player_name']}"
    )

    st.write(f"완료 연구소: {info['name']}")

    st.metric("완료 미션", "3 / 3")

    st.write(f"수행 활동: {info['activities']}")
    st.write(f"관련 역량: {info['skills']}")

    # 두 연구소를 모두 완료했는지 검사
    if (
        st.session_state["toxic_done"]
        and st.session_state["micro_done"]
    ):
        st.success(
            "두 연구소를 모두 완료했습니다! "
            "특별 엔딩이 열렸습니다."
        )

        if st.button(
            "특별 엔딩 보기",
            type="primary",
            use_container_width=True,
        ):
            move("bonus")

    else:
        st.info(
            "다른 연구소까지 완료하면 특별 엔딩이 열립니다."
        )

    if st.button(
        "다른 연구소 탐험하기",
        use_container_width=True,
    ):
        move("choose")

    if st.button(
        "처음으로 돌아가기",
        use_container_width=True,
    ):
        reset_game()
        st.rerun()


# ---------------------------
# 특별 엔딩 화면
# ---------------------------

def show_bonus():
    # 두 연구소 모두 완료해야 특별 엔딩 진입
    if not (
        st.session_state["toxic_done"]
        and st.session_state["micro_done"]
    ):
        st.warning(
            "두 연구소를 모두 완료해야 볼 수 있는 화면입니다."
        )
        return

    st.title("PHARM SHIFT COMPLETE!")

    st.subheader(
        "특별 엔딩 · 두 연구소의 연결고리"
    )

    st.write(
        f"축하해, {st.session_state['player_name']}!"
    )

    st.write(
        "독성학 연구소에서는 물질의 유해한 영향을, "
        "미생물 연구소에서는 미생물의 특징과 "
        "오염 가능성을 조사했어."
    )

    st.write(
        "두 분야 모두 관찰·기록·자료 해석을 바탕으로 "
        "과학적 결론을 검토한다는 공통점이 있어."
    )

    st.divider()

    st.subheader("🏅 가상 연구소 탐험 수료증")

    st.write(
        f"참가자: {st.session_state['player_name']}"
    )

    st.write(
        "완료 연구소: 독성학 연구소 · 미생물 연구소"
    )

    st.write("완료 미션: 6 / 6")

    st.caption(
        "게임 내 교육용 수료증이며 "
        "실제 공식 자격이나 수료를 뜻하지 않습니다."
    )

    if st.button(
        "처음으로 돌아가기",
        type="primary",
        use_container_width=True,
    ):
        reset_game()
        st.rerun()


# ---------------------------
# 메인 프로그램 실행
# ---------------------------

def main():
    initialize_state()
    show_home_button()

    # 현재 페이지에 따라 실행할 함수 선택
    pages = {
        "main": show_main,
        "register": show_register,
        "orientation": show_orientation,
        "choose": show_choose,
        "mission": show_mission,
        "ending": show_ending,
        "result": show_result,
        "bonus": show_bonus,
    }

    pages.get(
        st.session_state["page"],
        show_main,
    )()


if __name__ == "__main__":
    main()
