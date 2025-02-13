import os
import streamlit as st
import nest_asyncio
import asyncio
from analyzer import LCAAnalyzer

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

# Initialize the analyzer
@st.cache_resource
def get_analyzer():
    return LCAAnalyzer(
        r2r_api_key=st.secrets["R2R_API_KEY"],
        requesty_api_key=st.secrets["REQUESTY_API_KEY"],
        openrouter_api_key=st.secrets["OPENROUTER_API_KEY"]
    )

def main():
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
        This tool helps retrieve and benchmark environmental metrics using AI connected to a life-cycle assessment (LCA) database (e.g. Idemat, Agribalyse, etc) and the web.

        I'm working on expanding the database to include as many LCA data as possible from published studies. 
                    
        My mission: mitigating uncertainty and filling data gaps in LCA.
        
        ---
        Developed by [Tommaso De Santis](https://www.linkedin.com/in/tommaso-de-santis/)
        """)

    # Create the Streamlit interface
    include_web_search = st.toggle('Include web search', value=False, 
        help='Enable to search both database and web sources. The analysis might take up to a few minutes.')

    st.info("💡 Tip: For better results, avoid using abbreviations for chemical compounds and item names. For example, use 'sodium chloride' instead of 'NaCl', and 'polyethylene terephthalate' instead of 'PET'.")
    
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
                    st.markdown("### Results from database")
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

if __name__ == "__main__":
    main()
