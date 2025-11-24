import streamlit as st
import time

st.set_page_config(page_title="MoodFit", page_icon="🏋️", layout="centered")

st.title("MoodFit 로딩 중...")

time.sleep(2)
st.switch_page("1_user_info2")   # .py 확장자 X

