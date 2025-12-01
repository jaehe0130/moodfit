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
    """
    Streamlit Cloud(st.secrets)와 로컬 환경변수(os.getenv)를 모두 지원하는 헬퍼.
    """
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


# ========================= JSON 파서 =========================
def parse_json(text: str):
    if not text:
        raise ValueError("빈 JSON")

    text = text.strip()
    # ```json, ``` 제거
    text = re.sub(r"^```json", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    text = re.sub(r"^```", "", text).strip()

    # 중괄호 블록만 추출
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if m:
        text = m.group(0)

    return json.loads(text)


# ========================= Google Sheets =========================
city = st.text_input("🌍 도시명", "Seoul")
weather, temp = get_weather(city)
st.info(f"현재날씨: {weather}, {temp:.1f}°C")

sh = connect_gsheet("MoodFit")
ws_users = sh.worksheet("users")
ws_daily = sh.worksheet("daily")

daily_raw = ws_daily.get_all_values()
if len(daily_raw) < 2:
    st.error("❌ daily 시트에 데이터가 없습니다.")
    st.stop()

daily_df = pd.DataFrame(daily_raw[1:], columns=daily_raw[0])
users_df = pd.DataFrame(ws_users.get_all_records())

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


# 사용자 정적 정보
user_row = users_df[users_df["이름"] == user_name].iloc[0]
place_pref = user_row.get("운동장소선호", "상관없음")
equip_raw = user_row.get("보유장비", "")
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


# ========================= 감정 추출 함수 =========================
def get_emotion_from_daily(row):
    for col in ["감정", "대표감정", "주요감정", "감정_리스트"]:
        if col in row and pd.notna(row[col]):
            return str(row[col]).split(",")[0].strip()
    return ""


# ========================= Spotify 클라이언트 =========================
def get_spotify_client():
    """
    Streamlit secrets 의 [spotify] 섹션과 환경변수를 이용해 Spotify 클라이언트를 생성.
    - secrets.toml 예시:
        [spotify]
        client_id = "..."
        client_secret = "..."
    """
    if spotipy is None:
        st.warning("⚠️ spotipy 가 import 되지 않았습니다. requirements.txt에 'spotipy'를 추가해주세요.")
        return None

    cid = None
    csec = None

    # 1) [spotify] 섹션 우선 사용
    try:
        spotify_section = st.secrets["spotify"]
        cid = spotify_section.get("client_id") or spotify_section.get("CLIENT_ID")
        csec = spotify_section.get("client_secret") or spotify_section.get("CLIENT_SECRET")
    except Exception:
        spotify_section = {}

    # 2) 환경변수 폴백
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
    """
    Spotify에서 playlist를 검색하고, 구조가 이상한 결과(NaN, None 등)를 방어적으로 정리.
    """
    if sp is None:
        return []

    try:
        res = sp.search(q=query, type="playlist", limit=limit, market=market)

        playlists_block = res.get("playlists") or {}
        items = playlists_block.get("items") or []

        cleaned = []
        for it in items:
            # it 이 None 이거나 dict가 아니면 스킵
            if not isinstance(it, dict):
                continue

            # 제목
            title = it.get("name") or ""

            # owner
            owner_name = ""
            owner_obj = it.get("owner") or {}
            if isinstance(owner_obj, dict):
                owner_name = owner_obj.get("display_name") or owner_obj.get("id") or ""

            # URL
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
    # sp가 None이면 처음부터 빈 리스트 반환
    if sp is None:
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
                    messages=[
                        {
                            "role": "system",
                            "content": "당신은 운동-음악 큐레이터입니다. JSON만 출력."
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
                # LLM 실패 시 폴백 쿼리로 진행
                query = ""

        # 폴백: LLM이 실패하거나 빈 문자열이면 기본 쿼리
        if not query:
            query = f"{wname} workout playlist"

        playlists = search_spotify_playlists(sp, query, market=market)
        result.append({"운동명": wname, "playlists": playlists})

    return result


# ========================= Top3 추천 생성 =========================
if st.button("🤖 Top3 추천 받기", use_container_width=True):

    openai_key = get_secret("OPENAI_API_KEY")
    if not openai_key:
        st.error("❌ OPENAI_API_KEY가 설정되어 있지 않습니다.")
        st.stop()

    client = OpenAI(api_key=openai_key)

    rule_candidates = [
        {
            "운동명": r["운동명"],
            "운동목적": r["운동목적"],
            "운동강도": r.get("운동강도", "")
        }
        for _, r in candidates.iterrows()
    ]

    system_prompt = f"""
당신은 운동 추천 전문가입니다.
사용자의 컨디션, 목적, 보유장비, 날씨를 고려하여 서로 다른 계열의 운동 3개를 추천하고 이유를 작성.
JSON만 출력.

사용자 운동장소 선호: {place_pref}
보유장비: {', '.join(equip_list) if equip_list else '없음'}
현재 날씨: {weather}, 온도: {temp:.1f}°C

형식:
{{
"top3":[
{{"rank":1,"운동명":"","이유":""}},
{{"rank":2,"운동명":"","이유":""}},
{{"rank":3,"운동명":"","이유":""}}
]
}}
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
        top3 = parse_json(raw)["top3"]

    # ======== Google Sheet 업데이트 ========
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

    ws_daily.update_cell(sheet_row, c_w1, top3[0]["운동명"])
    ws_daily.update_cell(sheet_row, c_w2, top3[1]["운동명"])
    ws_daily.update_cell(sheet_row, c_w3, top3[2]["운동명"])
    ws_daily.update_cell(sheet_row, c_r1, top3[0]["이유"])
    ws_daily.update_cell(sheet_row, c_r2, top3[1]["이유"])
    ws_daily.update_cell(sheet_row, c_r3, top3[2]["이유"])

    st.success("🎉 daily 시트 저장 완료!")

    # ======== 추천 결과 출력 ========
    st.markdown("## 🏅 추천 Top3")
    for item in top3:
        st.write(f"### #{item['rank']} {item['운동명']}")
        st.write(item["이유"])

    # ========================= Spotify 블록 =========================
    emotion = get_emotion_from_daily(daily_row)
    top3_names = [t["운동명"] for t in top3]
    cache_key = f"{target_intensity}|{purpose}|{emotion}|{'/'.join(top3_names)}"

    if "playlist_cache" not in st.session_state:
        st.session_state["playlist_cache"] = {}

    if cache_key in st.session_state["playlist_cache"]:
        workout_playlist_pairs = st.session_state["playlist_cache"][cache_key]
    else:
        sp = get_spotify_client()
        workout_playlist_pairs = get_playlists_for_top3_with_llm(
            sp, top3, daily_row,
            target_intensity=target_intensity,
            purpose=purpose,
            market="KR"
        )
        st.session_state["playlist_cache"][cache_key] = workout_playlist_pairs

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

    # ========================= 평가 페이지 이동 =========================
    if st.button("📊 평가하기"):

    st.write("🔍 버튼 눌림: OK")  # 1) 버튼이 눌렸는지 확인

    # 2) 파일이 실제로 존재하는지 확인
    import os
    file_path = os.path.join("pages", "4_evaluation.py")
    st.write("📁 파일 존재 여부:", os.path.exists(file_path))

    # 3) switch_page 실행 전 확인
    st.write("➡️ switch_page 실행 시도:", "pages/4_evaluation.py")

    try:
        st.switch_page("pages/4_evaluation.py")
        st.write("✅ switch_page 실행됨 (이 메시지가 안 뜨면 실행 안 됨)")
    except Exception as e:
        st.write("❌ switch_page 에러 발생!")
        st.write(str(e))
