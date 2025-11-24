import streamlit as st
import time

st.set_page_config(
    page_title="MoodFit",
    page_icon="🏋️",
    layout="centered"
)

# ----------------------------
# 이미지 + 텍스트 UI
# ----------------------------
st.markdown("<div style='height:12vh;'></div>", unsafe_allow_html=True)

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image("assets/home_fitness.jpg", width=350)

st.markdown("""
<h1 style="text-align:center; font-size:42px; font-weight:900; margin-top:15px;">
🏋️ MoodFit
</h1>

<p style='text-align:center; font-size:18px; color:#333; margin-top:25px;'>
오늘의 감정을 선택하면<br>
당신에게 딱 맞는 운동 루틴을 추천해드릴게요!
</p>
""", unsafe_allow_html=True)

# ----------------------------
# Auto redirect logic
# ----------------------------
if "redirected" not in st.session_state:
    st.session_state.redirected = True
    time.sleep(2)
    st.rerun()   # <<<<<<<< HERE
else:
    st.switch_page("1_user_info2")
