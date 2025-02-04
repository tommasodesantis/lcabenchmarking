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
.css-1jc7ptx, .e1ewe7hr3, .viewerBadge_container__1QSob,
.styles_viewerBadge__1yB5_, .viewerBadge_link__1S137,
.viewerBadge_text__1JaDK {
    display: none;
}
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
    def __init__(self, r2r_api_key: str, requesty_api_key: str, openrouter_api_key: str):
        self.r2r_api_key = r2r_api_key
        self.requesty_api_key = requesty_api_key
        self.openrouter_api_key = openrouter_api_key
        self.client = R2RClient("https://api.cloud.sciphi.ai")
        
        self.retrieval_prompt = """You are an environmental metrics expert focused on precise retrieval and benchmarking of LCA data. Your purpose is to:

Retrieve and present environmental metrics from the knowledge base with attention to:

Available environmental impact indicators (eco-costs, ReCiPe, EF 3.1)
Process variants and specifications
System boundaries as defined in the database

Benchmark user data against reference values by:

Selecting ONLY THE MOST RELEVANT comparisons based on product category and specifications
Focus in particular on different product variants (e.g., packaging types)
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
- IMPORTANT: a reference section at the end which MUST CONTAIN relative urls of sources in extended format
- Publication dates and geographic scope
- Methodological framework used
- Data quality indicators
- Uncertainty ranges where available"""

        self.merger_prompt = """You are an environmental metrics expert tasked with creating a strictly formatted comparison table from three sources:
1. The user's query (which may contain values to benchmark)
2. Database results (containing structured LCA metrics)
3. Web search results (containing broader context and recent information)

Your ONLY task is to create a comparison table with the following MANDATORY columns in this exact order:

| Item/Process | Value (Unit) | Source | Reference | Year | Geography | Method | System Boundary | Uncertainty |
|-------------|--------------|---------|-----------|------|-----------|---------|----------------|-------------|

Follow these strict formatting rules for each column:

1. Item/Process:
   - Clear, specific name of the process or material
   - Include variant type if applicable (e.g., "Glass Bottle - Recycled")
   - One item per row, no combining multiple items

2. Value (Unit):
   - Format: "X.XX (unit)" (e.g., "1.23 (kg CO2eq/kg)")
   - Always round to 2 decimal places
   - Include unit in parentheses
   - For multiple indicators, use separate rows

3. Source:
   - Use ONLY: [USER], [DB], or [WEB]
   - No other variations allowed

4. Reference:
   - Format: "[SOURCE](url)"
   - For DB entries: "[IDEMAT 2025](https://www.ecocostsvalue.com/data-tools-books/)"
   - For web entries: "[SOURCE](actual_url)"
   - User entries: "N/A"

5. Year:
   - Format: YYYY
   - Use "N/A" if unknown

6. Geography:
   - Use ISO country codes when available (e.g., "US", "EU")
   - Use "GLO" for global
   - Use "N/A" if unknown

7. Method:
   - Specify LCA methodology/standard used
   - Examples: "ISO 14044", "PEF", "EPD"
   - Use "N/A" if unknown

8. System Boundary:
   - Use ONLY these terms:
     * cradle-to-gate
     * gate-to-gate
     * cradle-to-grave
     * cradle-to-cradle
   - Use "N/A" if unknown

9. Uncertainty:
   - Format: "±XX%" or "XX-YY (unit)"
   - Use "N/A" if not provided

Additional Rules:
1. Create separate rows for:
   - Different environmental indicators
   - Process variants
   - Different sources of same data
2. Sort rows by:
   - Item/Process name
   - Source type (USER > DB > WEB)
3. Use "N/A" for any missing data, never leave cells empty
4. No text before or after the table
5. No explanations or analysis
6. No data manipulation except rounding to 2 decimals
7. No combining multiple values in single cells

Example row format:
| Glass Bottle - Recycled | 1.23 (kg CO2eq/kg) | [DB] | [IDEMAT 2025](https://www.ecocostsvalue.com/data-tools-books/) | 2025 | EU | PEF | cradle-to-gate | ±15% |"""

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
            "Authorization": f"Bearer {self.requesty_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/yourusername/yourrepo",
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

        async def stream_response():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://router.requesty.ai/v1/chat/completions",
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
                response = requests.post(
                    "https://router.requesty.ai/v1/chat/completions",
                    headers=headers,
                    json={**payload, "stream": False}
                )
                result = response.json()
                yield result["choices"][0]["message"]["content"]

        if use_streaming:
            async for chunk in stream_response():
                yield chunk
        else:
            # Non-streaming mode
            try:
                response = requests.post(
                    "https://router.requesty.ai/v1/chat/completions",
                    headers=headers,
                    json={**payload, "stream": False}
                )
                result = response.json()
                yield result["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"Non-streaming error: {str(e)}")
                raise

    async def web_search(self, query: str) -> AsyncGenerator[str, None]:
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8888",
            "X-Title": "LCA Analysis Tool"
        }
        
        messages = [
            {"role": "system", "content": self.web_search_prompt},
            {"role": "user", "content": f"Query: {query}\n\nContext: Please search the web for relevant LCA and environmental metrics data."}
        ]
        
        payload = {
            "model": "perplexity/sonar",
            "messages": messages,
            "temperature": 0.7,
            "stream": True
        }

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
                print(f"Web search streaming error: {str(e)}")
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json={**payload, "stream": False}
                )
                result = response.json()
                yield result["choices"][0]["message"]["content"]

        async for chunk in stream_response():
            yield chunk

    async def analyze(self, query: str, include_web_search: bool = False) -> AsyncGenerator[Dict[str, str], None]:
        try:
            chunks = self.get_chunks(query)
            context = "\n\n".join([chunk["text"] for chunk in chunks])
            
            if not include_web_search:
                db_stream = self.process_with_llm(
                    query=query,
                    context=context,
                    model="deepinfra/meta-llama/Llama-3.3-70B-Instruct-Turbo",
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
                    model="deepinfra/meta-llama/Llama-3.3-70B-Instruct-Turbo",
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
                merged_context = f"""User Query (with values to benchmark):\n{query}\n\nDatabase Results:\n{db_result}\n\nWeb Search Results:\n{web_result}"""
                table_stream = self.process_with_llm(
                    query=query,
                    context=merged_context,
                    model="deepinfra/meta-llama/Llama-3.3-70B-Instruct-Turbo",
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
        requesty_api_key=st.secrets["REQUESTY_API_KEY"],
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
        progress_placeholder = st.empty()
        
        async def process_stream():
            if include_web_search:
                progress_placeholder.text("Searching database and web, this might take a few minutes...")
                
                # Create tabs instead of columns for better space management
                tabs = st.tabs(["Database Results", "Web Results", "Results overview"])
                
                with tabs[0]:
                    db_placeholder = st.empty()
                with tabs[1]:
                    web_placeholder = st.empty()
                with tabs[2]:
                    table_placeholder = st.empty()
                
                # Initialize accumulated text for each section
                db_text = ""
                web_text = ""
                table_text = ""
                
                # Add custom CSS for table overflow
                st.markdown("""
                    <style>
                        .stMarkdown {
                            overflow-x: auto;
                            max-width: 100%;
                        }
                        table {
                            white-space: nowrap;
                            display: block;
                            max-width: -moz-fit-content;
                            max-width: fit-content;
                            margin: 0 auto;
                            overflow-x: auto;
                        }
                    </style>
                """, unsafe_allow_html=True)
                
                # Process streaming results
                async for chunk in analyzer.analyze(query, include_web_search=True):
                    if chunk["section"] == "database":
                        db_text += chunk["content"]
                        db_placeholder.markdown(f'<div class="database-container">\n\n{db_text}</div>', unsafe_allow_html=True)
                    elif chunk["section"] == "web":
                        web_text += chunk["content"]
                        web_placeholder.markdown(f'<div class="web-container">\n\n{web_text}</div>', unsafe_allow_html=True)
                    elif chunk["section"] == "table":
                        table_text += chunk["content"]
                        table_placeholder.markdown(table_text)
            else:
                st.markdown("### Analysis Results")
                content_placeholder = st.empty()
                accumulated_text = ""
                
                # Add custom CSS for table overflow in single-view mode
                st.markdown("""
                    <style>
                        .stMarkdown {
                            overflow-x: auto;
                            max-width: 100%;
                        }
                        table {
                            white-space: nowrap;
                            display: block;
                            max-width: -moz-fit-content;
                            max-width: fit-content;
                            margin: 0 auto;
                            overflow-x: auto;
                        }
                    </style>
                """, unsafe_allow_html=True)
                
                async for chunk in analyzer.analyze(query, include_web_search=False):
                    accumulated_text += chunk["content"]
                    content_placeholder.markdown(accumulated_text)
            
            progress_placeholder.empty()
        
        asyncio.run(process_stream())
            
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.info("Please check your API keys and try again.")
