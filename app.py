import os
import json
import requests
import streamlit as st
import nest_asyncio
from typing import List, Dict, Any
from r2r import R2RClient
import asyncio

# Enable nested asyncio
nest_asyncio.apply()

# Set page config
st.set_page_config(
    page_title="LCA Benchmarking Tool",
    page_icon="🌍",
    layout="wide"
)

class LCAAnalyzer:
    def __init__(self, r2r_api_key: str, openrouter_api_key: str):
        self.r2r_api_key = r2r_api_key
        self.openrouter_api_key = openrouter_api_key
        self.client = R2RClient("https://api.cloud.sciphi.ai")
        
        self.retrieval_prompt = """You are an environmental metrics expert focused on quick retrieval and benchmarking of LCA data. Your purpose is to:
1. Quickly retrieve and present environmental metrics from the knowledge base
2. Help users benchmark their LCA data against reference values
3. Provide clear but concise comparisons with proper citations
4. Always generate a table which provides a clear overview of all the RELEVANT collected data for benchmarking
5. Always add a reference section at the end of the answer, ALWAYS mention the name of the database if available (if not, it is "IDEMAT 2025").

When responding:
- Always cite your sources using [1], [2], etc. and adding a reference section explaining what are the sources connected to the numbers.
- Always mention year, country, date and scope of the data. If any of this info is not available, state it clearly
- Highlight any limitations or assumptions
- If benchmarking user data, try to clearly hypothesize any deviations from reference values
- Don't do calculations, limit yourself to present the available data."""

        self.web_search_prompt = """You are an environmental metrics expert. Your task is to search the web and provide relevant information about environmental metrics and LCA data. Focus on:
1. Recent and reliable data sources
2. Scientific publications and official reports
3. Clear comparisons and benchmarks
4. ALWAYS incldue proper attribution of sources with links

Keep your response focused and analytical."""

        self.merger_prompt = """You are an environmental metrics expert. Your task is to merge and synthesize information from two sources:
1. A vector database search result containing verified LCA data
2. A web search result containing broader context and recent information

Create a unified response that:
1. Prioritizes verified database information but enriches it with web context
2. Clearly distinguishes between database and web sources
3. Highlights any discrepancies or complementary information
4. Maintains proper citation format [1], [2], etc.
5. Provides a clear, structured comparison generating a table at the bottom of the answer which provides a clear overview of all the RELEVANT collected data for benchmarking
6. Always add a reference section at the end of the answer, for sources coming from the web ALWAYS add links if available and for sources coming from the database ALWAYS mention the name of the database if available."""

    def get_chunks(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        response = self.client.retrieval.search(
            query=query,
            search_settings={
                "limit": limit
            }
        )
        return response["results"]["chunk_search_results"]

    async def process_with_llm(self, query: str, context: str, model: str, system_prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8888",
            "X-Title": "LCA Analysis Tool"
        }
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Query: {query}\n\nContext: {context}"}
        ]
        
        payload = {
            "model": model,
            "messages": messages
        }
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload
        )
        result = response.json()
        return result["choices"][0]["message"]["content"]

    async def web_search(self, query: str) -> str:
        return await self.process_with_llm(
            query=query,
            context="Please search the web for relevant LCA and environmental metrics data.",
            model="perplexity/sonar-reasoning",
            system_prompt=self.web_search_prompt
        )

    async def merge_results(self, database_result: str, web_result: str, query: str) -> str:
        context = f"""Database Search Results:
{database_result}

Web Search Results:
{web_result}"""

        return await self.process_with_llm(
            query=query,
            context=context,
            model="openai/gpt-4o-mini",
            system_prompt=self.merger_prompt
        )

    async def analyze(self, query: str, include_web_search: bool = False) -> str:
        chunks = self.get_chunks(query)
        context = "\n\n".join([chunk["text"] for chunk in chunks])
        
        if not include_web_search:
            return await self.process_with_llm(
                query=query,
                context=context,
                model="openai/gpt-4o-mini",
                system_prompt=self.retrieval_prompt
            )
        else:
            database_result = await self.process_with_llm(
                query=query,
                context=context,
                model="openai/gpt-4o-mini",
                system_prompt=self.retrieval_prompt
            )
            
            web_result = await self.web_search(query)
            
            return await self.merge_results(database_result, web_result, query)

# Initialize session state for authentication
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def authenticate(username, password):
    return (username == st.secrets.credentials.username and 
            password == st.secrets.credentials.password)

# Login form
if not st.session_state.authenticated:
    left_col, center_col, right_col = st.columns([1,2,1])
    
    with center_col:
        st.title("🌱 Welcome to LCA Benchmarker")       
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login", use_container_width=True):
            if authenticate(username, password):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid username or password")
    st.stop()

# Main app content (only shown when authenticated)
st.title("LCA Benchmarking Analysis")

# Add logout button to sidebar
with st.sidebar:
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()

    st.header("About")
    st.markdown("""
    This tool helps retrieve and benchmark environmental metrics using AI connected to an LCA database (currently only Idemat).

    I'm working on expanding the database to include as many LCA data as possible from published studies. 
                
    My mission is to help LCA professionals to benchmark their results instantly and accurately.
    
    ---
    Developed by [Tommaso De Santis](https://www.linkedin.com/in/tommaso-de-santis/)
    """)

# Initialize the analyzer
@st.cache_resource
def get_analyzer():
    return LCAAnalyzer(
        r2r_api_key=st.secrets["R2R_API_KEY"],
        openrouter_api_key=st.secrets["OPENROUTER_API_KEY"]
    )

# Create the Streamlit interface
include_web_search = st.toggle('Include web search', value=False, 
    help='Enable to search both database and web sources. The analysis might take up to a few minutes.')

query = st.text_area(
    "Enter your environmental metrics query:", 
    "My honey in a glass has a carbon footprint of 1 kg CO2eq/kg, how does it benchmark?", 
    height=100
)

if st.button("Analyze"):
    analyzer = get_analyzer()
    
    try:
        with st.spinner("Analyzing..."):
            # Create a placeholder for the progress
            progress_placeholder = st.empty()
            
            # Run the analysis
            if include_web_search:
                progress_placeholder.text("Searching database and web, this might take a few minutes...")
            result = asyncio.run(analyzer.analyze(query, include_web_search))
            
            if include_web_search:
                progress_placeholder.text("Merging results...")
            
            # Clear the progress placeholder
            progress_placeholder.empty()
            
            # Display results
            st.markdown("### Analysis Results")
            st.markdown(result)
            
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.info("Please check your API keys and try again.")
