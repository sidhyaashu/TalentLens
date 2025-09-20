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

# --- Page Configuration ---
st.set_page_config(
    page_title="TalentLens Resume Analyzer",
    page_icon="🤖",
    layout="wide"
)

# --- Constants ---
API_BASE_URL = "http://localhost:8000/api" # Use service name for Docker networking
CREDENTIALS_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
REDIRECT_URI = 'http://localhost:8501' # Your Streamlit URL
STATUS_OPTIONS = ["New", "Shortlisted", "Interviewing", "Rejected", "Hired"]

# --- Session State Initialization ---
st.session_state.setdefault('selected_jd', None)
st.session_state.setdefault('credentials', None)
st.session_state.setdefault('gdrive_current_folder_id', 'root')
st.session_state.setdefault('gdrive_folder_path', [('My Drive', 'root')])
st.session_state.setdefault('gdrive_selected_folder', None)
st.session_state.setdefault('search_term', "")


# --- Backend API Functions ---
@st.cache_data(ttl=300)
def get_jds():
    """Fetches all Job Descriptions from the backend."""
    try:
        r = requests.get(f"{API_BASE_URL}/jobs/")
        if r.status_code == 200:
            return r.json()
    except requests.RequestException as e:
        st.error(f"Failed to connect to backend: {e}")
    return []

def create_jd(title, description):
    """Creates a new Job Description."""
    try:
        r = requests.post(f"{API_BASE_URL}/jobs/", json={"title": title, "description": description})
        if r.status_code == 200:
            st.success("Job Description created successfully!")
            st.cache_data.clear() # Clear cache to fetch the new list
            return r.json()
        st.error(f"Failed to create JD: {r.text}")
    except requests.RequestException as e:
        st.error(f"Connection error: {e}")
    return None

@st.cache_data(ttl=10) # Cache results for a short time
def get_results_for_jd(jd_id, search=None):
    """Fetches analysis results for a given Job Description."""
    if not jd_id:
        return []
    try:
        params = {"search": search} if search else {}
        r = requests.get(f"{API_BASE_URL}/jobs/{jd_id}/results", params=params)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return []

def update_candidate_status(result_id, status):
    """Updates the status of a candidate's analysis result."""
    try:
        r = requests.put(f"{API_BASE_URL}/results/{result_id}/status", json={"status": status})
        return r.status_code == 200
    except requests.RequestException:
        return False

# --- Google Drive Functions ---
def get_google_auth_flow():
    """Initializes the Google OAuth flow."""
    try:
        return Flow.from_client_secrets_file(CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    except FileNotFoundError:
        st.error(f"Required credentials file not found: {CREDENTIALS_FILE}")
        return None

def google_callback():
    """Handles the redirect from Google's OAuth screen."""
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
            st.error(f"Authentication token fetch failed: {e}")

def get_drive_service(_creds):
    """Builds the Google Drive API service from credentials."""
    if not _creds:
        return None
    try:
        creds = Credentials.from_authorized_user_info(_creds, SCOPES)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Failed to build Google Drive service: {e}. Please log in again.")
        st.session_state.credentials = None # Clear bad credentials
        return None

def list_folders_in_drive(service, folder_id):
    """Lists sub-folders within a given Google Drive folder."""
    q = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    try:
        r = service.files().list(q=q, pageSize=200, fields="files(id, name)").execute()
        return sorted(r.get('files', []), key=lambda x: x['name'].lower())
    except HttpError:
        return []

def list_resumes_in_drive(service, folder_id):
    """Lists resume files (PDF, DOCX) within a given Google Drive folder."""
    q = f"'{folder_id}' in parents and (mimeType='application/pdf' or mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document') and trashed=false"
    try:
        r = service.files().list(q=q, pageSize=100, fields="files(id, name, mimeType)").execute()
        return r.get('files', [])
    except HttpError:
        return []

def download_drive_file(service, file_id):
    """Downloads a file's content from Google Drive."""
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)
    return fh.getvalue()

# --- Main App Logic ---
if 'code' in st.query_params and not st.session_state.credentials:
    google_callback()

st.title("🤖 TalentLens: Automated Resume Analyzer")

# --- Sidebar for Configuration and JD Management ---
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Enter your Gemini API Key", type="password", help="Your Google AI Studio API key.")
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
            placeholder="Choose a JD to work with..."
        )
        if selected_jd_title and st.session_state.selected_jd != jd_options[selected_jd_title]:
            st.session_state.selected_jd = jd_options[selected_jd_title]
            st.rerun()
    else:
        st.warning("No Job Descriptions found. Please create one.")

    with st.expander("Create New Job Description"):
        jd_title = st.text_input("Job Title")
        jd_desc = st.text_area("Job Description Text", height=150)
        if st.button("Save New JD"):
            if jd_title and jd_desc:
                if create_jd(jd_title, jd_desc):
                    st.rerun()
            else:
                st.warning("Please provide both a title and description.")

# --- Main Content Area ---
if not st.session_state.selected_jd:
    st.info("👋 Welcome to TalentLens! Please select or create a Job Description in the sidebar to begin.")
else:
    jd_id = st.session_state.selected_jd
    tab_analytics, tab_candidates, tab_upload = st.tabs(["📊 Dashboard Analytics", "📄 Candidate Results", "📤 Upload & Analyze"])

    # Fetch data once for all tabs
    results = get_results_for_jd(jd_id, st.session_state.search_term)
    df = pd.DataFrame(results) if results else pd.DataFrame()

    with tab_analytics:
        st.header("Dashboard Analytics")
        if df.empty:
            st.warning("No candidate data available. Upload resumes to see analytics.")
        else:
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Candidates", len(df))
            avg_score = df['relevance_score'].mean() if not df.empty else 0
            col2.metric("Average Score", f"{avg_score:.2f}%")
            col3.metric("Shortlisted", df[df['status'] == 'Shortlisted'].shape[0])
            st.write("---")
            c1, c2 = st.columns(2)
            verdict_counts = df['verdict'].value_counts().reset_index()
            fig_v = px.pie(verdict_counts, names='verdict', values='count', title='Verdict Distribution')
            c1.plotly_chart(fig_v, use_container_width=True)
            fig_s = px.histogram(df, x='relevance_score', nbins=20, title='Score Distribution')
            c2.plotly_chart(fig_s, use_container_width=True)

    # with tab_candidates:
    #     st.header("Candidate Results")
    #     if df.empty:
    #         st.info("No candidate results yet for this job description.")
    #     else:
    #         st.text_input("Search candidates by filename, skills, etc.", key="search_term", on_change=lambda: st.rerun())
            
    #         for _, row in df.iterrows():
    #             st.markdown("---")
    #             c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    #             c1.markdown(f"**{row['filename']}**")
    #             c2.metric("Score", f"{row['relevance_score']:.2f}%")
                
    #             # Ensure status from DB is valid, otherwise default to 'New'
    #             current_status = row.get('status', 'New')
    #             try:
    #                 idx = STATUS_OPTIONS.index(current_status)
    #             except ValueError:
    #                 idx = 0 # Default to 'New' if status is unrecognized
                
    #             new_status = c3.selectbox("Status", STATUS_OPTIONS, index=idx, key=f"status_{row['id']}")
                
    #             if new_status != current_status:
    #                 if update_candidate_status(row['id'], new_status):
    #                     st.success(f"Updated {row['filename']} to '{new_status}'")
    #                     st.rerun() # Refresh data after update
    #                 else:
    #                     st.error("Failed to update status.")
                        
    #             with c4:
    #                 # Disable button if no email is found
    #                 disable_button = not row.get('student_email')
    #                 if st.button("Send Feedback", key=f"send_{row['id']}", disabled=disable_button, use_container_width=True):
    #                     try:
    #                         response = requests.post(f"{API_BASE_URL}/results/{row['id']}/send-feedback")
    #                         if response.status_code == 202:
    #                             st.success(f"Feedback email sent to {row['student_email']}!")
    #                         else:
    #                             st.error(f"Error: {response.json().get('detail', 'Unknown error')}")
    #                     except requests.RequestException as e:
    #                         st.error(f"Connection error: {e}")

    #             with st.expander("View Detailed Analysis"):
    #                 st.markdown("##### 🔍 Missing Elements")
    #                 st.info(row['missing_elements'])
    #                 st.markdown("##### 💡 Improvement Suggestions")
    #                 st.success(row['improvement_suggestions'])
    with tab_candidates:
        st.header("Candidate Pipeline")

        if df.empty:
            st.info("No candidate results yet for this job description. Upload resumes in the next tab!")
        else:
            # The search bar now filters the main DataFrame before it's split into tabs
            st.text_input("Search all candidates by filename, skills, etc.", key="search_term", on_change=lambda: st.rerun())

            # Create the tabs dynamically from your STATUS_OPTIONS list
            tab_list = st.tabs([f"**{status}**" for status in STATUS_OPTIONS])

            # Iterate through each status and its corresponding tab
            for i, status in enumerate(STATUS_OPTIONS):
                with tab_list[i]:
                    # Filter the DataFrame for the current tab's status
                    status_df = df[df['status'] == status]

                    st.markdown(f"#### {len(status_df)} candidate(s) in this stage.")

                    if status_df.empty:
                        st.info(f"No candidates are currently in the '{status}' stage.")
                    else:
                        # Display each candidate within the correct tab
                        for _, row in status_df.iterrows():
                            st.markdown("---")
                            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])

                            with c1:
                                st.markdown(f"**{row['filename']}**")
                                if row.get('student_email'):
                                    st.caption(f"✉️ {row['student_email']}")
                                else:
                                    st.caption("Email not found in resume")

                            c2.metric("Score", f"{row['relevance_score']:.2f}%")

                            # The status dropdown now works within each filtered tab
                            current_status = row.get('status', 'New')
                            try:
                                idx = STATUS_OPTIONS.index(current_status)
                            except ValueError:
                                idx = 0

                            new_status = c3.selectbox("Change Status", STATUS_OPTIONS, index=idx, key=f"status_{row['id']}")

                            if new_status != current_status:
                                if update_candidate_status(row['id'], new_status):
                                    st.success(f"Moved {row['filename']} to '{new_status}'")
                                    # Rerun to refresh the data and move the candidate to the correct tab
                                    st.rerun()
                                else:
                                    st.error("Failed to update status.")

                            with c4:
                                disable_button = not row.get('student_email')
                                if st.button("Send Feedback", key=f"send_{row['id']}", disabled=disable_button, use_container_width=True, help="Sends feedback email via n8n. Disabled if no email was found."):
                                    try:
                                        response = requests.post(f"{API_BASE_URL}/results/{row['id']}/send-feedback")
                                        if response.status_code == 202:
                                            st.success(f"Feedback queued for {row['student_email']}!")
                                        else:
                                            st.error(f"Error: {response.json().get('detail', 'Unknown error')}")
                                    except requests.RequestException as e:
                                        st.error(f"Connection error: {e}")

                            with st.expander("View Detailed Analysis"):
                                st.markdown("##### 🔍 Missing Elements")
                                st.info(row['missing_elements'])
                                st.markdown("##### 💡 Improvement Suggestions")
                                st.success(row['improvement_suggestions'])
                                
    with tab_upload:
        st.header("Upload & Analyze New Resumes")
        col_local, col_gdrive = st.columns(2)

        with col_local:
            st.markdown("#### 📂 Local Upload")
            local_files = st.file_uploader("Upload resumes from your computer", type=["pdf", "docx"], accept_multiple_files=True)

        with col_gdrive:
            st.markdown("#### ☁️ Google Drive")
            drive_service = get_drive_service(st.session_state.credentials)
            if not drive_service:
                flow = get_google_auth_flow()
                if flow:
                    auth_url, _ = flow.authorization_url(prompt='consent')
                    # This is the corrected login button
                    st.link_button("🔑 Login with Google", auth_url)
                else:
                    st.warning("Google Drive not available.")
            else:
                st.success("Connected to Google Drive ✅")
                if st.button("⬆️ Parent Folder"):
                    if len(st.session_state.gdrive_folder_path) > 1:
                        st.session_state.gdrive_folder_path.pop()
                        st.session_state.gdrive_current_folder_id = st.session_state.gdrive_folder_path[-1][1]
                        st.rerun()

                path_str = " / ".join([n for n, _ in st.session_state.gdrive_folder_path])
                st.info(f"Current Path: {path_str}")

                folders = list_folders_in_drive(drive_service, st.session_state.gdrive_current_folder_id)
                folder_names = [f['name'] for f in folders]

                def on_folder_select():
                    sel = st.session_state.gdrive_selected_folder
                    if sel:
                        folder_id = next((f['id'] for f in folders if f['name']==sel), None)
                        if folder_id:
                            st.session_state.gdrive_current_folder_id = folder_id
                            st.session_state.gdrive_folder_path.append((sel, folder_id))
                            # No rerun here, let the UI update naturally

                st.selectbox("Open sub-folder", folder_names, index=None, placeholder="Select a folder...", key='gdrive_selected_folder', on_change=on_folder_select)

                drive_resumes = list_resumes_in_drive(drive_service, st.session_state.gdrive_current_folder_id)
                selected_drive_files = st.multiselect("Select resumes from this folder", drive_resumes, format_func=lambda f: f['name'])

        st.divider()
        if st.button("🚀 Analyze Selected Resumes", use_container_width=True, type="primary"):
            files_to_process = []
            if local_files:
                for f in local_files:
                    files_to_process.append({'name': f.name, 'bytes': f.getvalue(), 'type': f.type})

            if 'selected_drive_files' in locals() and selected_drive_files:
                with st.spinner("Downloading files from Google Drive..."):
                    for f in selected_drive_files:
                        file_bytes = download_drive_file(drive_service, f['id'])
                        files_to_process.append({'name': f['name'], 'bytes': file_bytes, 'type': f['mimeType']})

            if not api_key:
                st.error("Please enter your Gemini API Key in the sidebar before analyzing.")
            elif not files_to_process:
                st.error("No resumes selected. Please upload or select files from Google Drive.")
            else:
                progress_bar = st.progress(0, text="Starting analysis...")
                for i, f_data in enumerate(files_to_process):
                    progress_text = f"Submitting {f_data['name']} for analysis..."
                    progress_bar.progress((i + 1) / len(files_to_process), text=progress_text)
                    try:
                        files_payload = {'resume': (f_data['name'], f_data['bytes'], f_data['type'])}
                        data_payload = {'jd_id': jd_id}
                        headers = {'X-API-Key': api_key, 'X-LLM-Model': llm_model}
                        
                        r = requests.post(f"{API_BASE_URL}/analyze/", files=files_payload, data=data_payload, headers=headers)
                        
                        if r.status_code != 200:
                            st.error(f"Failed to submit {f_data['name']}: {r.json().get('detail', 'Unknown error')}")
                    except requests.RequestException as e:
                        st.error(f"Connection error while submitting {f_data['name']}: {e}")
                
                progress_bar.empty()
                st.success("All selected resumes have been submitted for background analysis! Results will appear in the 'Candidate Results' tab shortly.")