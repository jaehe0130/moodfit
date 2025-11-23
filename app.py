import streamlit as st
import time

st.set_page_config(
    page_title="MoodFit",
    page_icon="🏋️",
    layout="centered"
)

# ----------------------------
# 상단 여백 (중앙 배치용)
# ----------------------------
st.markdown("<div style='height:12vh;'></div>", unsafe_allow_html=True)

# ----------------------------
# 이미지 중앙 정렬
# ----------------------------
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image("assets/home_fitness.jpg", width=350)

# ----------------------------
# 텍스트
# ----------------------------
st.markdown("""
<h1 style="text-align:center; font-size:42px; font-weight:900; margin-top:15px;">
🏋️ MoodFit
</h1>

<p style="text-align:center; font-size:20px; color:#444; margin-top:-10px;">
감정 기반 개인 맞춤 운동 추천 서비스
</p>

<p style="text-align:center; font-size:18px; color:#333; margin-top:25px;">
오늘의 감정을 선택하면<br>
당신에게 딱 맞는 운동 루틴을 추천해드릴게요!
</p>
""", unsafe_allow_html=True)

# ----------------------------
# 자동 페이지 이동 (2초 후)
# ----------------------------
if "start_redirect" not in st.session_state:
    st.session_state.start_redirect = True
    time.sleep(2)
    st.switch_page("1_user_info2")
