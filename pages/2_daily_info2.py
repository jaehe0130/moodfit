import streamlit as st
import pandas as pd
from datetime import date
from sheets_auth import connect_gsheet  # 🔥 추가

EMOTION_AROUSAL = {
    "행복": 3, "기쁨": 4, "설렘": 4, "자신감": 3, "활력": 5, "만족": 2,
    "슬픔": 1, "분노": 5, "불안": 4, "두려움": 4, "피로": 1, "스트레스": 4,
    "무기력": 1, "지루함": 2, "외로움": 2,
    "차분함": 2, "집중": 3, "긴장": 4, "놀람": 4, "혼란": 3
}

def compute_avg_arousal(emotion_list):
    scores = [EMOTION_AROUSAL[e] for e in emotion_list if e in EMOTION_AROUSAL]
    return sum(scores) / len(scores) if scores else ""

st.set_page_config(page_title="오늘의 컨디션 입력", layout="centered", page_icon="💪")

st.markdown("""
    <h1 style='text-align:center; font-weight:700;'>💡 오늘의 컨디션 기록하기</h1>
    <p style='text-align:center; color:gray; margin-top:-10px;'>운동 추천의 정확도를 높여요!</p>
""", unsafe_allow_html=True)

# Google Sheet 연결
sh = connect_gsheet("MoodFit")
ws = sh.worksheet("daily")  # ▶️ daily 시트로 저장
# (처음 만들면 Sheet 내부에서 manually 시트명 daily 로 만들어두기)

selected_date = st.date_input("📅 오늘 날짜", value=date.today())

users = sh.sheet1.col_values(1)  # 이름 리스트 가져오기
user_name = st.selectbox("기록할 사용자 선택", users[1:])  # header 제외

st.markdown("### 😄 오늘의 감정 상태")
all_emotions = list(EMOTION_AROUSAL.keys())
emotions = st.multiselect("오늘 느낀 감정을 모두 선택하세요", all_emotions)

st.markdown("---")
col1, col2 = st.columns(2)
sleep_hours = col1.slider("수면 시간", 0, 12, 7)
exercise_time = col2.slider("운동 가능 시간(분)", 0, 180, 30)
stress_level = st.selectbox("스트레스", ["낮음", "보통", "높음"])

purpose = st.radio("오늘의 운동 목적", ["체중 감량", "체력 향상", "스트레스 해소", "체형 교정"],
                   horizontal=True)

exercise_place = st.selectbox("운동 장소", ["실내(집)", "실내(헬스장)", "야외(공원)", "기타"])
equip = st.multiselect("보유 장비", ["요가매트","덤벨","밴드","폼롤러","점프 로프","푸쉬업바"])
equip_str = ", ".join(equip) if equip else "없음"

avg_score = compute_avg_arousal(emotions)

if st.button("💾 저장하고 추천 받기", use_container_width=True):
    ws.append_row([
        str(selected_date), user_name, ", ".join(emotions),
        avg_score, sleep_hours, exercise_time, stress_level,
        purpose, exercise_place, equip_str,
        "", "", "", "", ""     # 추천1~3 + 평가용 공간 미리 확보
    ])
    st.success("✔ 저장 완료! 추천 페이지로 이동합니다")
    st.switch_page("pages/3_recommendation.py")
