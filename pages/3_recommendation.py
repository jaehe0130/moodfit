# recommend.py
# -*- coding: utf-8 -*-
import os
import re
import json
import requests
import pandas as pd
import numpy as np
import streamlit as st
from openai import OpenAI
from datetime import date, datetime

from sheets_auth import connect_gsheet   # 🔥 구글 시트 연결 함수 (별도 파일)

# =========================
# 0) 기본 설정
# =========================
st.set_page_config(
    page_title="운동 추천",
    layout="centered",
    page_icon="🏋️"
)

st.markdown("""
    <h1 style='text-align:center; font-weight:700;'>
        🏋️ 맞춤 운동 추천
    </h1>
    <p style="text-align:center; color:gray; margin-top:-10px;">
        오늘의 컨디션 + 날씨를 바탕으로 가장 잘 맞는 운동을 추천해드려요!
    </p>
""", unsafe_allow_html=True)

WORKOUT_CSV = "workout.csv"


# =========================
# 1) CSV 인코딩 안전 읽기 (workout용)
# =========================
def read_csv_robust(path: str) -> pd.DataFrame:
    encodings_to_try = ["utf-8-sig", "utf-8", "cp949"]
    last_err = None
    for enc in encodings_to_try:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as e:
            last_err = e
    raise last_err


# =========================
# 1-1) JSON 직렬화 안전 변환
# =========================
def to_json_safe(obj):
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return obj.isoformat()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_json_safe(v) for v in obj]
    if pd.isna(obj):
        return None
    return obj


# =========================
# 2) 운동 데이터 전처리
# =========================
def split_tags(s):
    if pd.isna(s):
        return []
    return [x.strip() for x in str(s).split(",") if x.strip()]


def normalize_intensity(x):
    x = str(x).strip()
    x = x.replace(" ", "").replace(",,", ",").strip(",")
    return x


def load_workouts():
    if not os.path.exists(WORKOUT_CSV):
        st.error("❌ workout.csv 파일이 없습니다. recommend.py와 같은 폴더에 넣어주세요.")
        st.stop()

    wdf = read_csv_robust(WORKOUT_CSV)

    required_cols = ["운동명", "운동강도", "운동목적", "감정매핑", "단위체중당에너지소비량"]
    missing = [c for c in required_cols if c not in wdf.columns]
    if missing:
        st.error(f"❌ workout.csv에 필요한 컬럼이 없습니다: {missing}")
        st.stop()

    wdf["운동강도"] = wdf["운동강도"].apply(normalize_intensity)
    wdf["운동목적_list"] = wdf["운동목적"].apply(split_tags)
    wdf["감정매핑_list"] = wdf["감정매핑"].apply(split_tags)

    wdf["단위체중당에너지소비량"] = pd.to_numeric(
        wdf["단위체중당에너지소비량"], errors="coerce"
    ).fillna(0)

    return wdf


# =========================
# 3) 날씨 조회
# =========================
def get_weather(city: str):
    key = os.getenv("WEATHER_API_KEY")
    if not key:
        return "unknown", 0.0

    url = (
        "http://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={key}&lang=kr&units=metric"
    )
    try:
        res = requests.get(url, timeout=5)
        data = res.json()
        weather = data.get("weather", [{}])[0].get("main", "unknown").lower()
        temp = float(data.get("main", {}).get("temp", 0))
        return weather, temp
    except Exception:
        return "unknown", 0.0


def infer_place_preference(daily_row, weather):
    place_pref = str(daily_row.get("운동장소", "")).strip()
    if place_pref == "nan":
        place_pref = ""

    bad_weather = any(w in weather for w in ["rain", "drizzle", "thunderstorm", "snow"])

    if bad_weather:
        final_place = "실내"
        msg = "☔/❄ 날씨 영향으로 실내 운동을 우선 추천합니다."
    else:
        if place_pref in ["실내", "실외"]:
            final_place = place_pref
            msg = f"🌤 사용자 선호 장소({place_pref})를 반영해 추천합니다."
        else:
            final_place = "상관없음"
            msg = "🌤 날씨가 무난해 실내/실외 모두 고려해 추천합니다."

    return final_place, msg


# =========================
# 4) 목표 강도 추정 (arousal>=4 → 고강도)
# =========================
INTENSITY_ORDER = ["저강도", "중강도", "고강도"]

POSITIVE_EMOTIONS = {"행복", "기쁨", "설렘", "자신감", "활력", "만족"}
NEGATIVE_EMOTIONS = {"슬픔", "분노", "불안", "초조", "우울", "긴장", "스트레스"}


def get_arousal_from_daily(daily_row):
    candidates = ["감정_평균각성점수", "각성도", "감정각성도", "감정각성도점수", "arousal", "emotion_arousal"]
    for col in candidates:
        if col in daily_row.index:
            try:
                return float(daily_row[col])
            except:
                pass
    return 3.0  # 기본 중간값


def get_emotion_from_daily(daily_row):
    candidates = ["감정_리스트", "감정", "오늘감정", "emotion", "감정상태"]
    for col in candidates:
        if col in daily_row.index:
            v = str(daily_row[col]).strip()
            if v and v != "nan":
                return v.split(",")[0].strip()
    return ""


def infer_target_intensity(daily_row, user_row):
    arousal = get_arousal_from_daily(daily_row)
    emotion = get_emotion_from_daily(daily_row)

    if arousal >= 4.0:
        base = "고강도"
    elif arousal >= 2.5:
        base = "중강도"
    else:
        base = "저강도"

    sleep_hours = float(daily_row.get("수면시간", 7) or 7)
    stress_level = str(daily_row.get("스트레스", "보통") or "보통")
    exercise_time = float(daily_row.get("운동가능시간(분)", 30) or 30)
    activity = str(user_row.get("활동량", "보통") or "보통")
    injury_status = str(user_row.get("부상 이력", "없음") or "없음")
    purpose = str(daily_row.get("운동목적", "") or "")

    target = base

    # 1) 부정 감정/스트레스 높으면 고강도 제한
    if emotion in NEGATIVE_EMOTIONS or stress_level == "높음":
        if target == "고강도":
            target = "중강도"

    # 2) 수면 부족/부상 있으면 하향
    if sleep_hours < 5 or injury_status == "있음":
        if target == "고강도":
            target = "중강도"
        elif target == "중강도":
            target = "저강도"

    # 3) 활동량 높고 시간 충분하면 상향
    if activity == "높음" and exercise_time >= 60 and injury_status != "있음":
        if target == "저강도":
            target = "중강도"
        elif target == "중강도" and emotion in POSITIVE_EMOTIONS:
            target = "고강도"

    # 4) 스트레스 해소 목적일 때 과한 고강도 제한
    if "스트레스 해소" in purpose and target == "고강도" and stress_level == "높음":
        target = "중강도"

    return target, arousal


# =========================
# 5) 1차 룰 기반 후보군 생성
# =========================
def filter_candidates(workouts_df, purpose, target_intensity):
    cand = workouts_df[workouts_df["운동목적_list"].apply(lambda lst: purpose in lst)]
    cand2 = cand[cand["운동강도"] == target_intensity]

    # 후보가 너무 적으면 인접 강도로 확장
    if len(cand2) < 5:
        idx = INTENSITY_ORDER.index(target_intensity)
        near = {target_intensity}
        if idx - 1 >= 0:
            near.add(INTENSITY_ORDER[idx - 1])
        if idx + 1 < len(INTENSITY_ORDER):
            near.add(INTENSITY_ORDER[idx + 1])
        cand2 = cand[cand["운동강도"].isin(list(near))]

    return cand2.reset_index(drop=True)


# =========================
# 6) LLM Top3 + 이유 생성
# =========================
def robust_json_parse(text):
    text = text.strip()
    text = re.sub(r"```(json)?", "", text).strip("` \n")
    m = re.search(r"\{.*\}", text, flags=re.S)
    if m:
        text = m.group(0)
    return json.loads(text)


def llm_rank_top3(candidates_df, user_row, daily_row,
                  weather, temp, city, place_pref, equip_list,
                  merged_user_info):

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("❌ OPENAI_API_KEY 환경변수가 없습니다. Streamlit Secrets에 설정해주세요.")
        st.stop()

    client = OpenAI(api_key=api_key)

    cand_list = []
    for i in range(len(candidates_df)):
        r = candidates_df.iloc[i]
        cand_list.append({
            "운동명": r["운동명"],
            "운동강도": r["운동강도"],
            "운동목적": r["운동목적"],
            "감정매핑": r["감정매핑"],
            "단위체중당에너지소비량": r["단위체중당에너지소비량"]
        })

    system = f"""
당신은 운동 처방 코치입니다.
후보 운동 목록 중 사용자에게 가장 잘 맞는 운동 Top3를 고르고,
각 추천에 대해 구체적인 이유를 쓰세요.

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
형식:
{{
  "top3": [
    {{"rank": 1, "운동명": "...", "이유": "..."}},
    {{"rank": 2, "운동명": "...", "이유": "..."}},
    {{"rank": 3, "운동명": "...", "이유": "..."}}
  ]
}}
"""

    user_prompt = {
        "현재날씨": {"도시": city, "상태": weather, "온도": temp},
        "사용자정적정보(users)": merged_user_info,
        "오늘동적정보(daily)": daily_row.to_dict(),
        "운동장소선호/권장": place_pref,
        "보유장비": equip_list,
        "후보운동목록": cand_list
    }

    safe_prompt = to_json_safe(user_prompt)

    resp = client.chat.completions.create(
        model="gpt-4o",   # 🔥 선택: gpt-4o
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(safe_prompt, ensure_ascii=False)}
        ],
        temperature=0.7
    )

    content = resp.choices[0].message.content
    try:
        parsed = robust_json_parse(content)
        return parsed["top3"]
    except:
        fallback = []
        take_n = min(3, len(candidates_df))
        for j in range(take_n):
            fallback.append({
                "rank": j+1,
                "운동명": candidates_df.iloc[j]["운동명"],
                "이유": "LLM 파싱 실패로 룰 기반 상위 후보를 임시 추천했습니다."
            })
        return fallback


# =========================
# Google Sheet 'recommendation' 시트에 저장
# =========================
for item in top3:
    ws_reco.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        user_name,
        str(pick_date_dt),
        city,
        weather,
        float(temp),
        purpose,
        target_intensity,
        place_pref,
        ", ".join(equip_list),
        item["rank"],
        item["운동명"],
        item["이유"]
    ])


# =========================
# 8) UI - 도시/사용자/날짜 선택
# =========================
st.markdown("## 🌍 도시 입력")
city = st.text_input("날씨를 반영할 도시명", value="Seoul")

weather, temp = get_weather(city)
st.info(f"🌤 현재 날씨: **{weather}**, 온도 **{temp:.1f}°C** (도시: {city})")

st.markdown("---")

st.markdown("## 👤 사용자 선택")
user_name = st.selectbox("추천 받을 사용자", users_df["이름"].astype(str).unique().tolist())

# 해당 사용자의 daily 기록 필터
user_daily = daily_df[daily_df["이름"].astype(str) == str(user_name)].copy()
if user_daily.empty:
    st.error("해당 사용자의 daily 기록이 없습니다. 먼저 컨디션을 기록해주세요.")
    st.stop()

st.markdown("## 📅 날짜 선택")
available_dates = sorted(user_daily["날짜"].dropna().unique())
pick_date = st.selectbox("추천 기준 날짜", available_dates)
pick_date_dt = pd.to_datetime(pick_date).date()

daily_row = user_daily[user_daily["날짜"] == pick_date_dt].iloc[0]

# users 정적 정보
user_row = users_df[users_df["이름"].astype(str) == str(user_name)].iloc[0]

# 정적 + 동적 정보 합치기
merged_user_info = user_row.to_dict()
for k, v in daily_row.to_dict().items():
    if k not in merged_user_info or pd.isna(merged_user_info.get(k)):
        merged_user_info[k] = v

purpose = str(daily_row.get("운동목적", "체력 향상") or "체력 향상")
target_intensity, arousal = infer_target_intensity(daily_row, user_row)

place_pref, place_msg = infer_place_preference(daily_row, weather)
equip_list = split_tags(daily_row.get("보유장비", ""))

st.caption(place_msg)

# 룰 기반 후보군 생성
candidates_df = filter_candidates(workouts_df, purpose, target_intensity)

st.markdown("---")

# =========================
# 9) 추천 버튼
# =========================
if st.button("🤖 Top3 운동 추천 받기", use_container_width=True):
    if len(candidates_df) == 0:
        st.error("추천할 후보 운동이 없습니다. 운동목적/강도 조건을 확인해주세요.")
        st.stop()

    with st.spinner("운동 추천을 생성 중입니다..."):
        top3 = llm_rank_top3(
            candidates_df, user_row, daily_row,
            weather, temp, city,
            place_pref, equip_list,
            merged_user_info
        )

    # 세션에 추천 운동 저장 → 평가 페이지에서 그대로 사용
    st.session_state["recommended_workouts"] = [item["운동명"] for item in top3]
    st.session_state["selected_user"] = user_name
    st.session_state["selected_date"] = str(pick_date_dt)

    # =========================
    # Google Sheet 'recommendation' 시트에 저장
    # =========================
    for item in top3:
        ws_reco.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_name,
            str(pick_date_dt),
            city,
            weather,
            float(temp),
            purpose,
            target_intensity,
            place_pref,
            ", ".join(equip_list),
            item["rank"],
            item["운동명"],
            item["이유"]
        ])

    st.success("🎉 추천 운동이 recommendation 시트에 저장되었습니다!")

    st.markdown("## 🏅 추천 Top3")
    for item in top3:
        st.markdown(f"""
        <div style="background:#f7f9fc; border-radius:16px; padding:18px; margin-bottom:10px; border:1px solid #e5e7eb;">
            <h3 style="margin:0;">#{item['rank']}  {item['운동명']}</h3>
            <p style="margin-top:6px; color:#374151;">
                {item['이유']}
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.write("추천 결과가 만족스러웠나요? 평가를 진행해주세요!")

    if st.button("📊 추천 평가 페이지로 이동", use_container_width=True):
        st.switch_page("4_evaluation_dashboard")   # pages/4_evaluation_dashboard.py
