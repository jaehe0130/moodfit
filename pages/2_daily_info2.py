import streamlit as st
import pandas as pd
from datetime import date
from sheets_auth import connect_gsheet

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

# =========================
# 🔌 Google Sheet 연결 (캐시)
# =========================
@st.cache_resource
def get_spreadsheet():
    """MoodFit 스프레드시트 객체 캐시"""
    return connect_gsheet("MoodFit")

def load_users():
    """
    회원 이름 목록을 항상 최신으로 가져오기.
    - 스프레드시트의 'users' 시트 사용
    - A열(첫 번째 열)에 '이름' 헤더 + 데이터가 있다고 가정
    """
    sh = get_spreadsheet()
    ws_user = sh.worksheet("users")  # ▶️ 회원 정보 시트 이름 명시

    names = ws_user.col_values(1)  # A열

    # 예: ["이름", "홍길동", "김지우", ...]
    if len(names) <= 1:
        return []

    return names[1:]  # 헤더("이름") 제외하고 실제 이름만 반환

# 스프레드시트 & daily 시트
sh = get_spreadsheet()
ws = sh.worksheet("daily")  # ▶️ daily 시트로 저장 (미리 만들어두기)

# =========================
# 📅 날짜 & 사용자 선택
# =========================
selected_date = st.date_input("📅 오늘 날짜", value=date.today())

users = load_users()
if not users:
    st.error("❌ 등록된 회원이 없습니다. 먼저 '회원 등록' 페이지에서 사용자를 추가해주세요.")
    st.stop()

user_name = st.selectbox("기록할 사용자 선택", users)

# =========================
# 😄 감정 상태 입력
# =========================
st.markdown("### 😄 오늘의 감정 상태")
all_emotions = list(EMOTION_AROUSAL.keys())
emotions = st.multiselect("오늘 느낀 감정을 모두 선택하세요", all_emotions)

st.markdown("---")

# =========================
# 💤 수면 / 시간 / 스트레스 / 목적 / 장소 / 장비
# =========================
col1, col2 = st.columns(2)
sleep_hours = col1.slider("수면 시간", 0, 12, 7)
exercise_time = col2.slider("운동 가능 시간(분)", 0, 180, 30)
stress_level = st.selectbox("스트레스", ["낮음", "보통", "높음"])

purpose = st.radio(
    "오늘의 운동 목적",
    ["체중 감량", "체력 향상", "스트레스 해소", "체형 교정"],
    horizontal=True
)

exercise_place = st.selectbox("운동 장소", ["실내(집)", "실내(헬스장)", "야외(공원)", "기타"])
equip = st.multiselect("보유 장비", ["요가매트", "덤벨", "밴드", "폼롤러", "점프 로프", "푸쉬업바"])
equip_str = ", ".join(equip) if equip else "없음"

avg_score = compute_avg_arousal(emotions)

# =========================
# 💾 저장 버튼
# =========================
if st.button("💾 저장하고 추천 받기", use_container_width=True):
    ws.append_row([
        str(selected_date),      # 날짜
        user_name,               # 이름
        ", ".join(emotions),     # 감정 리스트
        avg_score,               # 감정 각성도 평균
        sleep_hours,             # 수면 시간
        exercise_time,           # 운동 가능 시간
        stress_level,            # 스트레스
        purpose,                 # 운동 목적
        exercise_place,          # 운동 장소
        equip_str,               # 보유 장비
        "", "", "", "", ""       # 추천1~3 + 이유 자리 미리 확보
    ])

    st.success("✔ 저장 완료! 추천 페이지로 이동합니다")
    st.balloons()
    st.switch_page("pages/3_recommendation.py")
