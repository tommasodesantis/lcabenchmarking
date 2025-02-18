import os
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv

class CreditsManager:
    def __init__(self):
        load_dotenv()
        
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        if not supabase_url or not supabase_key:
            raise ValueError("Supabase credentials not found in environment variables")
        
        self.supabase = create_client(supabase_url, supabase_key)
        self._init_db()
    
    def _init_db(self):
        try:
            # Check if table exists by attempting to select from it
            self.supabase.table('user_credits').select('*').limit(1).execute()
        except Exception:
            # Create table if it doesn't exist
            self.supabase.table('user_credits').create({
                'email': 'text primary key',
                'credits': 'integer default 5',
                'created_at': 'timestamp with time zone default timezone(\'utc\'::text, now())'
            })
    
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
