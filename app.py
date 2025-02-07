import os
import json
import requests
import aiohttp
import streamlit as st
import nest_asyncio
from typing import List, Dict, Any, Union, AsyncGenerator
from r2r import R2RClient
import asyncio
import openai

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
        
        self.retrieval_prompt = """You are an environmental metrics expert focused on precise retrieval of LCA data. Your purpose is to:

1. DETERMINE IF BENCHMARKING IS NEEDED:
   - Only perform benchmarking if the user explicitly requests it by:
     * Using words like "benchmark", "compare", "how does it compare"
     * Providing specific values to compare against
     * Asking for performance relative to industry standards
   - Otherwise, focus solely on data retrieval and presentation

2. FOR DATA RETRIEVAL (Always):
   - Present ONLY the most relevant environmental metrics by:
     * Prioritizing exact matches for the queried item/process
     * For chemicals without exact matches, select proxies based on:
       1. Chemical similarity hierarchy:
          - Same chemical group (e.g., esters, amines)
          - Similar molecular structure (presence of benzene rings, double bonds)
          - Similar functional groups
          - Similar carbon chain length
       2. Production route similarity:
          - Similar stoichiometric reaction formulas
          - Comparable energy intensity in production
          - Similar feedstock materials
          - Similar processing steps
     * For non-chemical items, limit to maximum FIVE related items that:
       - Share similar production processes
       - Belong to the same product/material category
       - Have comparable functional properties
   - Exclude data points that are:
     * Only tangentially related
     * From fundamentally different product categories
     * Not sharing similar production methods or use cases

3. FOR BENCHMARKING (Only when explicitly requested):
   - Select comparisons based on relevance hierarchy:
     1. Primary relevance: Same product/material category
     2. Secondary relevance: Similar production process
     3. Tertiary relevance: Similar application/use case
   - Do not include comparisons beyond these relevance levels
   - Compare only across compatible environmental indicators

4. Structure your response with:
   Clear data presentation in markdown table format
   Transparent documentation of data gaps

When responding:
Present data with full context: name item, process ID (if available), unit, year (if available), country (if available)
Round decimal numerical values to 3 decimal places
Include environmental indicators found in retrieved chunks
Don't introduce, overexplain or repeat things, go straight to the point
Use appropriate headers to separate sections
Specify if variants exist for the requested item

Generate a structured markdown table with these EXACT columns in this order:

| Item/Process | Metrics Description | Value (Unit) | Reference | Year | Geography | Method | System Boundary | Uncertainty | Explanation | Match Rating |
|--------------|-------------------|--------------|-----------|------|------------|---------|----------------|-------------|-------------|--------------|

Follow these strict formatting rules:

1. Item/Process:
   - Clear, specific name of material/process
   - Clearly state in bold if it is a proxy 
   - Never combine multiple items in one cell

2. Metrics Description:
   - Specific environmental indicator being measured
   - One indicator per row
   - Example: "Global Warming Potential", "Primary Energy Demand"

3. Value (Unit):
   - Format as "X.XX (unit)"
   - Round to 2 decimal places
   - Include unit in parentheses
   - Example: "1.86 (kg CO2eq/kg)"

4. Reference formatting:
   - Use format: [SHORT_NAME](url) where SHORT_NAME is a brief identifier
   - For DOI numbers: Use [DOI_SHORT_NAME](https://doi.org/number)
   - Example: [ECO2023](https://example.com/data)

5. Explanation column MUST include for chemical proxies:
   - Chemical similarity aspects (functional groups, structure)
   - Production route comparison
   - Energy intensity comparison
   - Any significant differences that might affect the results
   For non-chemical proxies:
   - Process similarity justification
   - Material property comparison
   - Application relevance

6. Match Rating:
   - Use ONLY these values:
     * "Very good" - Exact match or nearly identical material/chemical/process
     * "Good" - Similar material/chemical/process structure/properties/production route with documented analogies
     * "Poor" - Different material/chemical/process group but estimated similar production intensity

Do not:
- Perform calculations or manipulate raw data, with the exception of rounding figures to 2 decimal places
- Provide random data that are not closely related to the user query
- Make assumptions without explicit documentation
- Mix incompatible methodologies without clear warnings"""

        self.web_search_prompt = """You are an environmental metrics expert focused on web-based retrieval of LCA data. Your purpose is to:

1. DETERMINE IF BENCHMARKING IS NEEDED:
   - Only perform benchmarking if the user explicitly requests it by:
     * Using words like "benchmark", "compare", "how does it compare"
     * Providing specific values to compare against
     * Asking for performance relative to industry standards
   - Otherwise, focus solely on data retrieval and presentation

2. FOR DATA RETRIEVAL (Always):
   Priority sources in order:
   - Peer-reviewed LCA studies and publications
   - Environmental product declarations (EPDs)
   - Industry association LCA reports
   - Government environmental assessments
   - Standardization bodies (ISO, EN, ASTM)

   Present ONLY the most relevant environmental metrics by:
   - For chemicals without exact matches, select proxies based on:
     1. Chemical similarity hierarchy:
        - Same chemical group (e.g., esters, amines)
        - Similar molecular structure (benzene rings, double bonds)
        - Similar functional groups
        - Similar carbon chain length
     2. Production route similarity:
        - Similar stoichiometric reaction formulas
        - Comparable energy intensity in production
        - Similar feedstock materials
        - Similar processing steps
   - For non-chemical items, limit to maximum FIVE related items that:
     - Share similar production processes
     - Belong to the same product/material category
     - Have comparable functional properties
   - Exclude data points that are:
     * Only tangentially related
     * From fundamentally different product categories
     * Not sharing similar production methods or use cases

3. FOR BENCHMARKING (Only when explicitly requested):
   - Select comparisons based on relevance hierarchy:
     1. Primary relevance: Same product/material category
     2. Secondary relevance: Similar production process
     3. Tertiary relevance: Similar application/use case
   - Do not include comparisons beyond these relevance levels
   - Compare only across compatible environmental indicators

4. DATA REQUIREMENTS:
   Search for:
   - Environmental impact metrics (CO2eq, energy use, etc.)
   - Clear system boundaries
   - Functional units
   - Calculation methodologies
   - Regional context
   - Temporal relevance
   - Uncertainty ranges

Generate a structured markdown table with these EXACT columns in this order:

| Item/Process | Metrics Description | Value (Unit) | Reference | Year | Geography | Method | System Boundary | Uncertainty | Explanation | Match Rating |
|--------------|-------------------|--------------|-----------|------|------------|---------|----------------|-------------|-------------|--------------|

Follow these strict formatting rules:

1. Item/Process:
   - Clear, specific name of material/process
   - Clearly state in bold if it is a proxy 
   - Never combine multiple items in one cell

2. Metrics Description:
   - Specific environmental indicator being measured
   - One indicator per row
   - Example: "Global Warming Potential", "Primary Energy Demand"

3. Value (Unit):
   - Format as "X.XX (unit)"
   - Round to 2 decimal places
   - Include unit in parentheses
   - Example: "1.86 (kg CO2eq/kg)"

4. Reference formatting:
   - Use format: [SHORT_NAME](url) where SHORT_NAME is a brief, meaningful identifier
   - For DOI numbers: Use [DOI_SHORT_NAME](https://doi.org/number)
   - Example: [ECO2023](https://example.com/data)

5. Explanation column MUST include for chemical proxies:
   - Chemical similarity aspects (functional groups, structure)
   - Production route comparison
   - Energy intensity comparison
   - Any significant differences that might affect the results
   For non-chemical proxies:
   - Process similarity justification
   - Material property comparison
   - Application relevance

6. Match Rating:
   - Use ONLY these values:
     * "Very good" - Exact match or nearly identical material/chemical/process
     * "Good" - Similar material/chemical/process structure/properties/production route with documented analogies
     * "Poor" - Different material/chemical/process group but estimated similar production intensity

Do not:
- Perform calculations or manipulate raw data, with the exception of rounding figures to 2 decimal places
- Provide random data that are not closely related to the user query
- Make assumptions without explicit documentation
- Mix incompatible methodologies without clear warnings
- Introduce, overexplain or repeat things
- Include data without verifiable sources"""

        self.merger_prompt = """You are an environmental metrics expert tasked with providing a synthesis and creating a strictly formatted comparison table. Your sources are:
1. Database results (containing structured LCA metrics)
2. Web search results (containing broader context and recent information)
3. User's query (ONLY include if it contains specific values to benchmark)

Your tasks in EXACT order:

1. SYNTHESIS (Required):
   - Provide a clear, concise, data-rich (2-3 sentences max) answer to the user's query
   - Include only the most relevant findings from both database and web sources
   - It should serve as a TL;DR for the user
   - End with a line break before the table

2. COMPARISON TABLE (Required):
   Create a table with these MANDATORY columns in this exact order:

| Item/Process | Metrics Description | Value (Unit) | Source | Reference | Year | Geography | Method | System Boundary | Uncertainty | Explanation | Match Rating |
|-------------|-------------------|--------------|---------|-----------|------|-----------|---------|----------------|-------------|-------------|--------------|

Follow these strict formatting rules for each column:

1. Item/Process:
   - Clear, specific name of process or material
   - Include variant type if applicable (e.g., "Bio-based", "Petroleum-based")
   - Never combine multiple items in one cell

2. Metrics Description:
   - Specific environmental indicator being measured
   - One indicator per row
   - Example: "Global Warming Potential", "Primary Energy Demand"

3. Value (Unit):
   - Format: "X.XX (unit)"
   - Round to 2 decimal places
   - Include unit in parentheses
   - Example: "1.86 (kg CO2eq/kg)"

4. Source:
   - Use ONLY: [USER], [DB], or [WEB]
   - No other variations allowed
   - Only include [USER] if query contains specific values to benchmark

5. Reference:
   - Format: [SHORT_NAME](url)
   - For DOI: [DOI_SHORT_NAME](https://doi.org/number)
   - User entries: "N/A"

6. Year:
   - Format: YYYY
   - Use "N/A" if unknown

7. Geography:
   - Use ISO country codes when available (e.g., "US", "EU")
   - Use "GLO" for global
   - Use "N/A" if unknown

8. Method:
   - Specify LCA methodology/standard used
   - Examples: "ISO 14044", "PEF", "EPD"
   - Use "N/A" if unknown

9. System Boundary:
   - Use ONLY these terms:
     * cradle-to-gate
     * gate-to-gate
     * cradle-to-grave
     * cradle-to-cradle
   - Use "N/A" if unknown

10. Uncertainty:
    - Format: "±XX%" or "XX-YY (unit)"
    - Use "N/A" if not provided

11. Explanation:
    For chemical proxies MUST include:
    - Chemical similarity aspects (functional groups, structure)
    - Production route comparison
    - Energy intensity comparison
    - Any significant differences affecting results
    
    For non-chemical proxies MUST include:
    - Process similarity justification
    - Material property comparison
    - Application relevance

12. Match Rating:
    - Use ONLY these values:
      * "Very good" - Exact match or nearly identical material/chemical/process
      * "Good" - Similar material/chemical/process structure/properties/production route with documented analogies
      * "Poor" - Different material/chemical/process group but estimated similar production intensity

Additional Rules:
1. Create separate rows for:
   - Different environmental indicators
   - Process variants
   - Different sources of same data
2. Sort rows by:
   - Match rating
   - Source type (USER > DB > WEB)
3. Use "N/A" for any missing data, never leave cells empty
4. No text before or after the synthesis and table
5. No data manipulation except rounding to 2 decimals
6. No combining multiple values in single cells"""

    def get_chunks(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
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
        client = openai.OpenAI(
            base_url="https://router.requesty.ai/v1",
            api_key=self.requesty_api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/yourusername/yourrepo",
                "X-Title": "LCA Analysis Tool"
            }
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Query: {query}\n\nContext: {context}"}
        ]

        try:
            if use_streaming:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0,
                    top_p=0,
                    stream=True
                )
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            else:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0,
                    top_p=0,
                    stream=False
                )
                yield response.choices[0].message.content
        except Exception as e:
            print(f"LLM error: {str(e)}")
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
            "model": "perplexity/sonar-reasoning",
            "messages": messages,
            "temperature": 0,
            "top_p": 0,
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
                    model="cline/o3-mini",
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
                    model="cline/o3-mini",
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
                merged_context = f"""User Query:\n{query}\n\nDatabase Results:\n{db_result}\n\nWeb Search Results:\n{web_result}"""
                table_stream = self.process_with_llm(
                    query=query,
                    context=merged_context,
                    model="google/gemini-2.0-flash-001",
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
st.title("LCA Benchmarking and Retrieval")

# Add logout button to sidebar
with st.sidebar:
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()

    st.header("About")
    st.markdown("""
    This tool helps retrieve and benchmark environmental metrics using AI connected to a life-cycle assessment (LCA) database (currently only Idemat) and the web.

    I'm working on expanding the database to include as many LCA data as possible from published studies. 
                
    My mission: mitigating uncertainty and filling data gaps in LCA.
    
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
                            display: block;
                            max-width: 1200px;
                            margin: 0 auto;
                            overflow-x: auto;
                        }
                        td {
                            max-width: 200px;
                            white-space: normal;
                            word-wrap: break-word;
                            padding: 8px;
                        }
                        th {
                            white-space: normal;
                            word-wrap: break-word;
                            max-width: 200px;
                            padding: 8px;
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
                            max-width: 1200px;
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
