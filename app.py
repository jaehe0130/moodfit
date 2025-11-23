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
            animation: fadeIn 1.6s ease-in-out;
        }
        @keyframes fadeIn {
            0% { opacity: 0; transform: translateY(10px); }
            100% { opacity: 1; transform: translateY(0); }
        }
        .hero-img {
            width: 70%;
            display: block;
            margin: 0 auto;
            border-radius: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }
    </style>
""", unsafe_allow_html=True)

# ----------------------------
# 화면 구성
# ----------------------------

st.markdown("""
    <div class='fade-in'>
        <h1 style='text-align:center; font-size:45px; font-weight:800;'>
            🏋️ MoodFit
        </h1>
        <p style='text-align:center; font-size:22px; color:#555; margin-top:-15px;'>
            당신의 감정에 가장 잘 맞는 운동을 추천해주는 서비스
        </p>
    </div>
""", unsafe_allow_html=True)

# 운동 이미지 (Unsplash)
st.markdown("""
    <img src="https://images.unsplash.com/photo-1583454110558-7125c8b4f5bb?auto=format&fit=crop&w=1200&q=80"
         class="hero-img fade-in">
""", unsafe_allow_html=True)

st.markdown("""
    <p style='text-align:center; color:#444; font-size:18px; margin-top:20px;' class='fade-in'>
        감정을 기록하고, 당신에게 딱 맞는 운동 루틴을 만나보세요!
    </p>
""", unsafe_allow_html=True)

# 3초 후 자동 이동
time.sleep(3)
st.switch_page("pages/1_user_info2.py")
