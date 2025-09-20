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
    page_title="TalentLens Resume Analyzer",
    page_icon="🤖",
    layout="wide"
)

# --- Constants ---
BACKEND_URL = "http://localhost:8000/api/analyze/"
CREDENTIALS_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
REDIRECT_URI = 'http://localhost:8501'

# --- Session State Initialization ---
st.session_state.setdefault('results', [])
st.session_state.setdefault('credentials', None)
st.session_state.setdefault('drive_files', [])
st.session_state.setdefault('current_folder_id', 'root')
st.session_state.setdefault('folder_path', [('My Drive', 'root')])
st.session_state.setdefault('selected_drive_folder_id', None)

# --- Google Drive Authentication & API Functions ---
def get_google_auth_flow():
    return Flow.from_client_secrets_file(CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)

def google_callback():
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
            st.rerun() 
        except Exception as e:
            st.error(f"Authentication failed: {e}")

# FIX: Removed the @st.cache_resource decorator to prevent state inconsistencies
def get_drive_service(creds_dict):
    """Builds the Google Drive service object from credentials."""
    if not creds_dict: return None
    try:
        creds = Credentials.from_authorized_user_info(creds_dict, SCOPES)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        # If credentials fail for any reason, log out the user to be safe
        st.error(f"Failed to build drive service, please log in again: {e}")
        st.session_state.credentials = None
        return None

def list_folders_in_drive(service, folder_id='root'):
    query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    try:
        results = service.files().list(q=query, pageSize=100, fields="files(id, name)").execute()
        return sorted(results.get('files', []), key=lambda x: x['name'].lower())
    except HttpError as error:
        st.error(f"An error occurred while fetching folders: {error}")
        return []

def list_resumes_in_drive(service, folder_id):
    query = f"'{folder_id}' in parents and (mimeType='application/pdf' or mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document') and trashed = false"
    try:
        results = service.files().list(q=query, pageSize=50, fields="files(id, name, mimeType)").execute()
        return results.get('files', [])
    except HttpError as error:
        st.error(f"An error occurred while fetching files: {error}")
        return []

def download_drive_file(service, file_id, file_name):
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done: _, done = downloader.next_chunk()
    fh.seek(0)
    return {'name': file_name, 'bytes': fh.getvalue()}

# --- Main App Logic & UI ---
if 'code' in st.query_params and not st.session_state.credentials:
    google_callback()

st.title("🤖 TalentLens: Automated Resume Analyzer")

drive_service = get_drive_service(st.session_state.credentials)

with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Enter your Gemini API Key", type="password")
    llm_model = st.selectbox("Select LLM Model", ("gemini-2.0-flash", "gemini-2.5-pro"), index=0)
    st.divider()
    st.header("🔗 Connect to Google Drive")
    if not drive_service:
        auth_url, _ = get_google_auth_flow().authorization_url(prompt='consent')
        st.link_button("Login with Google", auth_url)
    else:
        st.success("Connected to Google Drive!")
        if st.button("Logout from Google"):
            st.session_state.credentials = None
            st.session_state.current_folder_id = 'root'
            st.session_state.folder_path = [('My Drive', 'root')]
            st.session_state.drive_files = []
            st.rerun()

st.subheader("1. Enter Job Description")
job_description = st.text_area("Paste the Job Description here", height=250, placeholder="e.g., Senior Python Developer...")

st.subheader("2. Select Resumes")
tab1, tab2 = st.tabs(["📂 Local Upload", "☁️ Google Drive"])

with tab1:
    uploaded_files = st.file_uploader("Upload resumes (PDF or DOCX)", type=["pdf", "docx"], accept_multiple_files=True)

with tab2:
    if not drive_service:
        st.warning("Please login with Google in the sidebar to browse your Drive.")
    else:
        st.markdown("#### Navigate to Your Resumes Folder")
        path_str = " / ".join([name for name, id in st.session_state.folder_path])
        st.info(f"Current Path: **{path_str}**")

        if len(st.session_state.folder_path) > 1:
            if st.button("⬆️ Go to Parent Folder"):
                st.session_state.folder_path.pop()
                st.session_state.current_folder_id = st.session_state.folder_path[-1][1]
                st.session_state.drive_files = []
                st.rerun()

        folders = list_folders_in_drive(drive_service, st.session_state.current_folder_id)
        
        # Use a dictionary for easier lookup
        folder_dict = {f['name']: f['id'] for f in folders}
        selected_folder_name = st.selectbox("Select a folder to open:", list(folder_dict.keys()), index=None, placeholder="Choose a sub-folder...")

        if selected_folder_name:
            folder_id = folder_dict[selected_folder_name]
            st.session_state.current_folder_id = folder_id
            st.session_state.folder_path.append((selected_folder_name, folder_id))
            st.session_state.drive_files = []
            st.rerun()

        st.divider()

        if st.button(f"✅ Use this folder and list resumes", type="primary"):
            st.session_state.selected_drive_folder_id = st.session_state.current_folder_id
            with st.spinner("Fetching resume files..."):
                st.session_state.drive_files = list_resumes_in_drive(drive_service, st.session_state.selected_drive_folder_id)

        if st.session_state.drive_files:
            st.markdown("#### Select Resumes to Analyze")
            selected_drive_files = st.multiselect(
                "Select from the files found in the chosen folder:",
                options=st.session_state.drive_files, format_func=lambda x: x['name']
            )

# --- Analysis Logic ---
if st.button("Analyze Resumes", use_container_width=True):
    # Logic to process files and call backend...
    # (This section remains unchanged)
    files_to_process = []
    if uploaded_files:
        for f in uploaded_files:
            files_to_process.append({'name': f.name, 'bytes': f.getvalue(), 'type': f.type})
    
    if 'selected_drive_files' in locals() and selected_drive_files:
        with st.spinner("Downloading selected files from Google Drive..."):
            for drive_file in selected_drive_files:
                file_content = download_drive_file(drive_service, drive_file['id'], drive_file['name'])
                files_to_process.append({
                    'name': file_content['name'], 'bytes': file_content['bytes'], 'type': drive_file['mimeType']
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
                response = requests.post(BACKEND_URL, files=files_payload, data=data_payload, headers=headers, timeout=120)
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
    # (This section remains unchanged)
    st.divider()
    st.subheader("📊 Analysis Results")
    df = pd.DataFrame(st.session_state.results).sort_values(by="relevance_score", ascending=False).reset_index(drop=True)

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