import streamlit as st
import pandas as pd
import os
from datetime import datetime

st.set_page_config(page_title="추천운동 평가", page_icon="📊", layout="centered")
st.title("📊 추천운동 평가")

# -----------------------
# 추천 운동 후보 표시
# -----------------------
recommended = st.session_state.get("recommended_workouts", ["운동1", "운동2", "운동3"])

st.markdown("### 📍 오늘 추천받은 운동:")
for r in recommended:
    st.markdown(f"- **{r}**")

st.markdown("---")

# -----------------------
# 운동 추천 적합도 평가
# -----------------------
st.subheader("📝 추천 운동별 적합도 평가")
ratings = {}
for r in recommended:
    ratings[r] = st.slider(f"'{r}' 운동 적합도 평가", 1, 5, 3)

st.markdown("---")

# -----------------------
# 시스템 전체 평가 문항
# -----------------------
st.subheader("🧐 시스템 전반 평가")

q1 = st.slider("1. 추천 결과가 자연스러웠나요?", 1, 5, 3)
q2 = st.slider("2. 추천 이유를 이해할 수 있었나요?", 1, 5, 3)
q3 = st.slider("3. 추천이 다양하게 제시되었나요?", 1, 5, 3)
q4 = st.slider("4. 예상치 못한 유용한 추천이 있었나요?", 1, 5, 3)
q5 = st.slider("5. 추천 결과가 반복된다고 느꼈나요? (역문항)", 1, 5, 3)
q6 = st.slider("6. 추천 결과에 만족하셨나요?", 1, 5, 3)
q7 = st.slider("7. 전체적으로 시스템을 신뢰하시나요?", 1, 5, 3)
q8 = st.slider("8. 다시 사용할 의향이 있나요?", 1, 5, 3)

st.markdown("### ✏ 개선되었으면 하는 점은 무엇인가요?")
q9 = st.text_area("")

st.markdown("### 💡 가장 좋았던 점은 무엇인가요?")
q10 = st.text_area(" ")

st.markdown("---")

# -----------------------
# 저장 버튼
# -----------------------
if st.button("💾 평가 제출하기", use_container_width=True):

    result = {
        "timestamp": datetime.now(),
        "추천운동1": recommended[0],
        "추천운동2": recommended[1],
        "추천운동3": recommended[2],
        **{f"{r}_점수": ratings[r] for r in recommended},
        "Q1": q1, "Q2": q2, "Q3": q3, "Q4": q4,
        "Q5(역문항)": q5, "Q6": q6, "Q7": q7, "Q8": q8,
        "개선점": q9, "좋았던점": q10,
    }

    df = pd.DataFrame([result])

    if os.path.exists("evaluation_results.csv"):
        df.to_csv("evaluation_results.csv", mode="a", header=False, index=False)
    else:
        df.to_csv("evaluation_results.csv", index=False)

    st.success("🎉 평가가 저장되었습니다! 참여해주셔서 감사합니다!")
    st.balloons()
