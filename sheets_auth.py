import gspread
from google.oauth2.service_account import Credentials
import streamlit as st

def connect_gsheet(sheet_name: str):
    creds_info = st.secrets["gcp_service_account"]

    creds = Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"]
    )

    gc = gspread.authorize(creds)
    sh = gc.open(sheet_name)
    return sh
