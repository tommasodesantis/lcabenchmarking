import os
import streamlit as st
import nest_asyncio
import asyncio
from analyzer import LCAAnalyzer
from dotenv import load_dotenv
from auth import Authenticator
from auth.credits import CreditsManager

# Load environment variables
load_dotenv()

# Enable nested asyncio
nest_asyncio.apply()

# Set page config
st.set_page_config(
    page_title="LCA Benchmarking Tool",
    page_icon="🌍",
    layout="wide"
)

# Initialize authenticator and credits manager
allowed_users = st.secrets.ALLOWED_USERS
authenticator = Authenticator(
    allowed_users=allowed_users,
    token_key=st.secrets.TOKEN_KEY,
    secret_path="client_secret_879574062090-6k6vhd2s5qj1gc71mgqdhi2hc0rgjnkq.apps.googleusercontent.com.json",
    redirect_uri="http://localhost:8501/",
)

# Initialize credits manager (now using Supabase)
credits_manager = CreditsManager()

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

# Initialize the analyzer
@st.cache_resource
def get_analyzer():
    return LCAAnalyzer(
        r2r_api_key=st.secrets["R2R_API_KEY"],
        requesty_api_key=st.secrets["REQUESTY_API_KEY"],
        openrouter_api_key=st.secrets["OPENROUTER_API_KEY"]
    )

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

    # Main app content (only shown when authenticated)
    st.title("LCA Benchmarking and Retrieval")

    # Add logout button and credits display to sidebar
    with st.sidebar:
        if st.button("Logout"):
            authenticator.logout()
            st.stop()  # Stop execution immediately to show login screen

        # Display remaining credits
        remaining_credits = credits_manager.get_credits(st.session_state.user_info["email"])
        st.metric("Remaining free credits:", remaining_credits)

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

    st.info("💡 Tip: For better results, avoid using abbreviations. For example, use 'sodium chloride' instead of 'NaCl', and 'polyethylene terephthalate' instead of 'PET'.")
    
    query = st.text_area(
        "Enter your environmental metrics query:", 
        "My honey in a glass has a carbon footprint of 1 kg CO2eq/kg, how does it benchmark?", 
        height=100
    )

    if st.button("Analyze"):
        # Check if user has credits available
        user_email = st.session_state.user_info["email"]
        if not credits_manager.use_credit(user_email):
            st.error("You have used all your free credits. Please contact the administrator for more credits.")
            st.stop()

        analyzer = get_analyzer()
        
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
        
        try:
            asyncio.run(process_stream())
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.info("Please check your API keys and try again.")

if __name__ == "__main__":
    main()
