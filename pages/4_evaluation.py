import streamlit as st
from sheets_auth import connect_gsheet
from datetime import datetime

st.write("✅ evaluation.py loaded at:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
st.write("✅ version tag:", "EVAL-2025-12-30-v1")
st.divider()
st.set_page_config(page_title="추천운동 평가", page_icon="📊", layout="centered")
st.title("📊 추천운동 평가 (논문용 설문)")

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
    if rec:
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
# 4. 운동별 적합도 평가 (논문 핵심)
# =====================================================
st.subheader("📝 추천 운동별 적합도 평가 (1~5점)")

ratings = {}
for item in recommended:
    name = item["name"]
    ratings[name] = st.slider(f"'{name}' 운동 적합도", 1, 5, 3)

st.markdown("---")

# =====================================================
# 5. 시스템 전반 평가 (논문용 핵심 5~6문항)
# 평가 페이지 (논문 실험용)

# =====================================================
st.subheader("🧐 시스템 전반 평가 (논문용)")

# (핵심) 개인화/적합도
q_fit = st.slider("1. 추천 결과가 오늘 내 컨디션(감정/수면/스트레스/시간/날씨)에 전반적으로 적합했나요?", 1, 5, 3)

# (핵심) 설명가능성: 이해/설득력
q_explain_understand = st.slider("2. 추천 이유를 이해하기 쉬웠나요?", 1, 5, 3)
q_explain_convince   = st.slider("3. 추천 이유가 납득/설득력 있었나요?", 1, 5, 3)

# (핵심) 만족/재사용 의향
q_satis = st.slider("4. 추천 결과에 전반적으로 만족하셨나요?", 1, 5, 3)
q_reuse = st.slider("5. 향후에도 이 추천 시스템을 다시 사용할 의향이 있나요?", 1, 5, 3)

# (선택) 정성 피드백: 논문 논의/한계에 도움
q_improve = st.text_area("✏ 개선되었으면 하는 점 (선택)")
q_best    = st.text_area("💡 가장 좋았던 점 (선택)")

st.markdown("---")

# =====================================================
# 6. evaluation 시트에 한 줄로 평가 결과 저장
# =====================================================
if st.button("💾 평가 제출하기", use_container_width=True):

    sh = get_spreadsheet()
    ws_eval = sh.worksheet("evaluation")

    # evaluation 시트가 비어있다면, 논문용 헤더 생성
    eval_rows = ws_eval.get_all_values()
    if not eval_rows:
        ws_eval.append_row([
            "날짜", "이름",
            "추천운동1", "추천운동2", "추천운동3",
            "운동1_평가", "운동2_평가", "운동3_평가",
            "Q_fit(개인화적합)", "Q_explain_understand(이해)", "Q_explain_convince(설득)",
            "Q_satis(만족)", "Q_reuse(재사용의향)",
            "개선점", "좋았던점"
        ])

    row_to_append = [
        selected_date,
        selected_user,
        rec1, rec2, rec3,
        ratings.get(rec1, ""),
        ratings.get(rec2, ""),
        ratings.get(rec3, ""),
        q_fit, q_explain_understand, q_explain_convince,
        q_satis, q_reuse,
        q_improve,
        q_best
    ]

    ws_eval.append_row(row_to_append)
    st.success("🎉 평가가 저장되었습니다! 감사합니다!")
    st.balloons()
