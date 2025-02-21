import os
import streamlit as st
from supabase import create_client
from dotenv import load_dotenv

class FeedbackManager:
    def __init__(self):
        load_dotenv()
        
        # Try getting from streamlit secrets first
        supabase_url = st.secrets.get("SUPABASE_URL")
        supabase_key = st.secrets.get("SUPABASE_KEY")
        
        # If not in streamlit secrets, try environment variables
        if not supabase_url:
            supabase_url = os.getenv("SUPABASE_URL")
        if not supabase_key:
            supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError("Supabase credentials not found in environment variables")
        
        self.supabase = create_client(supabase_url, supabase_key)
        self._init_db()
    
    def _init_db(self):
        try:
            self.supabase.table('analysis_feedback').select('*').limit(1).execute()
        except Exception as e:
            raise ValueError("analysis_feedback table not found in Supabase") from e
    
    def save_feedback(self, email: str, query: str, answer: str, rating: int, feedback_message: str):
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")
            
        try:
            self.supabase.table('analysis_feedback').insert({
                'email': email,
                'query': query,
                'answer': answer,
                'rating': rating,
                'feedback_message': feedback_message
            }).execute()
        except Exception as e:
            raise
