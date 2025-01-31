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

# Add custom CSS
st.markdown("""
<style>
.database-container {
    background-color: #e6f3ff;
    border-left: 3px solid #0066cc;
    padding: 15px;
    margin: 10px 0;
    border-radius: 5px;
}
.web-container {
    background-color: #e6ffe6;
    border-left: 3px solid #009933;
    padding: 15px;
    margin: 10px 0;
    border-radius: 5px;
}
</style>
""", unsafe_allow_html=True)

class LCAAnalyzer:
    def __init__(self, r2r_api_key: str, openrouter_api_key: str):
        self.r2r_api_key = r2r_api_key
        self.openrouter_api_key = openrouter_api_key
        self.client = R2RClient("https://api.cloud.sciphi.ai")
        
        self.retrieval_prompt = """You are an environmental metrics expert focused on precise retrieval and benchmarking of LCA data. Your purpose is to:

Retrieve and present environmental metrics from the knowledge base with attention to:

Available environmental impact indicators (eco-costs, ReCiPe, EF 3.1)
Process variants and specifications
System boundaries as defined in the database

Benchmark user data against reference values by:

Selecting most relevant comparisons based on product category and specifications
Considering different product variants (e.g., packaging types)
Comparing across multiple environmental indicators

Structure your response with:

Clear data presentation with proper citations [1], [2], etc.
Comprehensive overview table of relevant metrics
Transparent documentation of data gaps

When responding:

Present data with full context: process ID, unit, year (if available), country (if available)
Round decimal numerical values to 2 decimal places
Include all available environmental indicators unless asked otherwise
Don't mention which environmental impact indicators are available, just report those requested by the user or if the query is generic report carbon footprint, total eco-ecost, ReCiPe, EF 3.1
Don't introduce, overexplain or repeat things, go straight to the point
Use appropriate headers to separate sections
Specify if variants exist for the requested process
Always cite sources

Generate a structured comparison table with:

Clear units of measurement
Complete set of relevant available indicators
Process variants when available

References must:

Use consistent [1], [2] format
Include database name (default: "IDEMAT 2025" with link https://www.ecocostsvalue.com/data-tools-books/)

Do not:

Perform calculations or manipulate raw data, with the exception of rounding figures to 2 decimal places
Make assumptions without explicit documentation
Mix incompatible methodologies without clear warning"""

        self.web_search_prompt = """You are an environmental metrics expert conducting web-based LCA research. Focus on:

1. Source Evaluation:
   - Peer-reviewed scientific publications (priority)
   - Official environmental product declarations (EPDs)
   - Industry association reports with verified methodologies
   - Government and regulatory body publications
   - Standardization organizations (ISO, EN, ASTM)

2. Content Requirements:
   - LCA-specific metrics and methodologies
   - Clear system boundaries and functional units
   - Documented calculation methods
   - Uncertainty ranges when available
   - Regional and temporal context

3. Response Structure:
   - Prioritize quantitative data with proper context
   - Document all assumptions and limitations
   - Every statement containing data must be backed by a verifiable source
   - Provide complete source attribution with relative urls
   - Flag any methodological inconsistencies
   - Don't introduce, overexplain or repeat things, go straight to the point

4. Critical Evaluation:
   - Compare methodologies across sources
   - Highlight data gaps and uncertainties
   - Note regional variations if available

Always include:
- A reference section at the end which MUST CONTAIN relative urls of sources in extended format
- Publication dates and geographic scope
- Methodological framework used
- Data quality indicators
- Uncertainty ranges where available"""

        self.merger_prompt = """You are an environmental metrics expert tasked with creating a comprehensive comparison table from two sources:
1. The user's query (which may contain values to benchmark)
2. Web search results (containing broader context and recent information)

Your ONLY task is to create a clear, well-structured comparison table that:

1. Compares key metrics from all sources:
   - User's provided values (marked as [USER])
   - Environmental impact indicators
   - Carbon footprint values
   - Process specifications
   - System boundaries

2. Includes for each data point:
   - Value with unit
   - Response attribution:
     * [USER] for user-provided values
     * [WEB] for web search values
   - Active urls copied from responses, present them as clickable links with the text '[SOURCE]"
   - Year of data
   - Geographic scope
   - Methodology used

3. Handles data presentation:
   - Extract and include any numerical values or metrics from the user's query
   - Use "N/A" for missing values
   - Keep original precision of numbers
   - Include uncertainty ranges when provided
   - Flag any methodological differences
   - Note any significant discrepancies between sources

Format the table using markdown for clear presentation.

DO NOT:
- Generate any text before or after the table
- Include lengthy explanations or analysis
- Modify or calculate new values
- Make assumptions about missing data

Simply create a comprehensive, well-structured table that allows easy comparison of all available metrics from all sources, ensuring the user's values (if any) are included in the comparison."""

    def get_chunks(self, query: str, limit: int = 30) -> List[Dict[str, Any]]:
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

    async def process_with_llm(self, query: str, context: str, model: str, system_prompt: str, use_streaming: bool = True) -> AsyncGenerator[str, None]:
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
        
        # Add provider routing configuration only for meta model
        provider_config = {
            "order": ["Lepton", "Together", "Avian"],
            "allow_fallbacks": True
        } if model == "meta-llama/llama-3.3-70b-instruct" else None

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "stream": use_streaming
        }

        # Only add provider config if it exists
        if provider_config:
            payload["provider"] = provider_config

        async def stream_response():
            try:
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
            except Exception as e:
                # Log the error for debugging
                print(f"Streaming error: {str(e)}")
                # Fallback to non-streaming
                try:
                    response = requests.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json={**payload, "stream": False}
                    )
                    result = response.json()
                    yield result["choices"][0]["message"]["content"]
                except Exception as fallback_error:
                    print(f"Fallback error: {str(fallback_error)}")
                    raise

        if use_streaming:
            async for chunk in stream_response():
                yield chunk
        else:
            # Non-streaming mode
            try:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json={**payload, "stream": False}
                )
                result = response.json()
                yield result["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"Non-streaming error: {str(e)}")
                raise

    async def web_search(self, query: str) -> AsyncGenerator[str, None]:
        async for chunk in self.process_with_llm(
            query=query,
            context="Please search the web for relevant LCA and environmental metrics data.",
            model="perplexity/sonar",
            system_prompt=self.web_search_prompt,
            use_streaming=True
        ):
            yield chunk

    async def analyze(self, query: str, include_web_search: bool = False) -> AsyncGenerator[Dict[str, str], None]:
        try:
            chunks = self.get_chunks(query)
            context = "\n\n".join([chunk["text"] for chunk in chunks])
            
            if not include_web_search:
                db_stream = self.process_with_llm(
                    query=query,
                    context=context,
                    model="meta-llama/llama-3.3-70b-instruct",
                    system_prompt=self.retrieval_prompt,
                    use_streaming=True
                )
                async for chunk in db_stream:
                    yield {"section": "database", "content": chunk}
            else:
                # Create placeholders for accumulated results
                db_result = ""
                web_result = ""
                
                # Process database search
                db_stream = self.process_with_llm(
                    query=query,
                    context=context,
                    model="meta-llama/llama-3.3-70b-instruct",
                    system_prompt=self.retrieval_prompt,
                    use_streaming=True
                )
                async for chunk in db_stream:
                    db_result += chunk
                    yield {"section": "database", "content": chunk}

                # Process web search
                web_stream = self.web_search(query)
                async for chunk in web_stream:
                    web_result += chunk
                    yield {"section": "web", "content": chunk}
                
                # Generate comparison table only after web search is complete
                merged_context = f"""User Query (with values to benchmark):\n{query}\n\nWeb Search Results:\n{web_result}"""
                table_stream = self.process_with_llm(
                    query=query,
                    context=merged_context,
                    model="meta-llama/llama-3.3-70b-instruct",
                    system_prompt=self.merger_prompt,
                    use_streaming=True
                )
                async for chunk in table_stream:
                    yield {"section": "table", "content": chunk}
        except Exception as e:
            print(f"Analysis error: {str(e)}")
            raise

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
        
        async def process_stream():
            if include_web_search:
                progress_placeholder.text("Searching database and web, this might take a few minutes...")
                
                # Create placeholders for each section
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### Database Search Results")
                    db_placeholder = st.empty()
                with col2:
                    st.markdown("### Web Search Results")
                    web_placeholder = st.empty()
                st.markdown("### Comparison Table")
                table_placeholder = st.empty()
                
                # Initialize accumulated text for each section
                db_text = ""
                web_text = ""
                table_text = ""
                
                # Process streaming results
                async for chunk in analyzer.analyze(query, include_web_search=True):
                    if chunk["section"] == "database":
                        db_text += chunk["content"]
                        db_placeholder.markdown(f'<div class="database-container">{db_text}</div>', unsafe_allow_html=True)
                    elif chunk["section"] == "web":
                        web_text += chunk["content"]
                        web_placeholder.markdown(f'<div class="web-container">{web_text}</div>', unsafe_allow_html=True)
                    elif chunk["section"] == "table":
                        table_text += chunk["content"]
                        table_placeholder.markdown(table_text)
            else:
                st.markdown("### Analysis Results")
                content_placeholder = st.empty()
                accumulated_text = ""
                
                async for chunk in analyzer.analyze(query, include_web_search=False):
                    accumulated_text += chunk["content"]
                    content_placeholder.markdown(accumulated_text)
            
            # Clear progress placeholder when done
            progress_placeholder.empty()
        
        # Run the async function
        asyncio.run(process_stream())
            
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.info("Please check your API keys and try again.")
