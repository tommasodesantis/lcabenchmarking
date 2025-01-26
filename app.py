import os
import streamlit as st
from r2r import R2RClient

# Set page config
st.set_page_config(
    page_title="LCA Benchmarking Tool",
    page_icon="🌍",
    layout="wide"
)

# Title and description
st.title("LCA Benchmarking Analysis")
st.markdown("Enter your query about environmental metrics for analysis and benchmarking.")

# Initialize the client
@st.cache_resource
def get_client():
    # Get API key from environment variable or Streamlit secrets
    api_key = os.getenv("R2R_API_KEY") or st.secrets["R2R_API_KEY"]
    # Set the API key in environment variable before initializing client
    os.environ["R2R_API_KEY"] = api_key
    return R2RClient("https://api.cloud.sciphi.ai")

# Define custom system prompt for LCA benchmarking
custom_prompt = """You are an expert LCA analyst specializing in benchmarking environmental metrics. Your task is to:

1. Compare any environmental metrics or values mentioned in the user's query with relevant data from the knowledge base
2. When comparing metrics:
   - Clearly state the units being compared
   - Note if metrics are from different system boundaries or functional units
   - Highlight if metrics are not directly comparable and explain why
   - Use citation numbers [1], [2], etc. to reference specific data points
3. If the user's values are:
   - Significantly higher: Suggest potential reasons and areas for improvement
   - Significantly lower: Flag this for verification and request more details about calculation methods
   - Within expected range: Confirm this and provide context from similar cases
4. Always specify:
   - The year of the reference data
   - Any relevant geographic or technological scope
   - Key assumptions that might affect the comparison

Query: {query}

Context: {context}

Provide a structured response with:
1. Direct comparison of metrics
2. Context and analysis
3. Recommendations or follow-up questions if needed

Remember: If crucial information is missing to make a fair comparison (such as functional unit or system boundaries), explicitly state what additional information would be needed.

Response:"""

# Create the Streamlit interface
query = st.text_area("Enter your environmental metrics query:", "What's the carbon footprint of honey?", height=100)

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
            st.markdown("### Analysis Results")
            st.write(response)
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.info("Please check your API key and try again.")

# Add sidebar with information
with st.sidebar:
    st.header("About")
    st.markdown("""
    This tool helps analyze and benchmark environmental metrics using LCA data.
    
    Enter your query about environmental impacts, carbon footprints, or other 
    sustainability metrics to get detailed analysis and comparisons.
    """)
