import streamlit as st
import requests
import pandas as pd
import io
import plotly.express as px
import time
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

# --- Page Configuration ---
st.set_page_config(
    page_title="TalentLens Resume Analyzer",
    page_icon="🤖",
    layout="wide"
)

# --- Constants ---
API_BASE_URL = "http://localhost:8000/api"
CREDENTIALS_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
REDIRECT_URI = 'http://localhost:8501'
STATUS_OPTIONS = ["New", "Shortlisted", "Interviewing", "Rejected", "Hired"]

# --- Session State Initialization ---
st.session_state.setdefault('selected_jd', None)
st.session_state.setdefault('credentials', None)
st.session_state.setdefault('gdrive_current_folder_id', 'root')
st.session_state.setdefault('gdrive_folder_path', [('My Drive', 'root')])
st.session_state.setdefault('gdrive_selected_folder', None)

# --- Backend API Functions ---
@st.cache_data(ttl=300)
def get_jds():
    try:
        r = requests.get(f"{API_BASE_URL}/jobs/")
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return []

def create_jd(title, description):
    try:
        r = requests.post(f"{API_BASE_URL}/jobs/", json={"title": title, "description": description})
        if r.status_code == 200:
            st.success("Job Description created!")
            st.cache_data.clear()
            return r.json()
        st.error(f"Failed to create JD: {r.text}")
    except requests.RequestException as e:
        st.error(f"Connection error: {e}")
    return None

def get_results_for_jd(jd_id, search=None):
    try:
        params = {"search": search} if search else {}
        r = requests.get(f"{API_BASE_URL}/jobs/{jd_id}/results", params=params)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return []

def update_candidate_status(result_id, status):
    try:
        r = requests.put(f"{API_BASE_URL}/results/{result_id}/status", json={"status": status})
        return r.status_code == 200
    except requests.RequestException:
        return False

# --- Google Drive Functions ---
def get_google_auth_flow():
    try:
        return Flow.from_client_secrets_file(CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    except FileNotFoundError:
        st.error(f"Missing {CREDENTIALS_FILE}")
        return None

def google_callback():
    flow = get_google_auth_flow()
    if not flow: return
    code = st.query_params.get('code')
    if code:
        try:
            flow.fetch_token(code=code)
            creds = flow.credentials
            st.session_state.credentials = {
                'token': creds.token, 'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri, 'client_id': creds.client_id,
                'client_secret': creds.client_secret, 'scopes': creds.scopes
            }
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Authentication failed: {e}")

def get_drive_service(_creds):
    """Rebuild service fresh each time creds change."""
    if not _creds:
        return None
    try:
        creds = Credentials.from_authorized_user_info(_creds, SCOPES)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Drive auth failed: {e}")
        st.session_state.credentials = None
        return None

def list_folders_in_drive(service, folder_id):
    q = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    try:
        r = service.files().list(q=q, pageSize=100, fields="files(id, name)").execute()
        return sorted(r.get('files', []), key=lambda x: x['name'].lower())
    except HttpError:
        return []

def list_resumes_in_drive(service, folder_id):
    q = f"'{folder_id}' in parents and (mimeType='application/pdf' or mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document') and trashed=false"
    try:
        r = service.files().list(q=q, pageSize=50, fields="files(id, name, mimeType)").execute()
        return r.get('files', [])
    except HttpError:
        return []

def download_drive_file(service, file_id):
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)
    return fh.getvalue()

# --- Main ---
if 'code' in st.query_params and 'credentials' not in st.session_state:
    google_callback()

st.title("🤖 TalentLens: Automated Resume Analyzer")

with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Enter your Gemini API Key", type="password")
    llm_model = st.selectbox("Select LLM Model", ("gemini-2.0-flash", "gemini-2.5-pro"), index=0)
    st.divider()

    st.header("📋 Job Descriptions")
    jd_list = get_jds()
    if jd_list:
        jd_options = {jd['title']: jd['id'] for jd in jd_list}
        selected_jd_title = st.selectbox(
            "Select a Job Description",
            options=jd_options.keys(),
            index=None,
            placeholder="Choose a JD..."
        )
        if selected_jd_title:
            st.session_state.selected_jd = jd_options[selected_jd_title]

    with st.expander("Create New Job Description"):
        jd_title = st.text_input("Job Title")
        jd_desc = st.text_area("Job Description Text", height=150)
        if st.button("Save New JD"):
            if jd_title and jd_desc and create_jd(jd_title, jd_desc):
                st.rerun()

if not st.session_state.selected_jd:
    st.info("👋 Please select or create a Job Description first.")
else:
    jd_id = st.session_state.selected_jd
    st.header("Workspace")

    tab_analytics, tab_candidates, tab_upload = st.tabs(["📊 Dashboard Analytics", "📄 Candidate Results", "📤 Upload & Analyze"])

    # --- Analytics ---
    results = get_results_for_jd(jd_id, st.session_state.get('search_term'))
    df = pd.DataFrame(results) if results else pd.DataFrame()

    with tab_analytics:
        if df.empty:
            st.warning("No candidates yet.")
        else:
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Candidates", len(df))
            col2.metric("Average Score", f"{df['relevance_score'].mean():.2f}%")
            col3.metric("Shortlisted", df[df['status'] == 'Shortlisted'].shape[0])
            st.write("---")
            c1, c2 = st.columns(2)
            verdict_counts = df['verdict'].value_counts().reset_index()
            fig_v = px.pie(verdict_counts, names='verdict', values='count', title='Verdict Distribution')
            c1.plotly_chart(fig_v, use_container_width=True)
            fig_s = px.histogram(df, x='relevance_score', nbins=20, title='Score Distribution')
            c2.plotly_chart(fig_s, use_container_width=True)

    # --- Candidates ---
    with tab_candidates:
        if df.empty:
            st.info("No results yet.")
        else:
            st.text_input("Search", key="search_term", on_change=st.rerun)
            for _, row in df.iterrows():
                st.write("---")
                c1, c2, c3 = st.columns([2,1,1])
                c1.markdown(f"**{row['filename']}**")
                c2.metric("Score", f"{row['relevance_score']:.2f}%")
                idx = STATUS_OPTIONS.index(row['status']) if row['status'] in STATUS_OPTIONS else 0
                new_status = c3.selectbox("Status", STATUS_OPTIONS, index=idx, key=f"status_{row['id']}")
                if new_status != row['status']:
                    if update_candidate_status(row['id'], new_status):
                        st.success(f"Updated {row['filename']} → {new_status}")
                        st.rerun()

                with st.expander("Details"):
                    st.info(row['missing_elements'])
                    st.success(row['improvement_suggestions'])

    # --- Upload & Analyze ---
    with tab_upload:
        col_local, col_gdrive = st.columns(2)

        with col_local:
            local_files = st.file_uploader("📂 Upload resumes", type=["pdf","docx"], accept_multiple_files=True)

        with col_gdrive:
            drive_service = get_drive_service(st.session_state.credentials)
            if not drive_service:
                flow = get_google_auth_flow()
                if flow:
                    auth_url, _ = flow.authorization_url(prompt='consent')
                    if st.button("🔑 Login with Google"):
                        st.markdown(
                            f"""
                            <meta http-equiv="refresh" content="0; url={auth_url}">
                            """,
                            unsafe_allow_html=True
                        )
                else:
                    st.warning("Google Drive not available.")
            else:
                st.success("Connected to Google Drive ✅")
                if st.button("⬆️ Parent"):
                    if len(st.session_state.gdrive_folder_path) > 1:
                        st.session_state.gdrive_folder_path.pop()
                        st.session_state.gdrive_current_folder_id = st.session_state.gdrive_folder_path[-1][1]

                path_str = " / ".join([n for n, _ in st.session_state.gdrive_folder_path])
                st.info(f"Path: {path_str}")

                folders = list_folders_in_drive(drive_service, st.session_state.gdrive_current_folder_id)
                folder_names = [f['name'] for f in folders]

                def on_folder_select():
                    sel = st.session_state.gdrive_selected_folder
                    if sel:
                        folder_id = next((f['id'] for f in folders if f['name']==sel), None)
                        st.session_state.gdrive_current_folder_id = folder_id
                        st.session_state.gdrive_folder_path.append((sel, folder_id))

                st.selectbox("Open folder", folder_names, index=None, key='gdrive_selected_folder', on_change=on_folder_select)

                drive_resumes = list_resumes_in_drive(drive_service, st.session_state.gdrive_current_folder_id)
                selected_drive_files = st.multiselect("Select resumes", drive_resumes, format_func=lambda f: f['name'])

        st.divider()
        if st.button("🚀 Analyze Selected Resumes", use_container_width=True):
            files_to_process = []
            if local_files:
                for f in local_files:
                    files_to_process.append({'name': f.name, 'bytes': f.getvalue(), 'type': f.type})

            if 'selected_drive_files' in locals() and selected_drive_files:
                for f in selected_drive_files:
                    file_bytes = download_drive_file(drive_service, f['id'])
                    files_to_process.append({'name': f['name'], 'bytes': file_bytes, 'type': f['mimeType']})

            if not api_key:
                st.error("Enter your Gemini API Key first.")
            elif not files_to_process:
                st.error("No resumes selected.")
            else:
                progress = st.progress(0, text="Starting analysis...")
                for i, f in enumerate(files_to_process):
                    progress.progress((i+1)/len(files_to_process), text=f"Uploading {f['name']}...")
                    try:
                        files_payload = {'resume': (f['name'], f['bytes'], f['type'])}
                        data_payload = {'jd_id': jd_id}
                        headers = {'X-API-Key': api_key, 'X-LLM-Model': llm_model}
                        r = requests.post(f"{API_BASE_URL}/analyze/", files=files_payload, data=data_payload, headers=headers)
                        if r.status_code != 200:
                            st.error(f"Failed {f['name']}: {r.text}")
                    except requests.RequestException as e:
                        st.error(f"Connection error {f['name']}: {e}")
                progress.empty()
                st.success("All resumes sent for analysis ✅")
