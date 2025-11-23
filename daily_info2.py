import streamlit as st
import pandas as pd
import os
from datetime import date
from streamlit_extras.stylable_container import stylable_container

# 페이지 기본 설정
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
        user_info = users_df[users_df["이름"] == user_name].iloc[0]

        new_data = pd.DataFrame({
            "날짜": [selected_date],
            "이름": [user_info["이름"]],
            "나이": [user_info["나이"]],
            "성별": [user_info["성별"]],
            "키(cm)": [user_info["키(cm)"]],
            "몸무게(kg)": [user_info["몸무게(kg)"]],
            "감정": [', '.join(emotions)],
            "수면시간": [sleep_hours],
            "운동가능시간(분)": [exercise_time],
            "스트레스": [stress_level],
            "운동목적": [purpose],
            "운동장소": [exercise_place],
            "보유장비": [owned_equipment_str]
        })

        if os.path.exists(daily_csv):
            old = pd.read_csv(daily_csv)
            updated = pd.concat([old, new_data], ignore_index=True)
            updated.to_csv(daily_csv, index=False)
        else:
            new_data.to_csv(daily_csv, index=False)

        st.success("✔️ 오늘의 컨디션이 성공적으로 저장되었습니다!")
        st.balloons()
