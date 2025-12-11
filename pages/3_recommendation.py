# -*- coding: utf-8 -*-
import os, re, json, requests
import pandas as pd
import numpy as np
import streamlit as st
from openai import OpenAI
from datetime import datetime, date
from sheets_auth import connect_gsheet

# ========================= Spotify import =========================
try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
except ImportError:
    spotipy = None
    SpotifyClientCredentials = None


# ========================= 공통: 시크릿/환경변수 헬퍼 =========================
def get_secret(key: str, default: str = ""):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)


# ========================= 기본 UI =========================
st.set_page_config(page_title="운동 추천", page_icon="🏋️", layout="centered")

st.markdown("""
<h1 style='text-align:center; font-weight:700;'>🏋️ 맞춤 운동 추천</h1>
<p style="text-align:center; color:gray; margin-top:-10px;">
오늘의 컨디션 + 날씨 기반 Top3 운동 추천
</p>
""", unsafe_allow_html=True)


# ========================= CSV 불러오기 =========================
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


workouts_df = load_workouts()


# ========================= 날씨 조회 =========================
def get_weather(city):
    key = get_secret("WEATHER_API_KEY")
    if not key:
        return "unknown", 0.0
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={key}&lang=kr&units=metric"
        res = requests.get(url).json()
        return res["weather"][0]["main"].lower(), res["main"]["temp"]
    except Exception:
        return "unknown", 0.0


# ========================= JSON 파서 (강화 버전) =========================
def parse_json(text: str):
    """
    LLM 응답 문자열에서 JSON 객체만 안전하게 파싱.
    실패 시, 원본 텍스트를 화면에 보여주고 예외를 다시 올립니다.
    """
    if not text or not text.strip():
        raise ValueError("LLM 응답이 비어 있습니다.")

    text = text.strip()

    # ```json, ``` 제거
    text = re.sub(r"^```json", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^```", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()

    # 중괄호 블록만 추출
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        text = m.group(0)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # 디버깅용: 실제로 어떤 응답이 왔는지 화면에 보여주기
        try:
            st.error("⚠️ LLM JSON 파싱에 실패했습니다. 아래 원본 응답을 확인하세요.")
            st.code(text)
        except Exception:
            print("JSON parse error, raw text:", text)
        raise e


# ========================= Google Sheets (연결 캐시) =========================
@st.cache_resource
def get_spreadsheet():
    """MoodFit 스프레드시트 객체 캐시"""
    return connect_gsheet("MoodFit")


# ❌ 캐시 X : 항상 최신 daily를 읽기 위해 데코레이터 제거
def load_daily_raw():
    """
    daily 시트 전체 데이터를 항상 새로 읽어옴.
    """
    sh = get_spreadsheet()
    ws_daily = sh.worksheet("daily")
    return ws_daily.get_all_values()


# 🔴 users_df는 캐시를 쓰면 새 회원이 안 보여서 캐시 제거
def load_users_df():
    """
    users 시트 전체를 DataFrame으로 가져오기.
    - 항상 최신 데이터를 보기 위해 캐시 사용 X
    """
    sh = get_spreadsheet()
    ws_users = sh.worksheet("users")
    return pd.DataFrame(ws_users.get_all_records())


# ========================= 감정 추출 함수 =========================
def get_emotion_from_daily(row):
    for col in ["감정", "대표감정", "주요감정", "감정_리스트"]:
        if col in row and pd.notna(row[col]):
            return str(row[col]).split(",")[0].strip()
    return ""


# ========================= 사용자 프로필 JSON 빌더 =========================
def build_user_profile(user_row, daily_row, weather, temp):
    profile = {
        "정적프로필": user_row.to_dict(),
        "오늘컨디션": daily_row.to_dict(),
        "환경정보": {
            "날씨": weather,
            "기온_C": temp,
        },
    }
    return profile


# ========================= Spotify 클라이언트 =========================
def get_spotify_client():
    if spotipy is None:
        st.warning("⚠️ spotipy 가 import 되지 않았습니다. requirements.txt에 'spotipy'를 추가해주세요.")
        return None

    cid = None
    csec = None

    try:
        spotify_section = st.secrets["spotify"]
        cid = spotify_section.get("client_id") or spotify_section.get("CLIENT_ID")
        csec = spotify_section.get("client_secret") or spotify_section.get("CLIENT_SECRET")
    except Exception:
        spotify_section = {}

    if not cid:
        cid = os.getenv("SPOTIFY_CLIENT_ID")
    if not csec:
        csec = os.getenv("SPOTIFY_CLIENT_SECRET")

    if not cid or not csec:
        st.warning("⚠️ Spotify Client ID/Secret 이 설정되어 있지 않습니다.")
        return None

    try:
        auth = SpotifyClientCredentials(client_id=cid, client_secret=csec)
        sp = spotipy.Spotify(auth_manager=auth)
        return sp
    except Exception as e:
        st.error(f"❌ Spotify 클라이언트 생성 중 오류: {e}")
        return None


def search_spotify_playlists(sp, query, market="KR", limit=3):
    if sp is None:
        return []

    try:
        res = sp.search(q=query, type="playlist", limit=limit, market=market)

        playlists_block = res.get("playlists") or {}
        items = playlists_block.get("items") or []

        cleaned = []
        for it in items:
            if not isinstance(it, dict):
                continue

            title = it.get("name") or ""

            owner_name = ""
            owner_obj = it.get("owner") or {}
            if isinstance(owner_obj, dict):
                owner_name = owner_obj.get("display_name") or owner_obj.get("id") or ""

            url = ""
            ext = it.get("external_urls") or {}
            if isinstance(ext, dict):
                url = ext.get("spotify") or ""

            cleaned.append({
                "title": title,
                "owner": owner_name,
                "url": url
            })

        return cleaned

    except Exception as e:
        st.error(f"❌ Spotify 검색 중 오류: {e}")
        return []


# ========================= LLM 기반 Spotify 검색 키워드 =========================
def get_playlists_for_top3_with_llm(
    sp, top3, daily_row, target_intensity, purpose, market="KR"
):
    if sp is None:
        # Spotify 사용 불가 시, 구조만 맞춰서 빈 리스트 반환
        return [{"운동명": t["운동명"], "playlists": []} for t in top3]

    client = None
    openai_key = get_secret("OPENAI_API_KEY")
    if openai_key:
        client = OpenAI(api_key=openai_key)

    emotion = get_emotion_from_daily(daily_row)
    result = []

    for item in top3:
        wname = item["운동명"]
        query = ""

        if client:
            prompt = {
                "workout": wname,
                "emotion": emotion,
                "purpose": purpose,
                "intensity": target_intensity,
                "instruction": "검색용 키워드 한 개만 JSON으로 출력. {\"query\": \"...\"}"
            }
            try:
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    response_format={"type": "json_object"},  # ✅ JSON 강제
                    messages=[
                        {
                            "role": "system",
                            "content": "당신은 운동-음악 큐레이터입니다. 검색용 키워드 한 개를 JSON 객체로만 출력하세요."
                        },
                        {
                            "role": "user",
                            "content": json.dumps(prompt, ensure_ascii=False)
                        }
                    ]
                )
                raw = resp.choices[0].message.content
                data = parse_json(raw)
                query = data.get("query", "")
            except Exception:
                query = ""

        if not query:
            query = f"{wname} workout playlist"

        playlists = search_spotify_playlists(sp, query, market=market)
        result.append({"운동명": wname, "playlists": playlists})

    return result


# ========================= 페이지 메인 로직 =========================

# ========== 날씨 입력 ==========
city = st.text_input("🌍 도시명", "Seoul")
weather, temp = get_weather(city)
st.info(f"현재날씨: {weather}, {temp:.1f}°C")

# 스프레드시트 & 시트 핸들
sh = get_spreadsheet()
ws_daily = sh.worksheet("daily")

# 최신 daily/users 데이터 로드
daily_raw = load_daily_raw()
if len(daily_raw) < 2:
    st.error("❌ daily 시트에 데이터가 없습니다.")
    st.stop()

daily_df = pd.DataFrame(daily_raw[1:], columns=daily_raw[0])
users_df = load_users_df()   # ✅ 항상 최신 users 시트를 읽음

# 👉 이름 공백 정규화 (매칭 문제 방지)
if "이름" in daily_df.columns:
    daily_df["이름"] = daily_df["이름"].astype(str).str.strip()
if "이름" in users_df.columns:
    users_df["이름"] = users_df["이름"].astype(str).str.strip()

daily_df["날짜"] = pd.to_datetime(daily_df["날짜"], errors="coerce").dt.date

# ========================= 사용자 선택 =========================
st.markdown("### 👤 사용자 선택")
user_name = st.selectbox("오늘 추천 받을 사용자", users_df["이름"].unique().tolist())

user_daily = daily_df[daily_df["이름"] == user_name]
if user_daily.empty:
    st.error("❌ 사용자의 daily 데이터가 없습니다.")
    st.stop()

pick_date = st.selectbox("추천 기준 날짜", sorted(user_daily["날짜"].unique(), reverse=True))
daily_row = user_daily[user_daily["날짜"] == pick_date].iloc[0]

mask = (daily_df["이름"] == user_name) & (daily_df["날짜"] == pick_date)
row_idx = daily_df[mask].index[0]
sheet_row = row_idx + 2  # 헤더 1줄 + 1-based index

# 사용자 정적 정보 (users 시트)
user_row = users_df[users_df["이름"] == user_name].iloc[0]

# daily 시트에서 운동장소/보유장비 사용 (현재는 룰 후보 필터링에는 사용 X, 이후 확장용)
place_pref = daily_row.get("운동장소", "상관없음")
equip_raw = daily_row.get("보유장비", "")
equip_list = [s.strip() for s in str(equip_raw).split(",") if s.strip()]

# ========================= RULE 후보군 =========================
purpose = daily_row.get("운동목적", "")
target_intensity = "중강도"  # 기본값

if purpose:
    candidates = workouts_df[workouts_df["운동목적_list"].apply(lambda x: purpose in x)]
    if candidates.empty:
        candidates = workouts_df.copy()
else:
    candidates = workouts_df.copy()

st.markdown("---")

# ========================= Top3 추천 생성 =========================
if st.button("🤖 Top3 추천 받기", use_container_width=True):

    openai_key = get_secret("OPENAI_API_KEY")
    if not openai_key:
        st.error("❌ OPENAI_API_KEY가 설정되어 있지 않습니다.")
        st.stop()

    client = OpenAI(api_key=openai_key)

    user_profile = build_user_profile(
        user_row=user_row,
        daily_row=daily_row,
        weather=weather,
        temp=temp,
    )

    rule_candidates = [
        {
            "운동명": r["운동명"],
            "운동목적": r["운동목적"],
            "운동강도": r.get("운동강도", ""),
        }
        for _, r in candidates.iterrows()
    ]

    # ===================== 시스템 프롬프트 =====================
    system_prompt = """
당신은 개인 맞춤 운동 추천 엔진입니다.

입력으로 사용자 프로필(user_profile)과 룰 기반 후보 운동(rule_candidates)이 주어집니다.
이 정보를 바탕으로 오늘 사용자에게 가장 적합한 운동 3가지를 선택하고, 각 운동에 대한 추천 이유를 작성하세요.

출력 형식은 반드시 아래 JSON 하나의 객체만 사용해야 합니다.
설명 문장, 마크다운, 코드블록 없이 JSON만 출력하세요.

{
  "top3": [
    {
      "rank": 1,
      "운동명": "운동 이름",
      "이유": "사용자 정적 정보, 오늘 컨디션, 날씨, 운동 목적/강도 등을 종합한 이유를 한국어로 자연스럽게 작성"
    },
    {
      "rank": 2,
      "운동명": "운동 이름",
      "이유": "..."
    },
    {
      "rank": 3,
      "운동명": "운동 이름",
      "이유": "..."
    }
  ]
}

규칙:
- 반드시 3개만 추천합니다.
- "운동명"은 rule_candidates 안에 존재하는 운동명만 사용합니다.
- "rank"는 1, 2, 3의 정수로 지정합니다.
- "이유"는 2~4문장 정도로, 너무 길지 않게 작성합니다.
    """
    # ===============================================================

    payload = {
        "user_profile": user_profile,
        "rule_candidates": rule_candidates,
    }

    with st.spinner("추천 생성 중..."):
        resp = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},  # ✅ JSON 강제
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False, default=str),
                },
            ],
            temperature=0.6,
        )

        raw = resp.choices[0].message.content
        parsed = parse_json(raw)

        if "top3" not in parsed:
            st.error("❌ LLM 응답에 'top3' 키가 없습니다. 프롬프트를 확인하세요.")
            st.code(raw)
            st.stop()

        top3 = parsed["top3"]

    headers = daily_raw[0]

    def col_idx(name):
        if name not in headers:
            st.error(f"❌ daily 시트에 '{name}' 컬럼 없음")
            st.stop()
        return headers.index(name) + 1  # 1-based

    c_w1 = col_idx("추천운동1")
    c_w2 = col_idx("추천운동2")
    c_w3 = col_idx("추천운동3")
    c_r1 = col_idx("추천이유1")
    c_r2 = col_idx("추천이유2")
    c_r3 = col_idx("추천이유3")

    # Google Sheets 업데이트
    ws_daily.update_cell(sheet_row, c_w1, top3[0]["운동명"])
    ws_daily.update_cell(sheet_row, c_w2, top3[1]["운동명"])
    ws_daily.update_cell(sheet_row, c_w3, top3[2]["운동명"])
    ws_daily.update_cell(sheet_row, c_r1, top3[0]["이유"])
    ws_daily.update_cell(sheet_row, c_r2, top3[1]["이유"])
    ws_daily.update_cell(sheet_row, c_r3, top3[2]["이유"])


    # 화면 표시
    st.markdown("## 🏅 추천 Top3")
    for item in top3:
        st.write(f"### #{item['rank']} {item['운동명']}")
        st.write(item["이유"])

    # ========================= Spotify 연동 =========================
    sp = get_spotify_client()
    workout_playlist_pairs = get_playlists_for_top3_with_llm(
        sp, top3, daily_row,
        target_intensity=target_intensity,
        purpose=purpose,
        market="KR"
    )

    st.markdown("## 🎧 추천 운동별 Spotify 플레이리스트")

    for pair in workout_playlist_pairs:
        wname = pair["운동명"]
        pls = pair["playlists"]

        st.markdown(f"### 🏷️ {wname}")

        if not pls:
            st.info("이 운동에 어울리는 플레이리스트를 찾지 못했어요 😢")
        else:
            p = pls[0]
            st.markdown(f"""
            <div style="
                background:#ffffff;
                border-radius:16px;
                padding:14px;
                margin-bottom:8px;
                border:1px solid #e5e7eb;">
                <h4 style="margin:0;">🎵 {p['title']}</h4>
                <p style="margin:4px 0 0 0; color:#6b7280;">
                    by {p['owner']}
                </p>
                <a href="{p['url']}" target="_blank">🔗 Spotify에서 열기</a>
            </div>
            """, unsafe_allow_html=True)

# ========================= 평가 페이지 이동 버튼 =========================
st.markdown("---")
if st.button("📊 평가하기", use_container_width=True):
    st.switch_page("pages/4_evaluation.py")
