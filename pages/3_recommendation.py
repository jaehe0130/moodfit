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

    # 운동목적 리스트화
    if "운동목적" not in df.columns:
        st.error("❌ workout.csv 에 '운동목적' 컬럼이 없습니다.")
        st.stop()
    df["운동목적_list"] = df["운동목적"].apply(split_tags)

    # (있으면) 운동강도 정규화
    if "운동강도" in df.columns:
        df["운동강도"] = df["운동강도"].astype(str).str.strip()

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


def load_daily_raw():
    """daily 시트 전체 데이터를 항상 새로 읽어옴."""
    sh = get_spreadsheet()
    ws_daily = sh.worksheet("daily")
    return ws_daily.get_all_values()


def load_users_df():
    """users 시트 전체를 DataFrame으로 가져오기(항상 최신)."""
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


# ========================= (핵심 변경) 각성점수 -> 목표 운동강도 =========================
def safe_float(x):
    try:
        if pd.isna(x):
            return None
        return float(str(x).strip())
    except Exception:
        return None


def infer_target_intensity_from_arousal(arousal_score):
    """
    감정_평균각성점수(숫자)를 기반으로 1차 후보군(운동강도)을 정합니다.
    - 스케일이 1~5, 0~5 등 다양한 경우를 대비해 '상대적' 기준으로 처리
    - 값이 비정상이면 None 반환(강도 필터링 X)
    """
    a = safe_float(arousal_score)
    if a is None:
        return None

    # 흔한 스케일: 1~5 또는 0~5를 가정한 기본 컷
    # 낮음: 2.5 이하 / 중간: 2.5~3.5 / 높음: 3.5이상
    if a <= 2.5:
        return "저강도"
    elif a < 3.5:
        return "중강도"
    else:
        return "고강도"


def filter_candidates_by_intensity(df, target_intensity):
    """
    workout.csv에 '운동강도'가 있을 때만 필터 적용.
    target_intensity가 None이면 필터링하지 않음.
    """
    if target_intensity is None:
        return df.copy()

    if "운동강도" not in df.columns:
        return df.copy()

    filtered = df[df["운동강도"].astype(str).str.strip() == target_intensity].copy()
    return filtered


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
    sp, top3, daily_row, purpose, market="KR"
):
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
        w_intensity = item.get("운동강도", "")

        query = ""

        if client:
            prompt = {
                "workout": wname,
                "emotion": emotion,
                "purpose": purpose,
                "intensity": w_intensity,
                "instruction": "검색용 키워드 한 개만 JSON으로 출력. {\"query\": \"...\"}"
            }
            try:
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    response_format={"type": "json_object"},
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
users_df = load_users_df()

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

# daily 시트에서 운동장소/보유장비
place_pref = daily_row.get("운동장소", "상관없음")
equip_raw = daily_row.get("보유장비", "")
equip_list = [s.strip() for s in str(equip_raw).split(",") if s.strip()]

# ========================= (핵심 변경) 1차 후보군: 각성점수 -> 운동강도 필터 =========================
arousal_score = daily_row.get("감정_평균각성점수", None)
target_intensity = infer_target_intensity_from_arousal(arousal_score)

candidates = filter_candidates_by_intensity(workouts_df, target_intensity)

# 강도 필터 결과가 너무 비거나, 강도 컬럼이 없거나, 어떤 이유로든 후보가 0이면 전체로 백업
if candidates.empty:
    candidates = workouts_df.copy()

# 사용자 운동목적 (이제 "후보군 필터"가 아니라 "프롬프트 우선순위"에 강하게 반영)
purpose = str(daily_row.get("운동목적", "")).strip()


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

    # 1차(각성점수 기반 운동강도)로 필터링된 후보군만 LLM에 전달
    rule_candidates = [
        {
            "운동명": r["운동명"],
            "운동목적": r.get("운동목적", ""),
            "운동강도": r.get("운동강도", ""),
        }
        for _, r in candidates.iterrows()
    ]

    # ===================== (핵심 변경) 시스템 프롬프트: 운동목적 우선순위 강화 =====================
    system_prompt = f"""
당신은 개인 맞춤 운동 추천 엔진입니다.

입력으로 다음 정보가 주어집니다.

1) user_profile["정적프로필"]
- Google Sheets의 users 시트 한 행 전체가 그대로 들어 있습니다.
- 포함되는 컬럼:
  - 이름, 나이(만나이), 성별, 키(cm), 몸무게(kg), 평소 활동량,
    부상 여부(예/아니오), 부상 부위(허리/무릎/어깨 등 또는 해당 없음)

2) user_profile["오늘컨디션"]
- Google Sheets의 daily 시트에서 사용자가 오늘 입력한 컨디션 정보입니다.
- 포함되는 컬럼:
  - 날짜, 이름, 감정, 감정_평균각성점수, 수면 시간, 운동 가능 시간(분),
    스트레스, 운동목적, 운동장소, 보유장비

3) user_profile["환경정보"]
- 오늘 날씨/기온:
  - 날씨(clear, clouds, rain 등)
  - 기온_C(섭씨)

4) rule_candidates
- **이미 감정_평균각성점수를 기반으로 "운동강도"가 맞게 1차 필터링된** 운동 목록입니다.
- 각 항목:
  - 운동명, 운동목적, 운동강도(저강도/중강도/고강도)

당신의 역할:
- 오늘 이 사용자에게 가장 적합한 운동 3가지를 **rule_candidates 안에서만** 선택하세요.

[우선순위 규칙: 운동목적 > 그 외 요소]
- 사용자가 오늘 선택한 운동목적(user_profile["오늘컨디션"]["운동목적"])을 **가장 우선으로** 충족해야 합니다.
- 즉, **Top3는 가능하면 모두 운동목적에 부합하는 운동으로 구성**하세요.
- 단, 아래 안전/현실 제약(부상/시간/장소/장비/수면/스트레스)이 크게 충돌하면
  목적 부합도를 일부 낮추더라도 더 안전하고 실행 가능한 운동을 우선할 수 있습니다.

[감정/각성점수 활용]
- rule_candidates는 이미 각성점수 기반 강도 필터가 적용되어 있습니다.
- 따라서 여기서는:
  - 감정(정서적 상태) + 각성점수를 근거로 "왜 이 강도가 적절한지"를 이유에 구체적으로 설명하고,
  - 동일 목적 내에서 '기분전환/긴장완화/에너지회복' 등 감정에 맞는 운동을 상위에 두세요.

[정적 정보 활용]
- 나이/성별/키/몸무게/활동량/부상 여부·부상 부위 반영:
  - 부상 부위를 악화시키는 동작은 제외하거나 순위 낮춤
  - 활동량이 낮은 경우 과도한 자극은 피함

[오늘 컨디션(동적 정보)]
- 수면 부족 + 스트레스 높음 → 강도/볼륨(부담) 자동 하향(가능 범위 내)
- 운동 가능 시간 짧음 → 짧게 끝낼 수 있는 운동 우선
- 운동장소/보유장비가 가능한 운동을 우선(집+장비없음→맨몸/매트 등)

[환경정보]
- 비/폭염/한파 등 → 실내운동 우선
- 맑고 온화 → 가벼운 야외 유산소 고려 가능

출력 형식:
- 반드시 아래 JSON 하나의 객체만 출력
- 설명 문장/마크다운/코드블록 없이 JSON만 출력

{{
  "top3": [
    {{
      "rank": 1,
      "운동명": "운동 이름",
      "이유": "운동목적을 1순위로 충족하는 근거 + 감정/각성점수 + 수면/스트레스 + 시간/장소/장비 + 부상 + 날씨를 종합해 2~4문장"
    }},
    ...
  ]
}}

규칙:
- 반드시 3개만 추천
- 운동명은 rule_candidates 안에 존재하는 것만 사용
- 요가 계열(요가/스트레칭/필라테스 등)은 중복되지 않도록 하며, 전체 2개 이하
- 이유는 실제 입력값(감정, 각성점수, 수면시간, 스트레스, 시간, 장소/장비 등)을 반영해 구체적으로 작성
"""
    # ===============================================================

    payload = {
        "user_profile": user_profile,
        "rule_candidates": rule_candidates,
    }

    with st.spinner("추천 생성 중..."):
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
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

    # workout.csv에서 운동명 → 운동강도 매핑해서 top3에 붙여줌 (Spotify LLM에서 쓰기 위함)
    if "운동강도" in workouts_df.columns:
        intensity_map = workouts_df.set_index("운동명")["운동강도"].to_dict()
        for item in top3:
            wname = item.get("운동명", "")
            item["운동강도"] = intensity_map.get(wname, "")
    else:
        for item in top3:
            item["운동강도"] = ""

    headers = daily_raw[0]

    def col_idx(name):
        if name not in headers:
            st.error(f"❌ daily 시트에 '{name}' 컬럼 없음")
            st.stop()
        return headers.index(name) + 1

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
