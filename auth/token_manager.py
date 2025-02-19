from datetime import datetime, timedelta
import jwt
from jwt import ExpiredSignatureError
import streamlit as st
import extra_streamlit_components as stx
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auth.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('auth.token_manager')

class AuthTokenManager:
    def __init__(
        self,
        cookie_name: str,
        token_key: str,
        token_duration_days: int,
    ):
        self.cookie_manager = stx.CookieManager()
        self.cookie_name = cookie_name
        
        # Validate token_key
        if token_key is None:
            logger.error("Token key is None")
            raise ValueError("Token key cannot be None")
        if not isinstance(token_key, str):
            logger.error(f"Token key is not a string. Type: {type(token_key)}")
            raise TypeError(f"Token key must be a string, not {type(token_key)}")
        if not token_key:
            logger.error("Token key is empty string")
            raise ValueError("Token key cannot be empty")
            
        self.token_key = str(token_key)  # Ensure it's a string
        self.token_duration_days = token_duration_days
        self.token = None
        
        logger.info(f"TokenManager initialized with key type: {type(self.token_key)}")
        logger.debug(f"Token key value: {self.token_key}")

    def get_decoded_token(self) -> str:
        self.token = self.cookie_manager.get(self.cookie_name)
        if self.token is None:
            return None
        self.token = self._decode_token()
        return self.token

    def set_token(self, email: str, oauth_id: str):
        exp_date = (
            datetime.now() + timedelta(days=self.token_duration_days)
        ).timestamp()
        token = self._encode_token(email, oauth_id, exp_date)
        self.cookie_manager.set(
            self.cookie_name,
            token,
            expires_at=datetime.fromtimestamp(exp_date),
        )

    def delete_token(self):
        try:
            self.cookie_manager.delete(self.cookie_name)
        except KeyError:
            pass

    def _decode_token(self) -> str:
        try:
            decoded = jwt.decode(self.token, self.token_key, algorithms=["HS256"])
            return decoded
        except ExpiredSignatureError:
            st.toast(":red[token expired, please login]")
            self.delete_token()
            return None
        except Exception:
            return None

    def _encode_token(self, email: str, oauth_id: str, exp_date: float) -> str:
        logger.debug(f"Encoding token for email: {email}")
        logger.debug(f"Token key type: {type(self.token_key)}")
        logger.debug(f"Token key value: {self.token_key}")
        
        payload = {"email": email, "oauth_id": oauth_id, "exp": exp_date}
        logger.debug(f"JWT payload: {payload}")
        
        try:
            token = jwt.encode(
                payload,
                self.token_key,
                algorithm="HS256",
            )
            logger.info("Token encoded successfully")
            return token
        except Exception as e:
            logger.error(f"Token encoding failed: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            raise
