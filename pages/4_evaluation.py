import streamlit as st
from datetime import datetime
from sheets_auth import connect_gsheet

st.set_page_config(page_title="추천운동 평가", page_icon="📊", layout="centered")
st.title("📊 추천운동 평가")

# =====================================================
# 0. 구글시트 연결
# =====================================================
sh = connect_gsheet("MoodFit")
ws_daily = sh.worksheet("daily")

rows = ws_daily.get_all_values()
header = rows[0]
data = rows[1:]

# 유저 목록 추출
user_list = sorted(list({row[1] for row in data if len(row) > 1 and row[1]}))

# 날짜 목록 추출 (해당 유저 선택 후 사용)
def get_dates_for_user(user):
    return sorted([row[0] for row in data if len(row) > 1 and row[1] == user])


# =====================================================
# 1. 사용자 선택
# =====================================================
st.subheader("👤 사용자 선택")
selected_user = st.selectbox("사용자를 선택하세요:", ["선택"] + user_list)

if selected_user == "선택":
    st.info("사용자를 먼저 선택해주세요.")
    st.stop()

# =====================================================
# 2. 날짜 선택
# =====================================================
st.subheader("📅 날짜 선택")

user_dates = get_dates_for_user(selected_user)

if not user_dates:
    st.error("⚠ 해당 사용자의 기록이 없습니다.")
    st.stop()

selected_date = st.selectbox("날짜를 선택하세요:", ["선택"] + user_dates)

if selected_date == "선택":
    st.info("평가할 날짜를 선택해주세요.")
    st.stop()

# =====================================================
# 3. Daily 시트에서 해당 row 찾기 (운동 + 이유 같이 가져오기)
# =====================================================
target_row = None
rec1 = rec2 = rec3 = ""
reason1 = reason2 = reason3 = ""

# data는 header 제외한 부분, 실제 시트 row 번호는 index + 1 (header 때문에 +1)
for i, row in enumerate(data, start=1):
    # row 최소 길이 체크
    if len(row) < 14:
        continue

    # 0열: 날짜, 1열: 이름
    if row[0] == selected_date and row[1] == selected_user:
        target_row = i + 1  # 실제 Google Sheet row 번호 (1-based 기준)

        # 1-based 열 번호 기준:
        # 11: 추천운동1, 12: 추천운동2, 13: 추천운동3
        # 14: 추천이유1, 15: 추천이유2, 16: 추천이유3
        # → 0-based index: 10,11,12 / 13,14,15
        rec1 = row[10]
        rec2 = row[11]
        rec3 = row[12]

        reason1 = row[13] if len(row) > 13 else ""
        reason2 = row[14] if len(row) > 14 else ""
        reason3 = row[15] if len(row) > 15 else ""
        break

if target_row is None:
    st.error("❌ Daily 데이터에서 해당 사용자/날짜 기록을 찾을 수 없습니다.")
    st.stop()

# 운동 이름 + 이유를 함께 관리
recommended = [
    {"name": rec1, "reason": reason1},
    {"name": rec2, "reason": reason2},
    {"name": rec3, "reason": reason3},
]

# 추천운동이 없는 경우 (이름이 하나라도 비어 있으면)
if not all([rec1, rec2, rec3]):
    st.warning("⚠ 이 날짜에는 저장된 추천운동이 없습니다.\n추천 페이지에서 먼저 추천을 받아주세요.")
    st.stop()

# =====================================================
# 4. 추천 운동 + 이유 표시
# =====================================================
st.markdown("### 📍 추천받은 운동:")

for item in recommended:
    name = item["name"]
    reason = item["reason"]

    if reason:
        # 운동명 + 이유를 한 줄/두 줄로 예쁘게 표시
        st.markdown(
            f"- **{name}**<br>"
            f"<span style='color:gray;'>이유: {reason}</span>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(f"- **{name}**")

st.markdown("---")

# =====================================================
# 5. 운동별 평가
# =====================================================
st.subheader("📝 추천 운동별 적합도 평가")

# 슬라이더는 운동 이름 기준으로 평가
ratings = {}
for item in recommended:
    name = item["name"]
    ratings[name] = st.slider(f"'{name}' 운동 적합도 평가", 1, 5, 3)

st.markdown("---")

# =====================================================
# 6. 시스템 전반 평가
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
# 7. 저장
# =====================================================
if st.button("💾 평가 제출하기", use_container_width=True):

    ws_eval = sh.worksheet("evaluation")

    # 운동별 평가 저장 (evaluation 시트에서 14~16열에 매핑한다고 가정)
    ws_eval.update_cell(target_row, 14, ratings[rec1])
    ws_eval.update_cell(target_row, 15, ratings[rec2])
    ws_eval.update_cell(target_row, 16, ratings[rec3])

    # 시스템 평가 저장 (17~26열에 매핑)
    ws_eval.update_cell(target_row, 17, q1)
    ws_eval.update_cell(target_row, 18, q2)
    ws_eval.update_cell(target_row, 19, q3)
    ws_eval.update_cell(target_row, 20, q4)
    ws_eval.update_cell(target_row, 21, q5)
    ws_eval.update_cell(target_row, 22, q6)
    ws_eval.update_cell(target_row, 23, q7)
    ws_eval.update_cell(target_row, 24, q8)
    ws_eval.update_cell(target_row, 25, q9)
    ws_eval.update_cell(target_row, 26, q10)

    st.success("🎉 평가가 저장되었습니다! 감사합니다!")
    st.balloons()
