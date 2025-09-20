import streamlit as st
import requests
import pandas as pd
import time

# --- Page Configuration ---
st.set_page_config(
    page_title="TalentLens Resume Analyzer",
    page_icon="🤖",
    layout="wide"
)

# --- Constants ---
API_BASE_URL = "http://localhost:8000/api"

# --- Session State Initialization ---
st.session_state.setdefault('results', [])
st.session_state.setdefault('selected_jd', None)
st.session_state.setdefault('job_descriptions', [])

# --- API Functions ---
def get_jds():
    try:
        response = requests.get(f"{API_BASE_URL}/jobs/")
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Failed to fetch Job Descriptions: {response.text}")
            return []
    except requests.RequestException as e:
        st.error(f"Connection error: {e}")
        return []

def create_jd(title, description):
    try:
        payload = {"title": title, "description": description}
        response = requests.post(f"{API_BASE_URL}/jobs/", json=payload)
        if response.status_code == 200:
            st.success("Job Description created successfully!")
            return response.json()
        else:
            st.error(f"Failed to create JD: {response.text}")
            return None
    except requests.RequestException as e:
        st.error(f"Connection error: {e}")
        return None

def get_results_for_jd(jd_id):
    try:
        response = requests.get(f"{API_BASE_URL}/jobs/{jd_id}/results")
        if response.status_code == 200:
            return response.json()
    except requests.RequestException:
        return [] # Return empty list on error

st.title("🤖 TalentLens: Automated Resume Analyzer")

# --- Sidebar for Configuration and JD Management ---
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Enter your Gemini API Key", type="password")
    llm_model = st.selectbox("Select LLM Model", ("gemini-1.5-flash", "gemini-1.5-pro"), index=0)

    st.divider()
    st.header("📋 Job Descriptions")

    if st.button("Refresh JD List"):
        st.session_state.job_descriptions = get_jds()
        st.rerun()

    if not st.session_state.job_descriptions:
        st.session_state.job_descriptions = get_jds()

    jd_options = {jd['title']: jd['id'] for jd in st.session_state.job_descriptions}
    selected_jd_title = st.selectbox(
        "Select a Job Description",
        options=jd_options.keys(),
        index=None,
        placeholder="Choose a JD to view/analyze"
    )
    if selected_jd_title:
        jd_id = jd_options[selected_jd_title]
        st.session_state.selected_jd = next((jd for jd in st.session_state.job_descriptions if jd['id'] == jd_id), None)

    with st.expander("Create New Job Description"):
        jd_title = st.text_input("Job Title")
        jd_desc = st.text_area("Job Description Text", height=150)
        if st.button("Save New JD"):
            if jd_title and jd_desc:
                new_jd = create_jd(jd_title, jd_desc)
                if new_jd:
                    st.session_state.job_descriptions = get_jds() # Refresh list
                    st.rerun()
            else:
                st.warning("Please provide both title and description.")

# --- Main Content ---
if not st.session_state.selected_jd:
    st.info("👋 Welcome to TalentLens! Please select a Job Description from the sidebar to begin, or create a new one.")
else:
    jd = st.session_state.selected_jd
    st.header(f"Analyzing for: {jd['title']}")

    with st.expander("View Job Description Details"):
        st.text(jd['description'])

    st.subheader("📤 Upload Resumes for Analysis")
    uploaded_files = st.file_uploader(
        "Upload resumes (PDF or DOCX)",
        type=["pdf", "docx"],
        accept_multiple_files=True
    )

    if st.button("Analyze Resumes", use_container_width=True, type="primary"):
        if not api_key:
            st.error("Please enter your Gemini API Key in the sidebar.")
        elif not uploaded_files:
            st.error("Please upload at least one resume.")
        else:
            progress_bar = st.progress(0, text="Starting Analysis...")
            for i, file in enumerate(uploaded_files):
                progress_text = f"Uploading {file.name}..."
                progress_bar.progress((i + 1) / len(uploaded_files), text=progress_text)
                try:
                    files_payload = {'resume': (file.name, file.getvalue(), file.type)}
                    data_payload = {'jd_id': jd['id']}
                    headers = {'X-API-Key': api_key, 'X-LLM-Model': llm_model}
                    response = requests.post(f"{API_BASE_URL}/analyze/", files=files_payload, data=data_payload, headers=headers)
                    if response.status_code != 200:
                        st.error(f"Failed to start analysis for {file.name}: {response.text}")
                except requests.RequestException as e:
                    st.error(f"Connection error for {file.name}: {e}")

            progress_bar.empty()
            st.success("All resumes have been sent for analysis. Results will appear below as they are processed. Click 'Refresh Results' to update.")


    # --- Results Dashboard ---
    st.divider()
    st.subheader("📊 Analysis Results")
    if st.button("Refresh Results"):
        st.rerun()

    results_placeholder = st.empty()
    with results_placeholder.container():
        results_data = get_results_for_jd(jd['id'])
        if not results_data:
            st.info("No analysis results found for this job description yet.")
        else:
            df = pd.DataFrame(results_data).sort_values(by="relevance_score", ascending=False).reset_index(drop=True)

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