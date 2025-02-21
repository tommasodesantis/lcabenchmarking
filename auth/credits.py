import os
import streamlit as st
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv

class OrganizationManager:
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
        # Verify table exists
        try:
            self.supabase.table('organization_info').select('*').limit(1).execute()
        except Exception as e:
            raise ValueError("organization_info table not found in Supabase. Please ensure the table is created.") from e
    
    def has_org_info(self, email: str) -> bool:
        try:
            result = self.supabase.table('organization_info').select('*').eq('email', email).execute()
            return len(result.data) > 0
        except Exception as e:
            raise

    def get_org_info(self, email: str) -> dict:
        try:
            result = self.supabase.table('organization_info').select('*').eq('email', email).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            raise

    def save_org_info(self, email: str, org_name: str, role: str, lca_needs: str, first_name: str = None, last_name: str = None):
        try:
            self.supabase.table('organization_info').upsert({
                'email': email,
                'org_name': org_name,
                'role': role,
                'lca_needs': lca_needs,
                'first_name': first_name,
                'last_name': last_name
            }).execute()
        except Exception as e:
            raise

class CreditsManager:
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
        # Verify table exists
        try:
            self.supabase.table('user_credits').select('*').limit(1).execute()
        except Exception as e:
            raise ValueError("user_credits table not found in Supabase. Please ensure the table is created.") from e
    
    def get_credits(self, email: str) -> int:
        try:
            result = self.supabase.table('user_credits').select('credits').eq('email', email).execute()
            
            if not result.data:
                # Initialize new user with 5 credits
                self.supabase.table('user_credits').insert({
                    'email': email,
                    'credits': 5
                }).execute()
                return 5
            
            return result.data[0]['credits']
        except Exception as e:
            raise
    
    def use_credit(self, email: str) -> bool:
        try:
            # Get current credits
            result = self.supabase.table('user_credits').select('credits').eq('email', email).execute()
            
            if not result.data:
                # Initialize new user with 5 credits
                self.supabase.table('user_credits').insert({
                    'email': email,
                    'credits': 5
                }).execute()
                current_credits = 5
            else:
                current_credits = result.data[0]['credits']
            
            if current_credits <= 0:
                return False
            
            # Deduct one credit
            self.supabase.table('user_credits').update({
                'credits': current_credits - 1
            }).eq('email', email).execute()
            
            return True
        except Exception as e:
            raise
    
    def add_credits(self, email: str, amount: int):
        if amount <= 0:
            raise ValueError("Credit amount must be positive")
            
        try:
            result = self.supabase.table('user_credits').select('credits').eq('email', email).execute()
            
            if not result.data:
                # Initialize new user with 5 + amount credits
                self.supabase.table('user_credits').insert({
                    'email': email,
                    'credits': 5 + amount
                }).execute()
            else:
                current_credits = result.data[0]['credits']
                self.supabase.table('user_credits').update({
                    'credits': current_credits + amount
                }).eq('email', email).execute()
        except Exception as e:
            raise
    
    def set_credits(self, email: str, amount: int):
        if amount < 0:
            raise ValueError("Credit amount must be non-negative")
            
        try:
            self.supabase.table('user_credits').upsert({
                'email': email,
                'credits': amount
            }).execute()
        except Exception as e:
            raise
