import streamlit as st
import pandas as pd
import os

# 페이지 기본 설정
st.set_page_config(
    page_title="회원 등록",
    layout="centered",
    page_icon="🧍"
)

# -------------------------
# 헤더 디자인
# -------------------------
st.markdown("""
    <h1 style='text-align:center; font-weight:700;'>
        🧍 회원 등록
    </h1>
    <p style="text-align:center; color:gray; margin-top:-10px;">
        회원 정보를 등록하면 개인 맞춤 운동 추천이 더 정확해져요!
    </p>
""", unsafe_allow_html=True)

csv_path = "users.csv"

# -----------------------------------
# 기본 정보 입력
# -----------------------------------
st.markdown("## 📝 기본 정보")

col1, col2 = st.columns(2)
with col1:
    name = st.text_input("이름", placeholder="홍길동")
with col2:
    gender = st.selectbox("성별", ["남성", "여성"])

col3, col4 = st.columns(2)
with col3:
    age = st.number_input("나이 (만나이)", min_value=10, max_value=100, value=25)
with col4:
    activity = st.selectbox("평소 활동량", ["낮음", "보통", "높음"])

col5, col6 = st.columns(2)
with col5:
    height = st.text_input("키 (cm)")
    if height.isdigit():
        height = int(height)
with col6:
    weight = st.text_input("몸무게 (kg)")
    if weight.isdigit():
        weight = int(weight)

st.markdown("---")

# -----------------------------------
# 부상 이력 입력
# -----------------------------------
st.markdown("## 🩹 부상 이력")

injury_status = st.radio("부상 여부", ["없음", "있음"], horizontal=True)

injury_detail = ""

if injury_status == "있음":
    common_injuries = ["무릎", "허리", "어깨", "발목", "손목", "기타"]
    selected_parts = st.multiselect(
        "부상 부위를 선택하세요",
        common_injuries
    )

    if "기타" in selected_parts:
        other_injury = st.text_input("기타 부상 입력", placeholder="예: 햄스트링, 종아리 등")
        if other_injury.strip():
            selected_parts.append(other_injury)

    injury_detail = ", ".join(selected_parts) if selected_parts else "있음"

st.markdown("---")

# -----------------------------------
# 인코딩 안전 읽기 함수
# -----------------------------------
def read_csv_robust(path: str) -> pd.DataFrame:
    encodings_to_try = ["utf-8-sig", "utf-8", "cp949"]
    last_err = None
    for enc in encodings_to_try:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as e:
            last_err = e
    raise last_err

# -----------------------------------
# 등록 버튼
# -----------------------------------
st.markdown("<br>", unsafe_allow_html=True)

if st.button("💾 회원 등록 완료", use_container_width=True):
    if name.strip() == "":
        st.warning("⚠️ 이름을 입력해주세요.")
    else:
        new_data = pd.DataFrame({
            "이름": [name],
            "나이": [age],
            "성별": [gender],
            "키(cm)": [height],
            "몸무게(kg)": [weight],
            "활동량": [activity],
            "부상 이력": [injury_status],
            "부상 상세": [injury_detail]
        })

        # CSV 파일이 존재하는 경우
        if os.path.exists(csv_path):
            try:
                existing = read_csv_robust(csv_path)
            except Exception as e:
                st.error(f"❌ CSV 인코딩 오류 발생: {e}")
                st.info("파일을 엑셀로 연 뒤 '다른 이름으로 저장 → CSV UTF-8'로 저장하면 해결돼요!")
                st.stop()

            # 중복 회원 체크
            if "이름" in existing.columns and name in existing["이름"].astype(str).values:
                st.warning("⚠️ 이미 등록된 회원입니다.")
            else:
                updated = pd.concat([existing, new_data], ignore_index=True)
                updated.to_csv(csv_path, index=False, encoding="utf-8-sig")
                st.success("🎉 회원 등록이 완료되었습니다!")
                st.balloons()

        else:
            # 새 파일 생성
            new_data.to_csv(csv_path, index=False, encoding="utf-8-sig")
            st.success("🎉 회원 등록이 완료되었습니다!")
