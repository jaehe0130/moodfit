# pages/3_recommendation.py
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
from sheets_auth import connect_gsheet

st.set_page_config(page_title="운동 추천", layout="centered", page_icon="🏋️")

st.markdown("""
    <h1 style='text-align:center; font-weight:700;'>🏋️ 맞춤 운동 추천</h1>
    <p style="text-align:center; color:gray; margin-top:-10px;">
        오늘의 컨디션 + 날씨 기반 Top3 운동 추천
    </p>
""", unsafe_allow_html=True)

WORKOUT_CSV = "workout.csv"

def read_csv_robust(path: str) -> pd.DataFrame:
    encodes=["utf-8-sig","utf-8","cp949"]
    for e in encodes:
        try: return pd.read_csv(path,encoding=e)
        except: pass
    return pd.read_csv(path)

def split_tags(s):
    if pd.isna(s): return []
    return [x.strip() for x in str(s).split(",") if x.strip()]

def normalize_intensity(x):
    return str(x).strip().replace(" ", "").strip(",")

def load_workouts():
    df = read_csv_robust(WORKOUT_CSV)
    df["운동강도"] = df["운동강도"].apply(normalize_intensity)
    df["운동목적_list"] = df["운동목적"].apply(split_tags)
    df["감정매핑_list"] = df["감정매핑"].apply(split_tags)
    df["단위체중당에너지소비량"] = pd.to_numeric(df["단위체중당에너지소비량"], errors="coerce")
    return df

def get_weather(city):
    key = os.getenv("WEATHER_API_KEY")
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={key}&units=metric&lang=kr"
    try:
        res=requests.get(url).json()
        return res["weather"][0]["main"].lower(), float(res["main"]["temp"])
    except:
        return "unknown", 0.0

INTENSITY_ORDER=["저강도","중강도","고강도"]

def filter_candidates(df,purpose,target):
    cand=df[df["운동목적_list"].apply(lambda x: purpose in x)]
    res=cand[cand["운동강도"]==target]
    if len(res)<5:
        idx=INTENSITY_ORDER.index(target)
        valid=set([INTENSITY_ORDER[max(0,idx-1)],target,INTENSITY_ORDER[min(2,idx+1)]])
        res=cand[cand["운동강도"].isin(valid)]
    return res.reset_index(drop=True)

def robust_json_parse(t):
    t=re.sub(r"```(json)?","",t).strip()
    return json.loads(re.search(r"\{.*\}",t,flags=re.S).group(0))

def llm_rank_top3(candidates_df,user_row,daily_row,weather,temp,city,place_pref,equip_list,merged):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    cand=[]
    for _,r in candidates_df.iterrows():
        cand.append({"운동명":r["운동명"],"운동강도":r["운동강도"],"운동목적":r["운동목적"],"감정매핑":r["감정매핑"]})

    system=f"""
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
 "top3":[
  {{"rank":1,"운동명":"...","이유":"..."}},
  {{"rank":2,"운동명":"...","이유":"..."}},
  {{"rank":3,"운동명":"...","이유":"..."}}
 ]
}}
"""

    user_prompt={
      "현재날씨":{"도시":city,"상태":weather,"온도":temp},
      "정적정보":merged,
      "동적정보":daily_row.to_dict(),
      "보유장비":equip_list,
      "운동장소":place_pref,
      "후보운동목록":cand
    }

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"system","content":system},
                  {"role":"user","content":json.dumps(user_prompt,ensure_ascii=False)}],
        temperature=0.6
    )

    return robust_json_parse(res.choices[0].message.content)["top3"]


# ========================= LOAD SHEETS =========================
sh=connect_gsheet("MoodFit")
ws_users=sh.worksheet("users")
ws_daily=sh.worksheet("daily")
ws_reco=sh.worksheet("recommendation")

users_df=pd.DataFrame(ws_users.get_all_records())
daily_df=pd.DataFrame(ws_daily.get_all_records())
workouts_df=load_workouts()

daily_df["날짜"]=pd.to_datetime(daily_df["날짜"],errors="coerce").dt.date

# UI
st.markdown("## 🌍 도시 입력")
city=st.text_input("도시명",value="Seoul")
weather,temp=get_weather(city)
st.info(f"현재날씨: {weather}, {temp:.1f}°C")

st.markdown("## 👤 사용자 선택")
user_name=st.selectbox("사용자",users_df["이름"].unique())

user_daily=daily_df[daily_df["이름"]==user_name]
available_dates=sorted(user_daily["날짜"].unique())
pick_date=st.selectbox("추천 날짜",available_dates)
daily_row=user_daily[user_daily["날짜"]==pick_date].iloc[0]
user_row=users_df[users_df["이름"]==user_name].iloc[0]

merged={**user_row.to_dict(),**daily_row.to_dict()}
place_pref=daily_row.get("운동장소","상관없음")
equip_list=split_tags(daily_row.get("보유장비",""))
purpose=daily_row["운동목적"]

target="중강도"
candidates_df=filter_candidates(workouts_df,purpose,target)

st.markdown("---")

if st.button("🤖 Top3 추천 받기",use_container_width=True):
    with st.spinner("추천 생성 중..."):
        top3=llm_rank_top3(candidates_df,user_row,daily_row,weather,temp,city,place_pref,equip_list,merged)

    # sheet 저장
    for item in top3:
        ws_reco.append_row([
            user_name,
            str(pick_date_dt),
            purpose,
            top3[0]["운동명"], top3[1]["운동명"], top3[2]["운동명"],
            top3[0]["이유"], top3[1]["이유"], top3[2]["이유"],
            target_intensity,
            weather,
            place_pref
        ])


    st.session_state["recommended_workouts"]=[i["운동명"] for i in top3]

    st.success("🎉 recommendation 시트에 저장 완료!")
    st.markdown("## 🏅 추천 Top3")

    for item in top3:
        st.write(f"### #{item['rank']} {item['운동명']}")
        st.write(item["이유"])

    if st.button("📊 추천 평가 페이지 이동"):
        st.switch_page("pages/4_evaluation_dashboard.py")
