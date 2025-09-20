import streamlit as st
import requests
import pandas as pd
import io
import json
import plotly.express as px
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

# --- Constants & Session State ---
API_BASE_URL = "http://localhost:8000/api"
CREDENTIALS_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
REDIRECT_URI = 'http://localhost:8501'
STATUS_OPTIONS = ["New", "Shortlisted", "Interviewing", "Rejected", "Hired"]

# Initialize session state variables
st.session_state.setdefault('selected_jd', None)
st.session_state.setdefault('credentials', None)
st.session_state.setdefault('gdrive_current_folder_id', 'root')
st.session_state.setdefault('gdrive_folder_path', [('My Drive', 'root')])
st.session_state.setdefault('gdrive_selected_folder', None)

# --- Backend API Functions ---
@st.cache_data(ttl=300)
def get_jds():
    try:
        response = requests.get(f"{API_BASE_URL}/jobs/")
        if response.status_code == 200: return response.json()
    except requests.RequestException: pass
    return []

def create_jd(title, description):
    try:
        response = requests.post(f"{API_BASE_URL}/jobs/", json={"title": title, "description": description})
        if response.status_code == 200:
            st.success("Job Description created!")
            st.cache_data.clear()
            return response.json()
        st.error(f"Failed to create JD: {response.text}")
    except requests.RequestException as e: st.error(f"Connection error: {e}")
    return None

def get_results_for_jd(jd_id, search_term=None):
    try:
        params = {}
        if search_term: params['search'] = search_term
        response = requests.get(f"{API_BASE_URL}/jobs/{jd_id}/results", params=params)
        if response.status_code == 200: return response.json()
    except requests.RequestException: pass
    return []

def update_candidate_status(result_id, status):
    try:
        response = requests.put(f"{API_BASE_URL}/results/{result_id}/status", json={"status": status})
        return response.status_code == 200
    except requests.RequestException:
        return False

# --- Google Drive Functions ---
def get_google_auth_flow():
    try:
        return Flow.from_client_secrets_file(CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    except FileNotFoundError:
        st.error(f"Error: {CREDENTIALS_FILE} not found.")
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
        except Exception as e: st.error(f"Authentication failed: {e}")

@st.cache_resource
def get_drive_service(_creds):
    if not _creds: return None
    try:
        creds = Credentials.from_authorized_user_info(_creds, SCOPES)
        return build('drive', 'v3', credentials=creds)
    except Exception:
        st.session_state.credentials = None
        return None

def list_folders_in_drive(service, folder_id):
    query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    try:
        results = service.files().list(q=query, pageSize=100, fields="files(id, name)").execute()
        return sorted(results.get('files', []), key=lambda x: x['name'].lower())
    except HttpError: return []

def list_resumes_in_drive(service, folder_id):
    query = f"'{folder_id}' in parents and (mimeType='application/pdf' or mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document') and trashed = false"
    try:
        results = service.files().list(q=query, pageSize=50, fields="files(id, name, mimeType)").execute()
        return results.get('files', [])
    except HttpError: return []

def download_drive_file(service, file_id):
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done: _, done = downloader.next_chunk()
    fh.seek(0)
    return fh.getvalue()

# --- Main App ---
if 'code' in st.query_params and 'credentials' not in st.session_state:
    google_callback()

st.title("🤖 TalentLens: Automated Resume Analyzer")

with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Enter your Gemini API Key", type="password")
    llm_model = st.selectbox("Select LLM Model", ("gemini-1.5-flash", "gemini-1.5-pro"), index=0)
    st.divider()

    st.header("📋 Job Descriptions")
    jd_list = get_jds()
    if jd_list:
        jd_options = {jd['title']: jd['id'] for jd in jd_list}
        selected_jd_title = st.selectbox("Select a Job Description", options=jd_options.keys(), index=None, placeholder="Choose a JD...")
        if selected_jd_title:
            st.session_state.selected_jd = next((jd for jd in jd_list if jd['id'] == jd_options[selected_jd_title]), None)
    with st.expander("Create New Job Description"):
        jd_title = st.text_input("Job Title")
        jd_desc = st.text_area("Job Description Text", height=150)
        if st.button("Save New JD"):
            if jd_title and jd_desc and create_jd(jd_title, jd_desc):
                st.rerun()

if not st.session_state.selected_jd:
    st.info("👋 Welcome! Please select or create a Job Description in the sidebar to begin.")
else:
    jd = st.session_state.selected_jd
    st.header(f"Workspace for: {jd['title']}")
    
    tab_analytics, tab_candidates, tab_upload = st.tabs(["📊 Dashboard Analytics", "📄 Candidate Results", "📤 Upload & Analyze"])

    results_data = get_results_for_jd(jd['id'], st.session_state.get('search_term'))
    df = pd.DataFrame(results_data) if results_data else pd.DataFrame()

    with tab_analytics:
        st.subheader("Analytics & Insights")
        if df.empty:
            st.warning("No candidate data to analyze. Use the 'Upload & Analyze' tab first.")
        else:
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Candidates", len(df))
            col2.metric("Average Score", f"{df['relevance_score'].mean():.2f}%")
            col3.metric("Shortlisted", df[df['status'] == 'Shortlisted'].shape[0])
            st.write("---")
            c1, c2 = st.columns(2)
            verdict_counts = df['verdict'].value_counts().reset_index()
            fig_verdict = px.pie(verdict_counts, names='verdict', values='count', title='Candidate Verdict Distribution',
                                 color='verdict', color_discrete_map={'High': 'green', 'Medium': 'orange', 'Low': 'red'})
            c1.plotly_chart(fig_verdict, use_container_width=True)
            fig_score = px.histogram(df, x='relevance_score', nbins=20, title='Relevance Score Distribution')
            c2.plotly_chart(fig_score, use_container_width=True)

    with tab_candidates:
        st.subheader("Candidate Results & Tracking")
        if df.empty:
            st.info("No candidates found. Use the 'Upload & Analyze' tab to begin.")
        else:
            st.text_input("Search by Keyword (in filename or analysis)", key="search_term", on_change=st.rerun)
            for _, row in df.iterrows():
                st.write("---")
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.markdown(f"**{row['filename']}**")
                c2.metric("Relevance Score", f"{row['relevance_score']:.2f}%")
                current_status_index = STATUS_OPTIONS.index(row['status']) if row['status'] in STATUS_OPTIONS else 0
                new_status = c3.selectbox("Status", options=STATUS_OPTIONS, index=current_status_index, key=f"status_{row['id']}")
                if new_status != row['status']:
                    if update_candidate_status(row['id'], new_status):
                        st.success(f"Updated status for {row['filename']} to {new_status}")
                        st.rerun()
                    else: st.error("Failed to update status.")
                with st.expander("View Detailed Analysis"):
                    st.markdown("##### 🔍 Missing Elements")
                    st.info(row['missing_elements'])
                    st.markdown("##### 💡 Improvement Suggestions")
                    st.success(row['improvement_suggestions'])

    with tab_upload:
        st.subheader("Select Resumes to Analyze")
        col_local, col_gdrive = st.columns(2)
        
        with col_local:
            st.markdown("#### 📂 From Your Computer")
            local_files = st.file_uploader("Upload resumes", type=["pdf", "docx"], accept_multiple_files=True, label_visibility="collapsed")

        with col_gdrive:
            st.markdown("#### ☁️ From Google Drive")
            drive_service = get_drive_service(st.session_state.credentials)
            if not drive_service:
                flow = get_google_auth_flow()
                if flow:
                    auth_url, _ = flow.authorization_url(prompt='consent')
                    st.link_button("Login with Google", auth_url)
                else:
                    st.warning("Google Drive cannot be used until `credentials.json` is configured.")
            else:
                st.success("Connected to Google Drive!")
                
                # --- Google Drive Browser Logic ---
                if st.button("⬆️ Parent Folder"):
                    if len(st.session_state.gdrive_folder_path) > 1:
                        st.session_state.gdrive_folder_path.pop()
                        st.session_state.gdrive_current_folder_id = st.session_state.gdrive_folder_path[-1][1]
                        
                path_str = " / ".join([name for name, _ in st.session_state.gdrive_folder_path])
                st.info(f"**Current Path:** {path_str}")

                folders = list_folders_in_drive(drive_service, st.session_state.gdrive_current_folder_id)
                folder_names = [f['name'] for f in folders]
                
                # Use a callback to handle folder selection to avoid rerun issues
                def on_folder_select():
                    selected_name = st.session_state.gdrive_selected_folder
                    if selected_name:
                        folder_id = next((f['id'] for f in folders if f['name'] == selected_name), None)
                        st.session_state.gdrive_current_folder_id = folder_id
                        st.session_state.gdrive_folder_path.append((selected_name, folder_id))

                st.selectbox("Open folder:", folder_names, index=None, placeholder="Choose a folder to open...", 
                             key='gdrive_selected_folder', on_change=on_folder_select)
                
                drive_resumes = list_resumes_in_drive(drive_service, st.session_state.gdrive_current_folder_id)
                selected_drive_files = st.multiselect("Select resumes:", drive_resumes, format_func=lambda f: f['name'])
        
        st.divider()
        if st.button("🚀 Analyze Selected Resumes", use_container_width=True, type="primary"):
            files_to_process = []
            if local_files:
                for f in local_files:
                    files_to_process.append({'name': f.name, 'bytes': f.getvalue(), 'type': f.type})
            
            if 'selected_drive_files' in locals() and selected_drive_files:
                with st.spinner("Downloading files from Google Drive..."):
                    for drive_file in selected_drive_files:
                        file_bytes = download_drive_file(drive_service, drive_file['id'])
                        files_to_process.append({'name': drive_file['name'], 'bytes': file_bytes, 'type': drive_file['mimeType']})

            if not api_key: st.error("Please enter your Gemini API Key in the sidebar.")
            elif not files_to_process: st.error("Please select at least one resume.")
            else:
                progress_bar = st.progress(0, text="Starting analysis...")
                for i, file_data in enumerate(files_to_process):
                    progress_bar.progress((i + 1) / len(files_to_process), text=f"Uploading {file_data['name']}...")
                    try:
                        files_payload = {'resume': (file_data['name'], file_data['bytes'], file_data.get('type'))}
                        data_payload = {'jd_id': jd['id']}
                        headers = {'X-API-Key': api_key, 'X-LLM-Model': llm_model}
                        response = requests.post(f"{API_BASE_URL}/analyze/", files=files_payload, data=data_payload, headers=headers)
                        if response.status_code != 200:
                            st.error(f"Failed to start analysis for {file_data['name']}: {response.text}")
                    except requests.RequestException as e: st.error(f"Connection error for {file_data['name']}: {e}")
                progress_bar.empty()
                st.success("All resumes sent for analysis! View progress in the 'Candidate Results' tab.")