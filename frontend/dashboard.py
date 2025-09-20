import streamlit as st
import requests
import pandas as pd
import io
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

# --- Page Configuration ---
st.set_page_config(
    page_title="Innomatics Resume Analyzer",
    page_icon="📄",
    layout="wide"
)

# --- Constants ---
BACKEND_URL = "http://backend:8000/api/analyze/"
CREDENTIALS_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
# IMPORTANT: This must match the URI in your Google Cloud Console
REDIRECT_URI = 'http://localhost:8501' 

# --- Session State Initialization ---
if 'results' not in st.session_state:
    st.session_state.results = []
if 'credentials' not in st.session_state:
    st.session_state.credentials = None
if 'drive_files' not in st.session_state:
    st.session_state.drive_files = []

# --- Google Drive Authentication ---
def get_google_auth_flow():
    """Initializes the Google OAuth flow."""
    return Flow.from_client_secrets_file(
        CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI
    )

def google_callback():
    """Handles the callback after Google authentication."""
    flow = get_google_auth_flow()
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
        except Exception as e:
            st.error(f"Authentication failed: {e}")

# --- Google Drive API Functions ---
@st.cache_resource
def get_drive_service(_creds_dict):
    """Returns an authorized Google Drive service object. Cached to prevent re-creation."""
    if not _creds_dict: return None
    try:
        creds = Credentials.from_authorized_user_info(_creds_dict, SCOPES)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Failed to build drive service: {e}")
        st.session_state.credentials = None
        return None

def list_files_from_drive(service, folder_id):
    """Lists files from a specific Google Drive folder."""
    query = f"'{folder_id}' in parents and (mimeType='application/pdf' or mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document')"
    try:
        results = service.files().list(
            q=query, pageSize=50, fields="nextPageToken, files(id, name, mimeType)"
        ).execute()
        return results.get('files', [])
    except HttpError as error:
        st.error(f"An error occurred while fetching files: {error}")
        return []

def download_drive_file(service, file_id, file_name):
    """Downloads a file from Google Drive and returns its content as bytes."""
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)
    return {'name': file_name, 'bytes': fh.getvalue()}

# --- Main App Logic ---
if 'code' in st.query_params and not st.session_state.credentials:
    google_callback()

st.title("🤖 Automated Resume Relevance Check System")

# --- Sidebar Configuration ---
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Enter your Gemini API Key", type="password")
    llm_model = st.selectbox("Select LLM Model", ("gemini-2.0-flash", "gemini-2.5-pro"), index=0)
    
    st.divider()
    
    st.header("🔗 Connect to Google Drive")
    drive_service = get_drive_service(st.session_state.credentials)
    if not drive_service:
        auth_url, _ = get_google_auth_flow().authorization_url(prompt='consent')
        st.link_button("Login with Google", auth_url)
    else:
        st.success("Connected to Google Drive!")
        if st.button("Logout from Google"):
            st.session_state.credentials = None
            st.rerun()

# --- Main Page UI ---
st.subheader("1. Enter Job Description")
job_description = st.text_area("Paste the Job Description here", height=250, placeholder="e.g., Senior Python Developer with experience in FastAPI and AWS...")

st.subheader("2. Select Resumes")
tab1, tab2 = st.tabs(["📂 Local Upload", "☁️ Google Drive"])

with tab1:
    uploaded_files = st.file_uploader(
        "Upload resumes (PDF or DOCX)", type=["pdf", "docx"], accept_multiple_files=True
    )

with tab2:
    if not drive_service:
        st.warning("Please login with Google in the sidebar to fetch files from Drive.")
    else:
        folder_id = st.text_input("Enter Google Drive Folder ID", help="You can find the ID in the folder's URL.")
        if st.button("Fetch Files from Folder"):
            with st.spinner("Fetching files..."):
                st.session_state.drive_files = list_files_from_drive(drive_service, folder_id)
        
        if st.session_state.drive_files:
            selected_drive_files = st.multiselect(
                "Select resumes to analyze", options=st.session_state.drive_files, format_func=lambda x: x['name']
            )

files_to_process = []
if st.button("Analyze Resumes", type="primary", use_container_width=True):
    # Consolidate files from both sources
    if uploaded_files:
        for f in uploaded_files:
            files_to_process.append({'name': f.name, 'bytes': f.getvalue(), 'type': f.type})
    
    if 'selected_drive_files' in locals() and selected_drive_files:
        with st.spinner("Downloading selected files from Google Drive..."):
            for drive_file in selected_drive_files:
                file_content = download_drive_file(drive_service, drive_file['id'], drive_file['name'])
                files_to_process.append({
                    'name': file_content['name'],
                    'bytes': file_content['bytes'],
                    'type': drive_file['mimeType']
                })

    if not api_key: st.error("Please enter your Gemini API Key in the sidebar.")
    elif not job_description.strip(): st.error("Please enter a job description.")
    elif not files_to_process: st.error("Please select at least one resume to analyze.")
    else:
        st.session_state.results = []
        progress_bar = st.progress(0, text="Starting Analysis...")
        for i, file_data in enumerate(files_to_process):
            progress_bar.progress((i + 1) / len(files_to_process), text=f"Analyzing {file_data['name']}...")
            try:
                files_payload = {'resume': (file_data['name'], file_data['bytes'], file_data.get('type'))}
                data_payload = {'jd': job_description}
                headers = {'X-API-Key': api_key, 'X-LLM-Model': llm_model}
                response = requests.post(BACKEND_URL, files=files_payload, data=data_payload, headers=headers)
                if response.status_code == 200:
                    st.session_state.results.append(response.json())
                else:
                    error_detail = response.json().get('detail', 'Unknown error')
                    st.error(f"Failed to analyze {file_data['name']}: {error_detail}")
            except requests.exceptions.RequestException as e:
                st.error(f"Connection error for {file_data['name']}: {e}")
        progress_bar.empty()
        if st.session_state.results: st.success("Analysis complete!")

# --- Results Dashboard ---
if st.session_state.results:
    st.divider()
    st.subheader("📊 Analysis Results")
    df = pd.DataFrame(st.session_state.results).sort_values(by="relevance_score", ascending=False).reset_index(drop=True)

    # Filtering options
    col1, col2 = st.columns([1, 2])
    score_threshold = col1.slider("Filter by minimum score", 0, 100, 0)
    verdict_filter = col2.multiselect("Filter by verdict", options=df['verdict'].unique(), default=df['verdict'].unique())
    
    filtered_df = df[(df['relevance_score'] >= score_threshold) & (df['verdict'].isin(verdict_filter))]
    st.write(f"Displaying {len(filtered_df)} of {len(df)} candidates.")
    
    for index, row in filtered_df.iterrows():
        st.write("---")
        c1, c2, c3 = st.columns([2, 1, 1])
        c1.markdown(f"#### {index + 1}. {row['filename']}")
        c2.metric("Relevance Score", f"{row['relevance_score']:.2f}%")
        verdict = row['verdict']
        if verdict == 'High': c3.success(f"**Verdict: {verdict}**")
        elif verdict == 'Medium': c3.warning(f"**Verdict: {verdict}**")
        else: c3.error(f"**Verdict: {verdict}**")

        with st.expander("View Detailed Analysis"):
            st.markdown("##### 🔍 Missing Skills / Projects / Certifications")
            st.info(row['missing_elements'])
            st.markdown("##### 💡 Suggestions for Improvement")
            st.success(row['improvement_suggestions'])