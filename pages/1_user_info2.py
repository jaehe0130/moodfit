import streamlit as st
import pandas as pd
from sheets_auth import connect_gsheet

sh = get_spreadsheet()
st.write("📄 Spreadsheet URL:", sh.url)
st.write("📑 Worksheets:", [ws.title for ws in sh.worksheets()])

# daily 시트 최근 3줄 찍어보기
try:
    ws_daily = sh.worksheet("daily")
    daily_rows = ws_daily.get_all_values()
    st.write("🧪 daily 마지막 3줄:", daily_rows[-3:])
except Exception as e:
    st.write("daily 시트 접근 에러:", e)

# users 시트도 확인
try:
    ws_users = sh.worksheet("users")
    users_rows = ws_users.get_all_values()
    st.write("🧪 users 전체:", users_rows)
except Exception as e:
    st.write("users 시트 접근 에러:", e)


# 페이지 기본 설정
st.set_page_config(
    page_title="회원 등록",
    layout="centered",
    page_icon="🧍"
)

st.markdown("""
    <h1 style='text-align:center; font-weight:700;'>
        🧍 회원 등록
    </h1>
    <p style="text-align:center; color:gray; margin-top:-10px;">
        회원 정보를 등록하면 개인 맞춤 운동 추천이 더 정확해져요!
    </p>
""", unsafe_allow_html=True)

# =========================
# 🔌 Google Sheet 연결 (캐시)
# =========================
@st.cache_resource
def get_spreadsheet():
    """MoodFit 스프레드시트 객체를 캐시해서 재사용"""
    return connect_gsheet("MoodFit")

@st.cache_data
def load_existing_names():
    """
    이미 등록된 이름 목록을 캐시해서 재사용.
    첫 행이 헤더라고 가정하고 [1:]로 내용만 사용.
    """
    sh = get_spreadsheet()
    ws = sh.sheet1
    names = ws.col_values(1)
    if len(names) <= 1:
        return []
    return names[1:]

# 스프레드시트/워크시트 객체 (이건 네트워크 호출 아님)
sh = get_spreadsheet()
ws = sh.sheet1   # 첫 시트

# =========================
# 📝 기본 정보
# =========================
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
with col6:
    weight = st.text_input("몸무게 (kg)")

# =========================
# 🔁 이름 중복 체크 (필요할 때만 시트 조회)
# =========================
name = name.strip()
is_duplicate = False
suggested_name = None
existing_names = []

if name:
    # 이름이 실제로 입력된 경우에만 시트에서 이름 목록을 로드
    existing_names = load_existing_names()

    if name in existing_names:
        is_duplicate = True
        # 같은 이름이 이미 있으면, 추천 이름 하나 만들어서 안내
        base = name
        i = 2
        candidate = f"{base}_{i}"
        while candidate in existing_names:
            i += 1
            candidate = f"{base}_{i}"
        suggested_name = candidate

        st.error(
            f"⚠ 이미 등록된 이름입니다. 나중에 운동 추천에서 헷갈리지 않도록, "
            f"다른 이름(별명)을 사용해주세요.\n\n"
            f"예시: **{suggested_name}**"
        )

st.markdown("---")

# =========================
# 🩹 부상 이력
# =========================
st.markdown("## 🩹 부상 이력")

injury_status = st.radio("부상 여부", ["없음", "있음"], horizontal=True)
injury_detail = ""

if injury_status == "있음":
    common_injuries = ["무릎", "허리", "어깨", "발목", "손목", "기타"]
    selected_parts = st.multiselect("부상 부위를 선택하세요", common_injuries)
    if "기타" in selected_parts:
        other = st.text_input("기타 부상 입력", placeholder="예: 햄스트링 등")
        if other.strip():
            selected_parts.append(other)
    injury_detail = ", ".join(selected_parts) if selected_parts else "있음"

st.markdown("<br>", unsafe_allow_html=True)

# =========================
# 💾 회원 등록 버튼
# =========================
if st.button("💾 회원 등록 완료", use_container_width=True):
    # 이름 미입력
    if not name:
        st.warning("⚠ 이름을 입력해주세요.")
        st.stop()

    # (안전장치) 버튼 클릭 시에도 혹시 모를 중복 체크를 위해 한 번 더 확인 가능
    # 단, load_existing_names는 캐시되어 있어서 실제 구글시트 호출은 거의 없음
    if not existing_names:
        existing_names = load_existing_names()

    if name in existing_names:
        # 위에서 이미 is_duplicate 계산했지만, 혹시 흐름상 누락된 경우를 대비한 이중 방어
        is_duplicate = True
        if not suggested_name:
            base = name
            i = 2
            candidate = f"{base}_{i}"
            while candidate in existing_names:
                i += 1
                candidate = f"{base}_{i}"
            suggested_name = candidate

    # 이름 중복이면 저장 막고 안내
    if is_duplicate:
        if suggested_name:
            st.warning(
                f"⚠ 이미 등록된 이름입니다. 예를 들어 **{suggested_name}** 처럼 "
                f"다른 이름(별명)을 입력한 뒤 다시 '회원 등록 완료' 버튼을 눌러주세요."
            )
        else:
            st.warning(
                "⚠ 이미 등록된 이름입니다. 나중에 운동 추천에서 헷갈리지 않도록, "
                "다른 이름(별명)을 사용해주세요."
            )
        st.stop()

    # 새 회원 행 생성
    new_row = [
        name, age, gender, height, weight, activity,
        injury_status, injury_detail
    ]

    ws.append_row(new_row)

    # 새 회원이 추가되었으므로 이름 캐시를 갱신
    load_existing_names.clear()

    st.success("🎉 회원 등록이 완료되었습니다!")
    st.balloons()
    st.switch_page("pages/2_daily_info2.py")
