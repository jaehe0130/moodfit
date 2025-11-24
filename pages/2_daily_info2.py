# import streamlit as st
# import pandas as pd
# import os
# from datetime import date
# from streamlit_extras.stylable_container import stylable_container
#
# # 페이지 기본 설정
# st.set_page_config(
#     page_title="오늘의 컨디션 입력",
#     layout="centered",
#     page_icon="💪"
# )
#
# # 상단 헤더
# st.markdown(
#     """
#     <h1 style='text-align:center; font-weight: 700;'>
#         💡 오늘의 컨디션 기록하기
#     </h1>
#     <p style='text-align:center; color:gray; margin-top:-10px;'>
#         하루 컨디션을 기록하면 맞춤 운동 추천의 정확도가 올라갑니다!
#     </p>
#     """,
#     unsafe_allow_html=True
# )
#
# user_csv = "users.csv"
# daily_csv = "daily_info.csv"
#
# # ⏳ 날짜 입력 카드
# st.markdown("### 📅 오늘 날짜")
# selected_date = st.date_input(
#     "",
#     value=date.today(),
#     help="운동 추천은 선택한 날짜 기준으로 제공됩니다."
# )
#
# # 👤 사용자 선택
# if not os.path.exists(user_csv):
#     st.error("⚠️ 먼저 '정적 정보' 메뉴에서 회원을 등록해주세요.")
# else:
#     users_df = pd.read_csv(user_csv)
#     st.markdown("### 👤 사용자 선택")
#     user_name = st.selectbox("기록할 사용자", users_df["이름"].tolist())
#
#     st.markdown("---")
#
#     # 😄 감정 상태
#     st.markdown("### 😄 오늘의 감정 상태")
#
#     positive_emotions = ["행복", "기쁨", "설렘", "자신감", "활력", "만족"]
#     negative_emotions = ["슬픔", "분노", "불안", "두려움", "피로", "스트레스", "무기력", "지루함", "외로움"]
#     neutral_emotions = ["차분함", "집중", "긴장", "놀람", "혼란"]
#
#     all_emotions = positive_emotions + negative_emotions + neutral_emotions
#
#     emotions = st.multiselect(
#         "오늘 느낀 감정을 모두 선택하세요",
#         all_emotions,
#         help="중복 선택 가능"
#     )
#
#     st.markdown("---")
#
#     # 🛌 기본 컨디션
#     st.markdown("### 🛌 오늘의 상태")
#
#     col1, col2 = st.columns(2)
#     with col1:
#         sleep_hours = st.slider("수면 시간", 0, 12, 7, help="권장 수면 시간은 7~9시간입니다.")
#     with col2:
#         exercise_time = st.slider("운동 가능 시간(분)", 0, 180, 30)
#
#     stress_level = st.selectbox(
#         "스트레스 정도",
#         ["낮음", "보통", "높음"],
#         help="오늘의 스트레스 수준을 선택하세요."
#     )
#
#     st.markdown("---")
#
#     # 🎯 운동 목적
#     st.markdown("### 🎯 운동 목적")
#
#     purpose = st.radio(
#         "오늘의 운동 목적을 선택하세요",
#         ["체중 감량", "체력 향상", "스트레스 해소", "체형 교정"],
#         horizontal=True
#     )
#
#     st.markdown("---")
#
#     # 🏋🏼 운동 환경
#     st.markdown("### 🏋🏼‍♂️ 운동 환경 및 장비")
#
#     exercise_place = st.selectbox(
#         "운동 장소",
#         ["실내(집)", "실내(헬스장)", "야외(공원/운동장)", "기타"]
#     )
#
#     equipment_options = [
#         "요가매트", "덤벨", "저항 밴드", "러닝머신", "실내자전거",
#         "폼롤러", "케틀벨", "스트레칭 밴드", "점프 로프", "푸쉬업바"
#     ]
#     owned_equipment = st.multiselect(
#         "보유 장비 (선택 사항)",
#         equipment_options,
#         help="없다면 선택하지 않아도 됩니다."
#     )
#     owned_equipment_str = ', '.join(owned_equipment) if owned_equipment else '없음'
#
#     st.markdown("---")
#
#     # 💾 저장 버튼
#     st.markdown("<br>", unsafe_allow_html=True)
#
#     if st.button("💾 오늘의 컨디션 저장하기", use_container_width=True):
#         user_info = users_df[users_df["이름"] == user_name].iloc[0]
#
#         new_data = pd.DataFrame({
#             "날짜": [selected_date],
#             "이름": [user_info["이름"]],
#             "나이": [user_info["나이"]],
#             "성별": [user_info["성별"]],
#             "키(cm)": [user_info["키(cm)"]],
#             "몸무게(kg)": [user_info["몸무게(kg)"]],
#             "감정": [', '.join(emotions)],
#             "수면시간": [sleep_hours],
#             "운동가능시간(분)": [exercise_time],
#             "스트레스": [stress_level],
#             "운동목적": [purpose],
#             "운동장소": [exercise_place],
#             "보유장비": [owned_equipment_str]
#         })
#
#         if os.path.exists(daily_csv):
#             old = pd.read_csv(daily_csv)
#             updated = pd.concat([old, new_data], ignore_index=True)
#             updated.to_csv(daily_csv, index=False)
#         else:
#             new_data.to_csv(daily_csv, index=False)
#
#         st.success("✔️ 오늘의 컨디션이 성공적으로 저장되었습니다!")


# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import os
import numpy as np
from datetime import date
from streamlit_extras.stylable_container import stylable_container

# =========================
# 1. 감정별 각성도 점수 매핑
# =========================
EMOTION_AROUSAL = {
    # 긍정 감정
    "행복": 3,
    "기쁨": 4,
    "설렘": 4,
    "자신감": 3,
    "활력": 5,
    "만족": 2,

    # 부정 감정
    "슬픔": 1,
    "분노": 5,
    "불안": 4,
    "두려움": 4,
    "피로": 1,
    "스트레스": 4,
    "무기력": 1,
    "지루함": 2,
    "외로움": 2,

    # 중립 감정
    "차분함": 2,
    "집중": 3,
    "긴장": 4,
    "놀람": 4,
    "혼란": 3,
}

# =========================
# 2. 각성도 레벨 구분 함수
# =========================
def get_arousal_level(score: float) -> str:
    if pd.isna(score):
        return ""
    if score < 1:
        return "매우 낮음"
    elif score < 2:
        return "낮음"
    elif score < 3:
        return "중간"
    elif score < 4:
        return "높음"
    else:
        return "매우 높음"

# =========================
# 3. 감정 리스트 → 평균 각성 점수
# =========================
def compute_avg_arousal(emotion_list):
    scores = []
    for e in emotion_list:
        if e in EMOTION_AROUSAL:
            scores.append(EMOTION_AROUSAL[e])
        # 매핑 없는 감정은 그냥 무시

    if not scores:
        return np.nan

    return float(sum(scores) / len(scores))


# =========================
# 페이지 기본 설정
# =========================
st.set_page_config(
    page_title="오늘의 컨디션 입력",
    layout="centered",
    page_icon="💪"
)

# 상단 헤더
st.markdown(
    """
    <h1 style='text-align:center; font-weight: 700;'>
        💡 오늘의 컨디션 기록하기
    </h1>
    <p style='text-align:center; color:gray; margin-top:-10px;'>
        하루 컨디션을 기록하면 맞춤 운동 추천의 정확도가 올라갑니다!
    </p>
    """,
    unsafe_allow_html=True
)

user_csv = "users.csv"
daily_csv = "daily_info.csv"

# ⏳ 날짜 입력 카드
st.markdown("### 📅 오늘 날짜")
selected_date = st.date_input(
    "",
    value=date.today(),
    help="운동 추천은 선택한 날짜 기준으로 제공됩니다."
)

# 👤 사용자 선택
if not os.path.exists(user_csv):
    st.error("⚠️ 먼저 '정적 정보' 메뉴에서 회원을 등록해주세요.")
    st.stop()
else:
    users_df = pd.read_csv(user_csv)
    st.markdown("### 👤 사용자 선택")
    user_name = st.selectbox("기록할 사용자", users_df["이름"].tolist())

    st.markdown("---")

    # 😄 감정 상태
    st.markdown("### 😄 오늘의 감정 상태")

    positive_emotions = ["행복", "기쁨", "설렘", "자신감", "활력", "만족"]
    negative_emotions = ["슬픔", "분노", "불안", "두려움", "피로", "스트레스", "무기력", "지루함", "외로움"]
    neutral_emotions = ["차분함", "집중", "긴장", "놀람", "혼란"]

    all_emotions = positive_emotions + negative_emotions + neutral_emotions

    emotions = st.multiselect(
        "오늘 느낀 감정을 모두 선택하세요",
        all_emotions,
        help="중복 선택 가능"
    )

    st.markdown("---")

    # 🛌 기본 컨디션
    st.markdown("### 🛌 오늘의 상태")

    col1, col2 = st.columns(2)
    with col1:
        sleep_hours = st.slider("수면 시간", 0, 12, 7, help="권장 수면 시간은 7~9시간입니다.")
    with col2:
        exercise_time = st.slider("운동 가능 시간(분)", 0, 180, 30)

    stress_level = st.selectbox(
        "스트레스 정도",
        ["낮음", "보통", "높음"],
        help="오늘의 스트레스 수준을 선택하세요."
    )

    st.markdown("---")

    # 🎯 운동 목적
    st.markdown("### 🎯 운동 목적")

    purpose = st.radio(
        "오늘의 운동 목적을 선택하세요",
        ["체중 감량", "체력 향상", "스트레스 해소", "체형 교정"],
        horizontal=True
    )

    st.markdown("---")

    # 🏋🏼 운동 환경
    st.markdown("### 🏋🏼‍♂️ 운동 환경 및 장비")

    exercise_place = st.selectbox(
        "운동 장소",
        ["실내(집)", "실내(헬스장)", "야외(공원/운동장)", "기타"]
    )

    equipment_options = [
        "요가매트", "덤벨", "저항 밴드", "러닝머신", "실내자전거",
        "폼롤러", "케틀벨", "스트레칭 밴드", "점프 로프", "푸쉬업바"
    ]
    owned_equipment = st.multiselect(
        "보유 장비 (선택 사항)",
        equipment_options,
        help="없다면 선택하지 않아도 됩니다."
    )
    owned_equipment_str = ', '.join(owned_equipment) if owned_equipment else '없음'

    st.markdown("---")

    # 💾 저장 버튼
    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("💾 오늘의 컨디션 저장하기", use_container_width=True):
        if len(emotions) == 0:
            st.warning("⚠️ 감정을 최소 1개 이상 선택해주세요.")
            st.stop()

        user_info = users_df[users_df["이름"] == user_name].iloc[0]

        # ✅ 감정 각성도/레벨 자동 계산
        avg_arousal = compute_avg_arousal(emotions)
        arousal_level = get_arousal_level(avg_arousal)

        new_data = pd.DataFrame({
            "날짜": [selected_date],
            "이름": [user_info["이름"]],
            "나이": [user_info["나이"]],
            "성별": [user_info["성별"]],
            "키(cm)": [user_info["키(cm)"]],
            "몸무게(kg)": [user_info["몸무게(kg)"]],
            "감정": [', '.join(emotions)],

            # ✅ 추가 저장 컬럼
            "감정_리스트": [', '.join(emotions)],
            "감정_평균각성점수": [avg_arousal],
            "감정_활성도레벨": [arousal_level],

            "수면시간": [sleep_hours],
            "운동가능시간(분)": [exercise_time],
            "스트레스": [stress_level],
            "운동목적": [purpose],
            "운동장소": [exercise_place],
            "보유장비": [owned_equipment_str]
        })

        # 기존 파일 있으면 concat, 없으면 새로 생성
        if os.path.exists(daily_csv):
            old = pd.read_csv(daily_csv)

            # 혹시 기존 파일에 위 3개 컬럼이 없으면 미리 만들어주기
            for c in ["감정_리스트", "감정_평균각성점수", "감정_활성도레벨"]:
                if c not in old.columns:
                    old[c] = ""

            updated = pd.concat([old, new_data], ignore_index=True)
            updated.to_csv(daily_csv, index=False, encoding="utf-8-sig")
        else:
            new_data.to_csv(daily_csv, index=False, encoding="utf-8-sig")

        st.success("✔️ 오늘의 컨디션이 성공적으로 저장되었습니다!")
        st.switch_page("pages/3_recommendation.py")  

