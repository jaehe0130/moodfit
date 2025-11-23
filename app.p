import streamlit as st
import time

st.set_page_config(
    page_title="MoodFit",
    page_icon="🏋️",
    layout="centered"
)

# ----------------------------
# Custom CSS (배경 + 애니메이션)
# ----------------------------
st.markdown("""
    <style>
        body {
            background: linear-gradient(135deg, #d2faff, #ffffff);
        }
        .fade-in {
            animation: fadeIn 1.4s ease-in-out;
        }
        @keyframes fadeIn {
            0% { opacity: 0; transform: translateY(10px); }
            100% { opacity: 1; transform: translateY(0); }
        }
        h1 {
            text-align: center;
            font-size: 48px;
            font-weight: 900;
            margin-bottom: -5px;
        }
        .subtitle {
            text-align: center;
            font-size: 20px;
            color: #555;
            margin-bottom: 25px;
        }
    </style>
""", unsafe_allow_html=True)

# ----------------------------
# 제목 + 설명 (위)
# ----------------------------
st.markdown("""
    <h1 class="fade-in">🏋️ MoodFit</h1>
    <p class="subtitle fade-in">감정 기반 개인 맞춤 운동 추천 서비스</p>
""", unsafe_allow_html=True)

# ----------------------------
# 이미지 (아래)
# ----------------------------
st.image("assets/home_fitness.jpg", use_column_width=True)

# ----------------------------
# 안내 문장
# ----------------------------
st.markdown("""
    <p class='fade-in' style='text-align:center; font-size:18px; color:#333; margin-top:20px;'>
        오늘의 감정을 선택하면<br>
        당신에게 딱 맞는 운동 루틴을 추천해드릴게요!
    </p>
""", unsafe_allow_html=True)

# ----------------------------
# 2초 후 자동 이동
# ----------------------------
time.sleep(2)
st.switch_page("pages/1_user_info2.py")
