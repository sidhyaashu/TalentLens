import streamlit as st
import requests
import pandas as pd
import io
import plotly.express as px
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import json

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
st.session_state.setdefault('selected_jd', None)

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

# --- Google Drive Functions (remain unchanged) ---
def get_google_auth_flow():
    return Flow.from_client_secrets_file(CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)

def google_callback():
    flow = get_google_auth_flow()
    code = st.query_params.get('code')
    if code:
        try:
            flow.fetch_token(code=code)
            st.session_state.credentials = flow.credentials.to_json()
            st.query_params.clear()
            st.rerun()
        except Exception as e: st.error(f"Authentication failed: {e}")

def get_drive_service():
    if 'credentials' not in st.session_state or not st.session_state.credentials: return None
    try:
        creds = Credentials.from_authorized_user_info(json.loads(st.session_state.credentials), SCOPES)
        return build('drive', 'v3', credentials=creds)
    except Exception:
        st.session_state.credentials = None
        return None
# ...(Other Drive functions are unchanged but should be included if missing)...
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

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Enter your Gemini API Key", type="password")
    llm_model = st.selectbox("Select LLM Model", ("gemini-2.0-flash", "gemini-2.5-pro"), index=0)
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

# --- Main Content ---
if not st.session_state.selected_jd:
    st.info("👋 Welcome! Please select or create a Job Description in the sidebar to begin.")
else:
    jd = st.session_state.selected_jd
    st.header(f"Workspace for: {jd['title']}")
    
    # --- Main Tabs ---
    tab_analytics, tab_candidates, tab_upload = st.tabs(["📊 Dashboard Analytics", "📄 Candidate Results", "📤 Upload Resumes"])

    results_data = get_results_for_jd(jd['id'], st.session_state.get('search_term'))
    df = pd.DataFrame(results_data) if results_data else pd.DataFrame()

    with tab_analytics:
        st.subheader("Analytics & Insights")
        if df.empty:
            st.warning("No candidate data to analyze. Please upload and analyze resumes first.")
        else:
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Candidates", len(df))
            col2.metric("Average Score", f"{df['relevance_score'].mean():.2f}%" if not df.empty else "N/A")
            col3.metric("Shortlisted", df[df['status'] == 'Shortlisted'].shape[0])

            st.write("---")
            c1, c2 = st.columns(2)
            # Verdict Distribution Pie Chart
            verdict_counts = df['verdict'].value_counts().reset_index()
            verdict_counts.columns = ['verdict', 'count']
            fig_verdict = px.pie(verdict_counts, names='verdict', values='count', title='Candidate Verdict Distribution',
                                 color='verdict', color_discrete_map={'High': 'green', 'Medium': 'orange', 'Low': 'red'})
            c1.plotly_chart(fig_verdict, use_container_width=True)

            # Score Distribution Histogram
            fig_score = px.histogram(df, x='relevance_score', nbins=20, title='Relevance Score Distribution')
            c2.plotly_chart(fig_score, use_container_width=True)

    with tab_candidates:
        st.subheader("Candidate Results & Tracking")
        if df.empty:
            st.info("No candidates found. Use the 'Upload Resumes' tab to begin analysis.")
        else:
            # Filtering and Searching
            st.text_input("Search by Keyword (in filename or analysis)", key="search_term", on_change=st.rerun)
            
            for index, row in df.iterrows():
                st.write("---")
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.markdown(f"**{row['filename']}**")
                c2.metric("Relevance Score", f"{row['relevance_score']:.2f}%")
                
                # Status Tagging
                current_status_index = STATUS_OPTIONS.index(row['status']) if row['status'] in STATUS_OPTIONS else 0
                new_status = c3.selectbox("Status", options=STATUS_OPTIONS, index=current_status_index, key=f"status_{row['id']}")
                if new_status != row['status']:
                    if update_candidate_status(row['id'], new_status):
                        st.success(f"Updated status for {row['filename']} to {new_status}")
                        st.rerun()
                    else:
                        st.error("Failed to update status.")

                with st.expander("View Detailed Analysis"):
                    st.markdown("##### 🔍 Missing Elements")
                    st.info(row['missing_elements'])
                    st.markdown("##### 💡 Improvement Suggestions")
                    st.success(row['improvement_suggestions'])

    with tab_upload:
        st.subheader("Upload New Resumes for Analysis")
        uploaded_files = st.file_uploader("Upload resumes (PDF or DOCX)", type=["pdf", "docx"], accept_multiple_files=True)
        
        if st.button("Analyze Uploaded Resumes", use_container_width=True, type="primary"):
            if not api_key: st.error("Please enter your Gemini API Key in the sidebar.")
            elif not uploaded_files: st.error("Please upload at least one resume.")
            else:
                progress_bar = st.progress(0, text="Starting analysis...")
                for i, file in enumerate(uploaded_files):
                    progress_bar.progress((i + 1) / len(uploaded_files), text=f"Uploading {file.name}...")
                    try:
                        files_payload = {'resume': (file.name, file.getvalue(), file.type)}
                        data_payload = {'jd_id': jd['id']}
                        headers = {'X-API-Key': api_key, 'X-LLM-Model': llm_model}
                        response = requests.post(f"{API_BASE_URL}/analyze/", files=files_payload, data=data_payload, headers=headers)
                        if response.status_code != 200:
                            st.error(f"Failed to start analysis for {file.name}: {response.text}")
                    except requests.RequestException as e: st.error(f"Connection error for {file.name}: {e}")
                progress_bar.empty()
                st.success("All resumes sent for analysis. Check the 'Candidate Results' tab.")