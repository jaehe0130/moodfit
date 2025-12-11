import streamlit as st
from sheets_auth import connect_gsheet

st.set_page_config(page_title="추천운동 평가", page_icon="📊", layout="centered")
st.title("📊 추천운동 평가")

# =====================================================
# 0. 구글시트 연결 (스프레드시트 객체만 캐시)
# =====================================================
@st.cache_resource
def get_spreadsheet():
    """MoodFit 스프레드시트 객체를 캐시해서 재사용"""
    return connect_gsheet("MoodFit")

def load_daily_rows():
    """
    daily 시트의 전체 데이터를 매번 새로 가져오기.
    👉 추천 직후 방금 저장된 사용자/날짜도 바로 보여야 하므로 캐시 X
    """
    sh = get_spreadsheet()
    ws_daily = sh.worksheet("daily")
    return ws_daily.get_all_values()

# ----------------- daily 시트 데이터 불러오기 -----------------
rows = load_daily_rows()

if not rows or len(rows) < 2:
    st.error("❌ daily 시트에 데이터가 없습니다.")
    st.stop()

header = rows[0]
data = rows[1:]

# =====================================================
# 1. 사용자 / 날짜 선택
# =====================================================

# daily 기준 이름 목록 (2열: 이름, 공백 제거)
user_list = sorted({
    (row[1] or "").strip()
    for row in data
    if len(row) > 1 and (row[1] or "").strip()
})

def get_dates_for_user(user: str):
    """해당 사용자의 날짜 목록만 daily 시트에서 추출 (이름 공백 제거 후 비교)"""
    result = set()
    for row in data:
        if len(row) > 1:
            name_val = (row[1] or "").strip()
            if name_val == user:
                result.add(row[0])   # 날짜는 문자열 그대로 사용
    return sorted(result)

st.subheader("👤 사용자 선택")
selected_user = st.selectbox("사용자를 선택하세요:", ["선택"] + user_list)

if selected_user == "선택":
    st.info("사용자를 먼저 선택해주세요.")
    st.stop()

st.subheader("📅 날짜 선택")
user_dates = get_dates_for_user(selected_user)

if not user_dates:
    st.error("⚠ 해당 사용자의 기록이 없습니다.\n"
             "먼저 컨디션 기록 + 운동 추천을 받은 뒤 평가해주세요.")
    st.stop()

selected_date = st.selectbox("날짜를 선택하세요:", ["선택"] + sorted(user_dates))

if selected_date == "선택":
    st.info("평가할 날짜를 선택해주세요.")
    st.stop()

# =====================================================
# 2. daily 시트에서 해당 사용자+날짜의 추천운동 & 이유 찾기
# =====================================================

# daily 시트 구조 (1-based 기준 가정):
# 11열: 추천운동1, 12열: 추천운동2, 13열: 추천운동3
# 14열: 추천이유1, 15열: 추천이유2, 16열: 추천이유3
# => 0-based index로는 10~12, 13~15

rec1 = rec2 = rec3 = ""
reason1 = reason2 = reason3 = ""

for row in data:
    # 추천운동/이유까지 들어갈 최소 길이: 16
    if len(row) < 16:
        continue

    date_val = row[0]
    name_val = (row[1] or "").strip()

    if date_val == selected_date and name_val == selected_user:
        rec1 = row[10]
        rec2 = row[11]
        rec3 = row[12]
        reason1 = row[13]
        reason2 = row[14]
        reason3 = row[15]
        break

if not rec1 and not rec2 and not rec3:
    st.warning("⚠ 이 날짜에는 저장된 추천운동이 없습니다.\n"
               "추천 페이지에서 먼저 추천을 받아주세요.")
    st.stop()

# 비어 있는 운동 이름은 제외하고 리스트 구성
recommended = []
for rec, reason in [(rec1, reason1), (rec2, reason2), (rec3, reason3)]:
    if rec:  # 운동명이 있는 경우만
        recommended.append({"name": rec, "reason": reason})

# =====================================================
# 3. 추천운동 + 이유 표시
# =====================================================
st.markdown("### 📍 추천받은 운동:")

for item in recommended:
    name = item["name"]
    reason = item["reason"]

    if reason:
        html = (
            f"- **{name}**<br>"
            f"<span style='color:gray;'>이유: {reason}</span>"
        )
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.markdown(f"- **{name}**")

st.markdown("---")

# =====================================================
# 4. 운동별 평가
# =====================================================
st.subheader("📝 추천 운동별 적합도 평가")

ratings = {}
for item in recommended:
    name = item["name"]
    ratings[name] = st.slider(f"'{name}' 운동 적합도 평가", 1, 5, 3)

st.markdown("---")

# =====================================================
# 5. 시스템 전반 평가
# =====================================================
st.subheader("🧐 시스템 전반 평가")

q1 = st.slider("1. 추천 결과가 자연스러웠나요?",             1, 5, 3)
q2 = st.slider("2. 추천 이유를 이해할 수 있었나요?",         1, 5, 3)
q3 = st.slider("3. 추천이 다양했나요?",                     1, 5, 3)
q4 = st.slider("4. 예상치 못한 유용한 추천이 있었나요?",     1, 5, 3)
q5 = st.slider("5. 추천 결과가 반복된다고 느꼈나요? (역문항)", 1, 5, 3)
q6 = st.slider("6. 추천 결과에 만족하셨나요?",               1, 5, 3)
q7 = st.slider("7. 전체적으로 시스템을 신뢰하시나요?",         1, 5, 3)
q8 = st.slider("8. 다시 사용 의향이 있나요?",                1, 5, 3)

q9  = st.text_area("✏ 개선되었으면 하는 점")
q10 = st.text_area("💡 가장 좋았던 점")

st.markdown("---")

# =====================================================
# 6. evaluation 시트에 한 줄로 평가 결과 저장
# =====================================================
if st.button("💾 평가 제출하기", use_container_width=True):

    sh = get_spreadsheet()
    ws_eval = sh.worksheet("evaluation")  # 평가 결과 시트 (비어 있어도 됨)

    # evaluation 시트가 완전 비어있다면, 헤더 한 줄 추가
    eval_rows = ws_eval.get_all_values()
    if not eval_rows:
        ws_eval.append_row([
            "날짜", "이름",
            "추천운동1", "추천운동2", "추천운동3",
            "운동1_평가", "운동2_평가", "운동3_평가",
            "Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8",
            "개선점", "좋았던점"
        ])

    # 운동 이름 순서를 rec1~3 기준으로 맞춰서 저장
    row_to_append = [
        selected_date,          # 날짜 (selectbox에서 선택한 문자열)
        selected_user,          # 이름
        rec1, rec2, rec3,       # 추천운동1~3
        ratings.get(rec1, ""),  # 운동1 평가
        ratings.get(rec2, ""),  # 운동2 평가
        ratings.get(rec3, ""),  # 운동3 평가
        q1, q2, q3, q4, q5, q6, q7, q8,   # 시스템 평가
        q9,                    # 개선점
        q10                    # 좋았던 점
    ]

    ws_eval.append_row(row_to_append)

    st.success("🎉 평가가 저장되었습니다! 감사합니다!")
    st.balloons()
