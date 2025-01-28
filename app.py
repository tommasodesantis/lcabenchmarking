import os
import streamlit as st
from r2r import R2RClient

# Set page config
st.set_page_config(
    page_title="LCA Benchmarking Tool",
    page_icon="🌍",
    layout="wide"
)

# Initialize session state for authentication
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def authenticate(username, password):
    return (username == st.secrets.credentials.username and 
            password == st.secrets.credentials.password)

# Login form
if not st.session_state.authenticated:
    st.title("Login")
    st.markdown("Please login to access the LCA Benchmarking Tool")
    
    # Create login form using columns for better layout
    col1, col2 = st.columns([2,1])
    with col1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if username == st.secrets.credentials.username and password == st.secrets.credentials.password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid username or password")
    st.stop()

# Main app content (only shown when authenticated)
st.title("LCA Benchmarking Analysis")
st.markdown("Enter your query about environmental metrics for retrieval and benchmarking.")

# Add logout button to sidebar
with st.sidebar:
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()

# Initialize the client
@st.cache_resource
def get_client():
    # Get API key from environment variable or Streamlit secrets
    api_key = os.getenv("R2R_API_KEY") or st.secrets["R2R_API_KEY"]
    # Set the API key in environment variable before initializing client
    os.environ["R2R_API_KEY"] = api_key
    return R2RClient("https://api.cloud.sciphi.ai")

# Define custom system prompt for environmental metrics benchmarking
custom_prompt = """You are an environmental metrics expert focused on quick retrieval and benchmarking of LCA data. Your purpose is to:

1. Quickly retrieve and present environmental metrics from the knowledge base
2. Help users benchmark their LCA data against reference values
3. Provide clear but concise comparisons with proper citations
4. Use tables at the bottom of the response to visualize the comparisons when necessary 

When responding:
- Always cite your sources using [1], [2], etc. and adding a reference section at the explaining what are the sources connected to the numbers.
- Always mention year, country, date and scope of the data. If any of this info is not available, state it clearly
- Highlight any limitations or assumptions
- If benchmarking user data, try to clearly hypothesize any deviations from reference values

Query: {query}

Context: {context}

Response:"""

# Create the Streamlit interface
query = st.text_area("Enter your environmental metrics query:", "My honey in a glass has a carbon footprint of 1 kg CO2eq/kg, how does it benchmark?", height=100)

if st.button("Analyze"):
    with st.spinner("Analyzing..."):
        try:
            client = get_client()
            response = client.retrieval.rag(
                query,
                rag_generation_config={
                    "model": "openai/gpt-4o-mini",
                    "temperature": 0.7,
                    "stream": False
                },
                task_prompt_override=custom_prompt
            )
            # Extract just the completion from the response
            if isinstance(response, dict) and 'results' in response:
                completion = response['results'].get('completion', '')
                st.markdown("### Analysis Results")
                st.markdown(completion)
            else:
                st.error("Unexpected response format")
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.info("Please check your API key and try again.")

# Add sidebar with information
with st.sidebar:
    st.header("About")
    st.markdown("""
    This tool helps retrieve and benchmark environmental metrics using AI connected to an LCA database.
    
    Enter your query about environmental impacts, carbon footprints, or other 
    sustainability metrics to get data and comparisons.
    """)
