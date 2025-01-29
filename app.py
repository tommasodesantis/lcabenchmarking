import os
import json
import requests
import aiohttp
import streamlit as st
import nest_asyncio
from typing import List, Dict, Any, Union, AsyncGenerator
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
5. Always add a reference section at the end of the answer, ALWAYS mention the name of the database if available (if not, it is "IDEMAT 2025" add also its clickable link https://www.ecocostsvalue.com/data-tools-books/).

When responding:
- Always cite your sources using [1], [2], etc. and adding a reference section explaining what are the sources connected to the numbers.
- Always mention year, country, date and scope of the data. If any of this info is not available, state it clearly
- Highlight any limitations or assumptions
- Make sure that units of measurement are always clearly presented next to relative values (also in tables)
- If benchmarking user data, try to clearly hypothesize any deviations from reference values
- Don't do calculations, limit yourself to present the available relevant data."""

        self.web_search_prompt = """You are an environmental metrics expert. Your task is to search the web and provide relevant information about environmental metrics and LCA data. Focus on:
1. Reliable data sources
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
5. Don't include calculations made by you, limit yourself to present the available relevant data.
5. Provides a clear, structured comparison generating a table at the bottom of the answer which provides a clear overview of all the RELEVANT collected data for benchmarking
6. Make sure that units of measurement are always clearly presented next to relative values (also in tables)
7. Always add a reference section at the end of the answer, for sources coming from the web ALWAYS add clickable links if available and for sources coming from the database ALWAYS mention the name of the database if available (if not it is "IDEMAT 2025", link is https://www.ecocostsvalue.com/data-tools-books/)."""

    def get_chunks(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        response = self.client.retrieval.search(
            query=query,
            search_settings={
                "limit": limit
            }
        )
        return response["results"]["chunk_search_results"]

    def parse_sse_chunk(self, chunk: bytes) -> str:
        """Parse a chunk of SSE data and extract the content."""
        if not chunk:
            return ""
        
        try:
            data = json.loads(chunk.decode('utf-8').split('data: ')[1])
            if data.get('choices') and len(data['choices']) > 0:
                delta = data['choices'][0].get('delta', {})
                return delta.get('content', '')
        except (json.JSONDecodeError, IndexError, KeyError):
            pass
        return ""

    async def process_with_llm(self, query: str, context: str, model: str, system_prompt: str, use_streaming: bool = True) -> Union[str, AsyncGenerator[str, None]]:
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
            "messages": messages,
            "temperature": 0.7,
            "stream": use_streaming
        }

        try:
            if use_streaming:
                async def stream_response():
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers=headers,
                            json=payload
                        ) as response:
                            async for line in response.content:
                                if line:
                                    content = self.parse_sse_chunk(line)
                                    if content:
                                        yield content
                return stream_response()
            else:
                # Fallback to non-streaming
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload
                )
                result = response.json()
                return result["choices"][0]["message"]["content"]
        except Exception as e:
            if use_streaming:
                # If streaming fails, fallback to non-streaming
                return await self.process_with_llm(query, context, model, system_prompt, use_streaming=False)
            raise e

    async def web_search(self, query: str) -> str:
        return await self.process_with_llm(
            query=query,
            context="Please search the web for relevant LCA and environmental metrics data.",
            model="perplexity/sonar-reasoning",
            system_prompt=self.web_search_prompt,
            use_streaming=False
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

    async def analyze(self, query: str, include_web_search: bool = False) -> Union[str, AsyncGenerator[str, None]]:
        chunks = self.get_chunks(query)
        context = "\n\n".join([chunk["text"] for chunk in chunks])
        
        if not include_web_search:
            return await self.process_with_llm(
                query=query,
                context=context,
                model="openai/gpt-4o-mini",
                system_prompt=self.retrieval_prompt,
                use_streaming=True
            )
        else:
            # For web search, we need to collect results before merging
            database_result = ""
            async for chunk in await self.process_with_llm(
                query=query,
                context=context,
                model="openai/gpt-4o-mini",
                system_prompt=self.retrieval_prompt,
                use_streaming=True
            ):
                database_result += chunk
            
            web_result = await self.web_search(query)
            
            # Stream the merged results
            return await self.process_with_llm(
                query=query,
                context=f"""Database Search Results:\n{database_result}\n\nWeb Search Results:\n{web_result}""",
                model="openai/gpt-4o-mini",
                system_prompt=self.merger_prompt,
                use_streaming=True
            )

# Initialize session state for authentication
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def authenticate(username, password):
    usernames = st.secrets.usernames
    passwords = st.secrets.passwords
    if username in usernames:
        idx = usernames.index(username)
        return password == passwords[idx]
    return False

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
        # Create placeholders for output
        progress_placeholder = st.empty()
        output_placeholder = st.empty()
        
        async def process_stream():
            accumulated_text = ""
            
            if include_web_search:
                progress_placeholder.text("Searching database and web, this might take a few minutes...")
            
            # Get the streaming response
            result = await analyzer.analyze(query, include_web_search)
            
            # Handle both streaming and non-streaming responses
            if isinstance(result, str):
                # Non-streaming response
                output_placeholder.markdown(result)
            else:
                # Streaming response
                output_placeholder.markdown("### Analysis Results")
                content_placeholder = st.empty()
                
                async for chunk in result:
                    accumulated_text += chunk
                    content_placeholder.markdown(accumulated_text)
            
            # Clear progress placeholder when done
            progress_placeholder.empty()
        
        # Run the async function
        asyncio.run(process_stream())
            
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.info("Please check your API keys and try again.")
