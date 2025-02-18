import os
import logging
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv

logger = logging.getLogger('auth.credits')

class CreditsManager:
    def __init__(self):
        """Initialize the CreditsManager with Supabase client."""
        load_dotenv()
        
        # Initialize Supabase client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        if not supabase_url or not supabase_key:
            raise ValueError("Supabase credentials not found in environment variables")
        
        self.supabase = create_client(supabase_url, supabase_key)
        self._init_db()
    
    def _init_db(self):
        """Initialize the Supabase table if it doesn't exist."""
        try:
            # Check if table exists by attempting to select from it
            self.supabase.table('user_credits').select('*').limit(1).execute()
            logger.info("Credits table exists in Supabase")
        except Exception as e:
            logger.info("Creating user_credits table in Supabase")
            try:
                # Create table if it doesn't exist
                self.supabase.table('user_credits').create({
                    'email': 'text primary key',
                    'credits': 'integer default 5',
                    'created_at': 'timestamp with time zone default timezone(\'utc\'::text, now())'
                })
                logger.info("Credits table created successfully in Supabase")
            except Exception as e:
                logger.error(f"Failed to initialize database: {str(e)}")
                raise
    
    def get_credits(self, email: str) -> int:
        """Get the number of remaining credits for a user.
        
        Args:
            email: The user's email address.
            
        Returns:
            int: Number of remaining credits. Returns 5 for new users.
        """
        logger.debug(f"Getting credits for user: {email}")
        try:
            result = self.supabase.table('user_credits').select('credits').eq('email', email).execute()
            
            if not result.data:
                # Initialize new user with 5 credits
                logger.info(f"Initializing credits for new user: {email}")
                self.supabase.table('user_credits').insert({
                    'email': email,
                    'credits': 5
                }).execute()
                return 5
            
            return result.data[0]['credits']
        except Exception as e:
            logger.error(f"Failed to get credits: {str(e)}")
            raise
    
    def use_credit(self, email: str) -> bool:
        """Use one credit for the specified user.
        
        Args:
            email: The user's email address.
            
        Returns:
            bool: True if credit was successfully used, False if no credits remaining.
        """
        logger.debug(f"Attempting to use credit for user: {email}")
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
                logger.warning(f"No credits remaining for user: {email}")
                return False
            
            # Deduct one credit
            self.supabase.table('user_credits').update({
                'credits': current_credits - 1
            }).eq('email', email).execute()
            
            logger.info(f"Successfully used credit for {email}. {current_credits - 1} remaining")
            return True
        except Exception as e:
            logger.error(f"Failed to use credit: {str(e)}")
            raise
    
    def add_credits(self, email: str, amount: int):
        """Add credits to a user's account.
        
        Args:
            email: The user's email address.
            amount: Number of credits to add (must be positive).
        """
        if amount <= 0:
            raise ValueError("Credit amount must be positive")
            
        logger.debug(f"Adding {amount} credits for user: {email}")
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
            
            logger.info(f"Successfully added {amount} credits for {email}")
        except Exception as e:
            logger.error(f"Failed to add credits: {str(e)}")
            raise
    
    def set_credits(self, email: str, amount: int):
        """Set a user's credits to a specific amount.
        
        Args:
            email: The user's email address.
            amount: Number of credits to set (must be non-negative).
        """
        if amount < 0:
            raise ValueError("Credit amount must be non-negative")
            
        logger.debug(f"Setting credits to {amount} for user: {email}")
        try:
            self.supabase.table('user_credits').upsert({
                'email': email,
                'credits': amount
            }).execute()
            logger.info(f"Successfully set credits to {amount} for {email}")
        except Exception as e:
            logger.error(f"Failed to set credits: {str(e)}")
            raise
