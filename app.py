import streamlit as st
import time

st.set_page_config(page_title="MoodFit", page_icon="🏋️", layout="centered")

# 이미지
st.image("assets/home_fitness.jpg", width=350)

# 제목
st.title("MoodFit")

# 2초 대기
time.sleep(2)

# 페이지 이동
st.switch_page("1_user_info2")


