import streamlit as st

st.set_page_config(
    page_title="MoodFit",
    page_icon="🏋️",
    layout="centered"
)

# ----------------------------
# 화면 중앙 정렬 컨테이너
# ----------------------------
st.markdown("<div style='height:12vh;'></div>", unsafe_allow_html=True)  # 상단 여백

with st.container():
    st.image("assets/home_fitness.jpg", width=350)   # 이미지 크기 조정

    st.markdown("""
    <h1 style="text-align:center; font-size:42px; font-weight:900; margin-top:10px;">
    🏋️ MoodFit
    </h1>

    <p style="text-align:center; font-size:20px; color:#444; margin-top:-10px;">
    감정 기반 개인 맞춤 운동 추천 서비스
    </p>

    <p style='text-align:center; font-size:18px; color:#333; margin-top:25px;'>
    오늘의 감정을 선택하면<br>
    당신에게 딱 맞는 운동 루틴을 추천해드릴게요!
    </p>
    """, unsafe_allow_html=True)

st.markdown("<div style='height:10vh;'></div>", unsafe_allow_html=True)  # 하단 여백

# ----------------------------
# 2초 뒤 자동 페이지 이동
# ----------------------------
time.sleep(2)
switch_page("1_user_info2")  # 확장자 없이 pages 폴더 내 파일 이름만
