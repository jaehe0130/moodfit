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


# ========================= Google Sheets (연결 캐시만) =========================
@st.cache_resource
def get_spreadsheet():
    """MoodFit 스프레드시트 객체 캐시"""
    return connect_gsheet("MoodFit")


def load_daily_raw():
    """
    daily 시트 전체 데이터를 항상 최신으로 가져오기.
    추천 결과를 정확한 행에 쓰기 위해 캐시를 사용하지 않음.
    """
    sh = get_spreadsheet()
    ws_daily = sh.worksheet("daily")
    return ws_daily.get_all_values()


def load_users_df():
    """
    users 시트 전체를 DataFrame으로 가져오기.
    새로 가입한 회원이 바로 보이도록 캐시하지 않음.
    """
    sh = get_spreadsheet()
    ws_users = sh.worksheet("users")
    return pd.DataFrame(ws_users.get_all_records())


# ========================= 감정 추출 함수 =========================
def get_emotion_from_daily(row):
    """
    daily 시트에서 감정 관련 컬럼을 우선순위대로 찾아서 대표 감정을 하나 반환.
    """
    for col in ["감정", "대표감정", "주요감정", "감정_리스트"]:
        if col in row and pd.notna(row[col]):
            return str(row[col]).split(",")[0].strip()
    return ""


# ========================= 사용자 프로필 JSON 빌더 =========================
def build_user_profile(user_row, daily_row, weather, temp):
    """
    LLM에 넘길 사용자 프로필/컨디션 정보를 하나의 dict로 묶어줌.
    - 정적프로필: users 시트 정보
    - 오늘컨디션: daily 시트 정보
    - 환경정보: 날씨, 기온 등
    """
    profile = {
        "정적프로필": user_row.to_dict(),   # 이름, 나이 (만나이), 성별, 키(cm), 몸무게(kg), 평소 활동량, 부상 여부, 부상 부위
        "오늘컨디션": daily_row.to_dict(),  # 감정, 감정_평균각성점수, 수면 시간, 운동 가능 시간(분), 스트레스, 운동목적, 운동장소, 보유장비
        "환경정보": {
            "날씨": weather,
            "기온_C": temp,
        },
    }
    return profile


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


# ========================= 페이지 메인 로직 =========================

# ========== 날씨 입력 ==========
city = st.text_input("🌍 도시명", "Seoul")
weather, temp = get_weather(city)
st.info(f"현재날씨: {weather}, {temp:.1f}°C")

# 스프레드시트 & 시트 핸들 (업데이트용)
sh = get_spreadsheet()
ws_daily = sh.worksheet("daily")

# 최신 daily/users 데이터 로드
daily_raw = load_daily_raw()
if len(daily_raw) < 2:
    st.error("❌ daily 시트에 데이터가 없습니다.")
    st.stop()

daily_df = pd.DataFrame(daily_raw[1:], columns=daily_raw[0])
users_df = load_users_df()

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

# daily 시트에서 운동장소/보유장비 사용
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

    # 사용자 프로필 JSON 구성
    user_profile = build_user_profile(
        user_row=user_row,
        daily_row=daily_row,
        weather=weather,
        temp=temp,
    )

    # 운동 후보 JSON (workout.csv 기반)
    rule_candidates = [
        {
            "운동명": r["운동명"],
            "운동목적": r["운동목적"],
            "운동강도": r.get("운동강도", ""),
        }
        for _, r in candidates.iterrows()
    ]

    # ===== 프롬프트 =====
    system_prompt = f"""
당신은 개인 맞춤형 운동 코치입니다.

[입력 설명]
- 나는 user_profile 과 rule_candidates 를 JSON 형태로 전달합니다.
- user_profile 안에는 다음과 같은 정보가 들어 있습니다.
  - 정적프로필 (users 시트):
    - 이름, 나이 (만나이), 성별, 키(cm), 몸무게(kg), 평소 활동량, 부상 여부, 부상 부위
  - 오늘컨디션 (daily 시트):
    - 날짜, 감정, 감정_평균각성점수, 수면 시간, 운동 가능 시간(분), 스트레스, 운동목적, 운동장소, 보유장비
  - 환경정보:
    - 현재 날씨, 기온

[반드시 지켜야 할 규칙]

1. user_profile 을 적극적으로 활용하세요.
   - 수면 시간:
     - 5시간 미만이면 고강도·점프·HIIT 운동은 피하고, 저강도 스트레칭/요가/가벼운 근력 위주로 추천합니다.
   - 스트레스:
     - 스트레스가 높을수록(숫자가 크거나 '높음'에 해당하면) 긴장 완화/마음 안정에 도움이 되는 운동(스트레칭, 요가, 호흡을 동반한 운동 등)을 포함합니다.
   - 운동 가능 시간(분):
     - 시간이 매우 짧으면(예: 20분 이하) 짧게 끝낼 수 있는 운동 위주로 추천합니다.
     - 시간이 길면 전신 루틴이나 여러 근육을 쓰는 운동을 포함할 수 있습니다.
   - 평소 활동량:
     - 활동량이 낮으면, 처음부터 너무 강한 운동 대신 난이도가 낮은 운동부터 시작하도록 추천합니다.
   - 키·몸무게:
     - 체중이 많이 나갈수록 관절에 부담이 큰 점프/러닝보다는, 관절 부담이 적은 운동을 우선 고려합니다.
   - 부상 여부/부상 부위:
     - 부상 여부가 '예' 혹은 true 인 경우, 해당 부위(예: 무릎, 허리 등)에 무리가 가는 운동은 피합니다.
     - 예: 무릎 부상이 있으면 점프/스쿼트/런닝은 조심하고, 상체/코어/비체중부하 운동을 더 추천합니다.
   - 감정/감정_평균각성점수:
     - 각성 점수가 낮고 기분이 처져 있으면, 지나치게 힘든 운동보다는 가볍게 기분 전환할 수 있는 운동을 선택합니다.
     - 각성 점수가 높고 에너지가 넘친다면, 유산소나 조금 더 활동적인 운동을 포함할 수 있습니다.

2. 운동장소 선호를 반영하세요. (daily 시트의 '운동장소' 참고)
   - 운동장소가 "집" 또는 "실내"인 경우:
     - 특별한 이유가 없으면 야외에서만 하는 운동(걷기, 조깅, 러닝, 등산, 자전거 타기 등)은 추천하지 않습니다.
   - 운동장소가 "야외"인 경우:
     - 가능하면 야외에서 수행하기 좋은 운동을 1개 이상 포함합니다.
   - "상관없음"인 경우:
     - 장소는 자유롭게 선택하되, 사용자 컨디션에 맞지 않는 극단적인 운동은 피합니다.

3. 다양성을 확보하세요.
   - top3 운동은 서로 다른 계열/목적/패턴이 되도록 합니다.
   - 예: 모두 '걷기' 계열(걷기, 빠르게 걷기, 조깅, 런닝 등)만 추천하지 말고,
     - 유산소 / 근력 / 스트레칭 / 코어 등 계열이 다양해지도록 선택합니다.
   - rule_candidates 에 운동계열/태그 정보가 있다면 이를 적극 활용하여 비슷한 운동이 겹치지 않게 합니다.

4. 후보 운동만 사용하세요.
   - 반드시 rule_candidates 안에 존재하는 운동명만 선택합니다.
   - 새로운 운동명을 만들어내지 마세요.

5. 출력 형식
   - JSON만 출력합니다.
   - 이유에는 user_profile 의 어떤 정보를 고려했는지 자연스럽게 드러나도록 설명합니다.
     (예: "수면 시간이 짧고 스트레스가 높아, 부드러운 전신 스트레칭 위주로 구성했습니다." 등)

출력 형식:
{{
  "top3": [
    {{"rank":1, "운동명":"", "이유":""}},
    {{"rank":2, "운동명":"", "이유":""}},
    {{"rank":3, "운동명":"", "이유":""}}
  ]
}}
"""

    # LLM에 넘길 payload (사용자 정보 + 운동 후보)
    payload = {
        "user_profile": user_profile,
        "rule_candidates": rule_candidates,
    }

    with st.spinner("추천 생성 중..."):
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, default=str)
            },
        ],
        temperature=0.6,
    )

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

    # ======== Spotify 플레이리스트 생성 및 출력 ========
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

# ========================= 평가 페이지 이동 버튼 (항상 화면 하단에) =========================
st.markdown("---")
if st.button("📊 평가하기", use_container_width=True):
    st.switch_page("pages/4_evaluation.py")
