import sqlite3
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger('auth.credits')

class CreditsManager:
    def __init__(self, db_path: str = "auth/credits.db"):
        """Initialize the CreditsManager with SQLite database.
        
        Args:
            db_path: Path to the SQLite database file. Defaults to "auth/credits.db".
        """
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize the SQLite database and create the user_credits table if it doesn't exist."""
        db_dir = Path(self.db_path).parent
        if not db_dir.exists():
            db_dir.mkdir(parents=True)
            
        logger.debug(f"Initializing credits database at {self.db_path}")
        conn = sqlite3.connect(self.db_path)
        try:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS user_credits (
                    email TEXT PRIMARY KEY,
                    credits INTEGER DEFAULT 5,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            logger.info("Credits database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise
        finally:
            conn.close()
    
    def get_credits(self, email: str) -> int:
        """Get the number of remaining credits for a user.
        
        Args:
            email: The user's email address.
            
        Returns:
            int: Number of remaining credits. Returns 5 for new users.
        """
        logger.debug(f"Getting credits for user: {email}")
        conn = sqlite3.connect(self.db_path)
        try:
            c = conn.cursor()
            c.execute("SELECT credits FROM user_credits WHERE email=?", (email,))
            result = c.fetchone()
            
            if result is None:
                # Initialize new user with 5 credits
                logger.info(f"Initializing credits for new user: {email}")
                c.execute(
                    "INSERT INTO user_credits (email, credits) VALUES (?, ?)",
                    (email, 5)
                )
                conn.commit()
                return 5
                
            return result[0]
        except Exception as e:
            logger.error(f"Failed to get credits: {str(e)}")
            raise
        finally:
            conn.close()
    
    def use_credit(self, email: str) -> bool:
        """Use one credit for the specified user.
        
        Args:
            email: The user's email address.
            
        Returns:
            bool: True if credit was successfully used, False if no credits remaining.
        """
        logger.debug(f"Attempting to use credit for user: {email}")
        conn = sqlite3.connect(self.db_path)
        try:
            c = conn.cursor()
            c.execute("SELECT credits FROM user_credits WHERE email=?", (email,))
            result = c.fetchone()
            
            if result is None:
                # Initialize new user with 5 credits
                c.execute(
                    "INSERT INTO user_credits (email, credits) VALUES (?, ?)",
                    (email, 5)
                )
                conn.commit()
                result = (5,)
            
            current_credits = result[0]
            if current_credits <= 0:
                logger.warning(f"No credits remaining for user: {email}")
                return False
            
            # Deduct one credit
            c.execute(
                "UPDATE user_credits SET credits=? WHERE email=?",
                (current_credits - 1, email)
            )
            conn.commit()
            logger.info(f"Successfully used credit for {email}. {current_credits - 1} remaining")
            return True
        except Exception as e:
            logger.error(f"Failed to use credit: {str(e)}")
            raise
        finally:
            conn.close()
    
    def add_credits(self, email: str, amount: int):
        """Add credits to a user's account.
        
        Args:
            email: The user's email address.
            amount: Number of credits to add (must be positive).
        """
        if amount <= 0:
            raise ValueError("Credit amount must be positive")
            
        logger.debug(f"Adding {amount} credits for user: {email}")
        conn = sqlite3.connect(self.db_path)
        try:
            c = conn.cursor()
            c.execute("SELECT credits FROM user_credits WHERE email=?", (email,))
            result = c.fetchone()
            
            if result is None:
                # Initialize new user with 5 + amount credits
                c.execute(
                    "INSERT INTO user_credits (email, credits) VALUES (?, ?)",
                    (email, 5 + amount)
                )
            else:
                current_credits = result[0]
                c.execute(
                    "UPDATE user_credits SET credits=? WHERE email=?",
                    (current_credits + amount, email)
                )
            
            conn.commit()
            logger.info(f"Successfully added {amount} credits for {email}")
        except Exception as e:
            logger.error(f"Failed to add credits: {str(e)}")
            raise
        finally:
            conn.close()
    
    def set_credits(self, email: str, amount: int):
        """Set a user's credits to a specific amount.
        
        Args:
            email: The user's email address.
            amount: Number of credits to set (must be non-negative).
        """
        if amount < 0:
            raise ValueError("Credit amount must be non-negative")
            
        logger.debug(f"Setting credits to {amount} for user: {email}")
        conn = sqlite3.connect(self.db_path)
        try:
            c = conn.cursor()
            c.execute(
                "INSERT OR REPLACE INTO user_credits (email, credits) VALUES (?, ?)",
                (email, amount)
            )
            conn.commit()
            logger.info(f"Successfully set credits to {amount} for {email}")
        except Exception as e:
            logger.error(f"Failed to set credits: {str(e)}")
            raise
        finally:
            conn.close()
