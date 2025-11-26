# -*- coding: utf-8 -*-
import os, re, json, requests
import pandas as pd
import numpy as np
import streamlit as st
from openai import OpenAI
from datetime import datetime, date
from sheets_auth import connect_gsheet

st.set_page_config(page_title="운동 추천", page_icon="🏋️", layout="centered")

st.markdown("""
<h1 style='text-align:center; font-weight:700;'>🏋️ 맞춤 운동 추천</h1>
<p style="text-align:center; color:gray; margin-top:-10px;">
오늘의 컨디션 + 날씨 기반 Top3 운동 추천
</p>
""", unsafe_allow_html=True)


# ========================= WORKOUT CSV =========================
WORKOUT_CSV = "workout.csv"

def read_csv(path):
    for enc in ["utf-8-sig", "utf-8", "cp949"]:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            pass
    st.error("❌ workout.csv 읽기 실패")
    st.stop()


def split_tags(x):
    if pd.isna(x):
        return []
    return [s.strip() for s in str(x).split(",") if s.strip()]


def load_workouts():
    df = read_csv(WORKOUT_CSV)
    if "운동목적" not in df.columns:
        st.error("❌ workout.csv 에 '운동목적' 컬럼이 없습니다.")
        st.stop()
    df["운동목적_list"] = df["운동목적"].apply(split_tags)
    return df

# 전역에서 한 번만 로드
workouts_df = load_workouts()


# ========================= 날씨 조회 =========================
def get_weather(city):
    key = os.getenv("WEATHER_API_KEY")
    if not key:
        return "unknown", 0.0

    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={key}&lang=kr&units=metric"
    try:
        res = requests.get(url).json()
        return res["weather"][0]["main"].lower(), res["main"]["temp"]
    except Exception:
        return "unknown", 0.0


# ========================= LLM JSON 파싱 =========================
def parse_json(text):
    text = re.sub(r"```(json)?", "", text).strip("` ")
    return json.loads(text)


# ========================= STREAMLIT UI =========================
city = st.text_input("🌍 도시명", "Seoul")
weather, temp = get_weather(city)
st.info(f"현재날씨: {weather}, {temp:.1f}°C")


# ========================= LOAD SHEETS =========================
sh = connect_gsheet("MoodFit")
ws_users = sh.worksheet("users")
ws_daily = sh.worksheet("daily")

# === RAW 데이터 조회 후 DataFrame 변환 (빈 행 대비 처리) ===
daily_raw = ws_daily.get_all_values()   # 전체 값 가져오기
if len(daily_raw) < 2:
    st.error("❌ daily 시트에 데이터가 부족합니다. 최소 1개의 데이터 행이 필요합니다.")
    st.stop()

daily_df = pd.DataFrame(daily_raw[1:], columns=daily_raw[0])  # 첫 row는 컬럼 헤더
users_df = pd.DataFrame(ws_users.get_all_records())

# === 날짜 변환 ===
if "날짜" not in daily_df.columns:
    st.error("❌ daily 시트에 '날짜' 헤더가 없습니다. 정확히 '날짜' 로 입력해주세요.")
    st.stop()

daily_df["날짜"] = pd.to_datetime(daily_df["날짜"], errors="coerce").dt.date


# ========================= 사용자 선택 =========================
st.markdown("### 👤 사용자 선택")
user_name = st.selectbox("오늘 추천 받을 사용자", users_df["이름"].unique().tolist())

user_daily = daily_df[daily_df["이름"] == user_name]
if user_daily.empty:
    st.error("❌ 선택한 사용자의 daily 데이터가 없습니다.")
    st.stop()

pick_date = st.selectbox("추천 기준 날짜", sorted(user_daily["날짜"].unique(), reverse=True))
daily_row = user_daily[user_daily["날짜"] == pick_date].iloc[0]
pick_date_dt = pick_date  # 그대로 저장

# daily 시트에서 이 행이 몇 번째 row인지 계산 (시트 row 번호)
mask = (daily_df["이름"] == user_name) & (daily_df["날짜"] == pick_date)
row_idx = daily_df[mask].index[0]      # 0-based
sheet_row = row_idx + 2               # 시트는 1행 헤더라 +2


# users 시트에서 추가 정보 가져오기
user_row = users_df[users_df["이름"] == user_name].iloc[0]
place_pref = user_row.get("운동장소선호", "상관없음")
equip_raw = user_row.get("보유장비", "")
equip_list = [s.strip() for s in str(equip_raw).split(",") if s.strip()]


# ========================= RULE 기반 후보군 =========================
purpose = daily_row.get("운동목적", "")
target_intensity = "중강도"  # 기본값 placeholder

if purpose:
    candidates = workouts_df[workouts_df["운동목적_list"].apply(lambda x: purpose in x)]
    if candidates.empty:
        st.warning("⚠️ 해당 운동목적에 맞는 운동이 없어 전체 운동에서 추천합니다.")
        candidates = workouts_df.copy()
else:
    st.warning("⚠️ daily 시트에 '운동목적' 값이 비어 있습니다. 전체 운동에서 추천합니다.")
    candidates = workouts_df.copy()

st.markdown("---")


# ========================= 추천 버튼 =========================
if st.button("🤖 Top3 추천 받기", use_container_width=True):

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    rule_candidates = [
        {
            "운동명": r["운동명"],
            "운동목적": r["운동목적"],
            "운동강도": r.get("운동강도", ""),
        }
        for _, r in candidates.iterrows()
    ]

    system_prompt = """
당신은 운동 추천 전문가입니다.
사용자의 컨디션, 날씨, 목표 목적을 고려하여 운동 3개를 추천하고 이유를 작성하세요.
서로 다른 유형의 운동을 선택하세요.
JSON만 출력하세요.
[중요 규칙]
1) Top3는 서로 다른 유형/계열로 다양해야 합니다.
   - 예: 요가/스트레칭 계열만 2개 이상 포함되면 안 됩니다.
   - 가능하면 유산소/근력/유연성/균형 등 성격이 다른 운동을 섞어주세요.
2) 사용자 정적정보(users 시트)를 반드시 고려하세요.
   - 나이/성별/키/몸무게/활동량/부상 이력/부상 상세 등
3) 오늘의 동적 상태(daily 시트)를 종합해
   - 수면시간, 스트레스, 운동가능시간(분), 감정, 운동목적
   현실적으로 수행 가능한 운동을 우선하세요.
4) 운동 장소/날씨:
   - 비/눈이거나 실내 선호면 실내/홈트 중심으로 추천하세요.
   - 사용자 장소 권장: {place_pref}
5) 보유 장비:
   - 사용자가 가진 장비로 가능한 운동을 우선하세요.
   - 보유장비: {", ".join(equip_list) if equip_list else "없음/미기재"}
6) JSON 형식 외 텍스트는 절대 출력하지 마세요.

반드시 JSON만 출력합니다.
형식={
"top3":[
{"rank":1,"운동명":"", "이유":""},
{"rank":2,"운동명":"", "이유":""},
{"rank":3,"운동명":"", "이유":""}
]}
"""

    with st.spinner("추천 생성 중..."):
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(rule_candidates, ensure_ascii=False)},
            ],
            temperature=0.6,
        )

        raw = resp.choices[0].message.content
        try:
            top3 = parse_json(raw)["top3"]
        except Exception as e:
            st.error(f"❌ JSON 파싱 실패: {e}")
            st.text(raw)
            st.stop()

    if not top3 or len(top3) < 1:
        st.error("❌ 추천 생성 실패. 다시 시도하세요.")
        st.stop()

    # ========================= daily 시트에 추천 결과 저장 =========================
    # daily 시트 헤더에서 추천 관련 컬럼 위치 찾기
    headers = daily_raw[0]  # ["이름","날짜","운동목적",..., "추천운동1", ...]

    def col_idx(col_name: str) -> int:
        """해당 컬럼명이 없으면 에러를 띄우고, 있으면 1-based column index 반환"""
        if col_name not in headers:
            st.error(f"❌ daily 시트에 '{col_name}' 컬럼이 없습니다. 헤더에 추가해 주세요.")
            st.stop()
        return headers.index(col_name) + 1

    c_w1 = col_idx("추천운동1")
    c_w2 = col_idx("추천운동2")
    c_w3 = col_idx("추천운동3")
    c_r1 = col_idx("추천이유1")
    c_r2 = col_idx("추천이유2")
    c_r3 = col_idx("추천이유3")

    # 각 칸에 값 입력
    ws_daily.update_cell(sheet_row, c_w1, top3[0]["운동명"] if len(top3) > 0 else "")
    ws_daily.update_cell(sheet_row, c_w2, top3[1]["운동명"] if len(top3) > 1 else "")
    ws_daily.update_cell(sheet_row, c_w3, top3[2]["운동명"] if len(top3) > 2 else "")
    ws_daily.update_cell(sheet_row, c_r1, top3[0]["이유"] if len(top3) > 0 else "")
    ws_daily.update_cell(sheet_row, c_r2, top3[1]["이유"] if len(top3) > 1 else "")
    ws_daily.update_cell(sheet_row, c_r3, top3[2]["이유"] if len(top3) > 2 else "")

    st.success("🎉 daily 시트에 추천 결과 저장 완료!")

    st.markdown("## 🏅 추천 Top3")
    for item in top3:
        st.write(f"### #{item['rank']} {item['운동명']}")
        st.write(item["이유"])

    if st.button("📊 평가하기"):
        st.session_state["recommended_workouts"] = [w["운동명"] for w in top3]
        st.switch_page("4_evaluation.py")
