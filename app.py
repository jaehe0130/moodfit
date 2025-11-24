import streamlit as st

st.set_page_config(
    page_title="MoodFit",
    page_icon="🏋️",
    layout="centered"
)

# ====== 중앙 정렬 전체 컨테이너 ======
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image("assets/home_fitness.jpg", width=340)

    st.markdown(
        """
        <h1 style="text-align:center; font-size:42px; font-weight:900; margin-top:10px;">
            🏋️ MoodFit
        </h1>
        <p style="text-align:center; font-size:18px; color:#666; margin-top:-10px;">
            감정 기반 개인 맞춤 운동 추천 서비스
        </p>
        """,
        unsafe_allow_html=True
    )

    # 버튼 중앙
    if st.button("👉 시작하기", use_container_width=True):
        st.switch_page("1_user_info2.py")

