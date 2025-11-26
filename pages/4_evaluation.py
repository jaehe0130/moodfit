import streamlit as st
from datetime import datetime
from sheets_auth import connect_gsheet

st.set_page_config(page_title="추천운동 평가", page_icon="📊", layout="centered")
st.title("📊 추천운동 평가")

# =====================================================
# 🛑 1. 필수 session_state 값 체크
# =====================================================
required_keys = ["recommended_workouts", "selected_user", "selected_date"]

missing = [k for k in required_keys if k not in st.session_state]

if missing:
    st.error("⚠ 필수 정보가 존재하지 않아 평가 페이지를 열 수 없습니다.")
    st.info("추천 과정을 먼저 진행해주세요.")
    if st.button("⬅ 추천 페이지로 돌아가기"):
        st.switch_page("pages/3_recommendation.py")
    st.stop()

recommended = st.session_state["recommended_workouts"]
user_name  = st.session_state["selected_user"]
date       = st.session_state["selected_date"]

# =====================================================
# 2. 추천 운동 목록 표시
# =====================================================
st.markdown("### 📍 오늘 추천받은 운동:")
for r in recommended:
    st.markdown(f"- **{r}**")

st.markdown("---")

# =====================================================
# 3. 운동별 평가
# =====================================================
st.subheader("📝 추천 운동별 적합도 평가")
ratings = {}
for r in recommended:
    ratings[r] = st.slider(f"'{r}' 운동 적합도 평가", 1, 5, 3)

st.markdown("---")

# =====================================================
# 4. 시스템 자체 평가
# =====================================================
st.subheader("🧐 시스템 전반 평가")

q1 = st.slider("1. 추천 결과가 자연스러웠나요?", 1, 5, 3)
q2 = st.slider("2. 추천 이유를 이해할 수 있었나요?", 1, 5, 3)
q3 = st.slider("3. 추천이 다양했나요?", 1, 5, 3)
q4 = st.slider("4. 예상치 못한 유용한 추천이 있었나요?", 1, 5, 3)
q5 = st.slider("5. 추천 결과가 반복된다고 느꼈나요? (역문항)", 1, 5, 3)
q6 = st.slider("6. 추천 결과에 만족하셨나요?", 1, 5, 3)
q7 = st.slider("7. 전체적으로 시스템을 신뢰하시나요?", 1, 5, 3)
q8 = st.slider("8. 다시 사용 의향이 있나요?", 1, 5, 3)

q9  = st.text_area("✏ 개선되었으면 하는 점")
q10 = st.text_area("💡 가장 좋았던 점")

st.markdown("---")

# =====================================================
# 5. 저장 처리
# =====================================================
if st.button("💾 평가 제출하기", use_container_width=True):

    # 구글시트 연결
    sh = connect_gsheet("MoodFit")
    ws_daily = sh.worksheet("evaluation")

    # 전체 데이터 읽기
    rows = ws_daily.get_all_values()

    # 해당 유저 + 날짜 찾기
    target_row = None
    for i, row in enumerate(rows):
        # row[0] = 날짜, row[1] = 이름
        if row[0] == str(date) and row[1] == user_name:
            target_row = i + 1  # 실제 index
    
    if not target_row:
        st.error("❌ Daily 데이터가 없어 평가를 저장할 수 없습니다.")
        st.info("추천 과정부터 다시 진행해주세요.")
        st.stop()

    # 운동별 평가 저장
    ws_daily.update_cell(target_row, 14, ratings[recommended[0]])
    ws_daily.update_cell(target_row, 15, ratings[recommended[1]])
    ws_daily.update_cell(target_row, 16, ratings[recommended[2]])

    # 시스템 평가 저장
    ws_daily.update_cell(target_row, 17, q1)
    ws_daily.update_cell(target_row, 18, q2)
    ws_daily.update_cell(target_row, 19, q3)
    ws_daily.update_cell(target_row, 20, q4)
    ws_daily.update_cell(target_row, 21, q5)
    ws_daily.update_cell(target_row, 22, q6)
    ws_daily.update_cell(target_row, 23, q7)
    ws_daily.update_cell(target_row, 24, q8)
    ws_daily.update_cell(target_row, 25, q9)
    ws_daily.update_cell(target_row, 26, q10)

    st.success("🎉 평가가 저장되었습니다! 참여해주셔서 감사합니다!")
    st.balloons()
