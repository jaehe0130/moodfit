import streamlit as st

st.set_page_config(page_title="MoodFit", page_icon="🏋️", layout="centered")

st.markdown("<div style='height:12vh;'></div>", unsafe_allow_html=True)

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image("assets/home_fitness.jpg", width=350)

st.markdown("""
<h1 style="text-align:center; font-size:42px; font-weight:900; margin-top:15px;">
🏋️ MoodFit
</h1>
""", unsafe_allow_html=True)

# ---- JS Redirect (2초 뒤 이동)
st.markdown("""
<script>
setTimeout(function() {
    window.location.href = "/1_user_info2";
}, 2000);
</script>
""", unsafe_allow_html=True)

