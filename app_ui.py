import os
import time
import streamlit as st
import nest_asyncio
import asyncio
from analyzer import LCAAnalyzer
from dotenv import load_dotenv
from auth import Authenticator
from auth.credits import CreditsManager, OrganizationManager

# Load environment variables
load_dotenv()

# Enable nested asyncio
nest_asyncio.apply()

# Initialize session state variables
if 'org_form_submitted' not in st.session_state:
    st.session_state.org_form_submitted = False
if 'analysis_running' not in st.session_state:
    st.session_state.analysis_running = False
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = {
        'database': '',
        'web': '',
        'table': ''
    }
if 'query' not in st.session_state:
    st.session_state.query = ''

# Set page config
st.set_page_config(
    page_title="LCA Benchmarking Tool",
    page_icon="🌍",
    layout="wide"
)

# Function to determine redirect URI based on environment
def get_redirect_uri():
    # Check environment from secrets
    env = st.secrets.get("ENVIRONMENT", "production")
    
    if env == "development":
        return "http://localhost:8501/"
    
    # Fallback to production URL
    return "https://lcabenchmarking-ykp3ctmxmfh5ctrpsxz8fh.streamlit.app/"

# Initialize authenticator and credits manager
authenticator = Authenticator(
    token_key=st.secrets.TOKEN_KEY,
    redirect_uri=get_redirect_uri(),
)

# Initialize managers
credits_manager = CreditsManager()
org_manager = OrganizationManager()

# Add custom CSS
st.markdown("""
<style>
.css-1jc7ptx, .e1ewe7hr3, .viewerBadge_container__1QSob,
.styles_viewerBadge__1yB5_, .viewerBadge_link__1S137,
.viewerBadge_text__1JaDK {
    display: none;
}
.stInfo {
    font-size: 0.85rem !important;
    padding: 0.5rem 0.8rem !important;
}
.credits-container {
    background-color: #f8f9fa;
    border-left: 3px solid #6c757d;
    padding: 8px 12px;
    margin: 10px 0;
    border-radius: 4px;
    font-size: 1.1rem;
    font-weight: bold;
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

# Initialize the analyzer
@st.cache_resource
def get_analyzer():
    return LCAAnalyzer(
        r2r_api_key=st.secrets["R2R_API_KEY"],
        requesty_api_key=st.secrets["REQUESTY_API_KEY"],
        openrouter_api_key=st.secrets["OPENROUTER_API_KEY"]
    )

def show_org_info_form():
    st.title("🏢 Organization Information")
    st.info("To access the LCA Benchmarking Tool, please provide information about your organization.")
    
    with st.form("org_info_form"):
        first_name = st.text_input("First Name (optional)")
        last_name = st.text_input("Last Name (optional)")
        org_name = st.text_input("Organization name*")
        role = st.text_input("Your role in the organization*")
        lca_needs = st.text_area(
            "Do you experience the problem of data gaps when working with LCA? If yes for what kind of LCA data specifically?*",
            help="Specify material/process categories that are most relevant for your work"
        )
        
        st.markdown("*Required fields")
        submit_button = st.form_submit_button("Submit")
        
        if submit_button:
            if not org_name or not role or not lca_needs:
                st.error("Please fill in all required fields")
                return False
            
            try:
                org_manager.save_org_info(
                    st.session_state.user_info["email"],
                    org_name,
                    role,
                    lca_needs,
                    first_name if first_name else None,
                    last_name if last_name else None
                )
                st.session_state.org_form_submitted = True
                st.success("Thank you! These information will be very useful to improve this product.")
                time.sleep(1)  # Give user time to see the success message
                st.rerun()
                return True
            except Exception as e:
                st.error(f"Error saving organization information: {str(e)}")
                return False
    
    return False

def main():
    # Check authentication and handle OAuth flow
    authenticator.check_auth()

    # Login form if not authenticated
    if not st.session_state.connected:
        left_col, center_col, right_col = st.columns([1,2,1])
        with center_col:
            st.title("🌱 Welcome to LCA Benchmarker")
            authenticator.login()
        st.stop()

    # Check if organization info is needed for Google OAuth users
    if (st.session_state.user_info.get("oauth_id") and 
        not org_manager.has_org_info(st.session_state.user_info["email"]) and 
        not st.session_state.org_form_submitted):
        if not show_org_info_form():
            st.stop()

    # Main app content (only shown when authenticated and org info provided if needed)
    st.title("LCA Benchmarking and Retrieval")

    # Add logout button and credits display to sidebar
    with st.sidebar:
        if st.button("Logout"):
            authenticator.logout()
            st.stop()  # Stop execution immediately to show login screen

        # Display remaining credits
        remaining_credits = credits_manager.get_credits(st.session_state.user_info["email"])
        st.markdown(f'<div class="credits-container">Remaining free credits: {remaining_credits}</div>', unsafe_allow_html=True)

        st.header("About")
        st.markdown("""
        This tool helps retrieve and benchmark environmental metrics using AI connected to a life-cycle assessment (LCA) database and the web.

        I'm working on expanding the database to include as many LCA data as possible from published studies. 
                    
        My mission: mitigating uncertainty and filling data gaps in LCA.
        
        ---
        Developed by [Tommaso De Santis](https://www.linkedin.com/in/tommaso-de-santis/). Happy to
        [schedule a call](https://cal.com/tommaso-de-santis/lcabench-intro-call) to discuss your use cases.

        ---
        """)
        
        # Add credits text and buttons
        st.markdown("Out of free credits? Get 5 more by: ")
        st.link_button("📝 Requesting a new feature", "https://tally.so/r/n0DDd6", type="secondary")
        st.link_button("💭 Giving me a feedback", "https://tally.so/r/3xllXo", type="secondary")

    # Create the Streamlit interface
    include_web_search = st.toggle('Include web search', value=True, 
        help='Enable to search both database and web sources. The analysis might take up to a few minutes.')

    st.info("""💡 For better results, avoid using abbreviations. For example, use 'sodium chloride' instead of 'NaCl'

💡 Use dots (.) instead of commas (,) for decimal values. For example: '1.5' instead of '1,5'""")
    
    query = st.text_area(
        "Enter your environmental metrics query:", 
        "My honey in a glass has a carbon footprint of 1 kg CO2eq/kg, how does it benchmark?", 
        height=100
    )

    # Store query in session state to persist across reruns
    if query != st.session_state.query:
        st.session_state.query = query
        # Reset results when query changes
        st.session_state.analysis_results = {
            'database': '',
            'web': '',
            'table': ''
        }

    analyze_button = st.button("Analyze", disabled=st.session_state.analysis_running)

    if analyze_button:
        # Check if user has credits available
        user_email = st.session_state.user_info["email"]
        if not credits_manager.use_credit(user_email):
            st.error("You have used all your free credits. Interested in using LCAbench in your organization? Schedule a call to discuss option: [book a slot](https://cal.com/tommaso-de-santis/lcabench-intro-call)")
            st.stop()

        st.session_state.analysis_running = True
        analyzer = get_analyzer()
        
        progress_placeholder = st.empty()
        
        async def process_stream():
            try:
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
                    async for chunk in analyzer.analyze(st.session_state.query, include_web_search=True):
                        if chunk["section"] == "database":
                            st.session_state.analysis_results['database'] += chunk["content"]
                            db_placeholder.markdown(
                                f'<div class="database-container">\n\n{st.session_state.analysis_results["database"]}</div>', 
                                unsafe_allow_html=True
                            )
                        elif chunk["section"] == "web":
                            st.session_state.analysis_results['web'] += chunk["content"]
                            web_placeholder.markdown(
                                f'<div class="web-container">\n\n{st.session_state.analysis_results["web"]}</div>', 
                                unsafe_allow_html=True
                            )
                        elif chunk["section"] == "table":
                            st.session_state.analysis_results['table'] += chunk["content"]
                            table_placeholder.markdown(st.session_state.analysis_results['table'])
                else:
                    content_placeholder = st.empty()
                    progress_placeholder.text("Searching database, this might take a few seconds...")
                    
                    async for chunk in analyzer.analyze(st.session_state.query, include_web_search=False):
                        st.session_state.analysis_results['database'] += chunk["content"]
                        content_placeholder.markdown(
                            f'<div class="database-container">\n\n{st.session_state.analysis_results["database"]}</div>', 
                            unsafe_allow_html=True
                        )
            
                progress_placeholder.empty()
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.info("Please check your API keys and try again.")
            finally:
                st.session_state.analysis_running = False
        
        try:
            asyncio.run(process_stream())
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.info("Please check your API keys and try again.")
            st.session_state.analysis_running = False

if __name__ == "__main__":
    main()
