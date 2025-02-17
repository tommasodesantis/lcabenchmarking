from datetime import datetime, timedelta
import jwt
from jwt import ExpiredSignatureError
import streamlit as st
import extra_streamlit_components as stx
import logging

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
        self.token_key = token_key
        self.token_duration_days = token_duration_days
        self.token = None

    def get_decoded_token(self) -> str:
        logger.debug(f"Attempting to get token from cookie: {self.cookie_name}")
        self.token = self.cookie_manager.get(self.cookie_name)
        if self.token is None:
            logger.info("No token found in cookie")
            return None
        logger.debug("Token found in cookie, attempting to decode")
        self.token = self._decode_token()
        if self.token:
            logger.debug("Token successfully decoded")
        return self.token

    def set_token(self, email: str, oauth_id: str):
        logger.debug(f"Setting token for email: {email}")
        exp_date = (
            datetime.now() + timedelta(days=self.token_duration_days)
        ).timestamp()
        token = self._encode_token(email, oauth_id, exp_date)
        logger.debug(f"Token expiration set to: {datetime.fromtimestamp(exp_date)}")
        try:
            self.cookie_manager.set(
                self.cookie_name,
                token,
                expires_at=datetime.fromtimestamp(exp_date),
            )
            logger.info(f"Token successfully set in cookie for {email}")
        except Exception as e:
            logger.error(f"Failed to set token in cookie: {str(e)}")
            raise

    def delete_token(self):
        logger.debug(f"Attempting to delete token from cookie: {self.cookie_name}")
        try:
            self.cookie_manager.delete(self.cookie_name)
            logger.info("Token successfully deleted from cookie")
        except KeyError:
            logger.debug("No token found to delete")

    def _decode_token(self) -> str:
        try:
            decoded = jwt.decode(self.token, self.token_key, algorithms=["HS256"])
            logger.debug("Token successfully decoded")
            return decoded
        except ExpiredSignatureError:
            logger.warning("Token expired")
            st.toast(":red[token expired, please login]")
            self.delete_token()
            return None
        except Exception as e:
            logger.error(f"Failed to decode token: {str(e)}")
            return None

    def _encode_token(self, email: str, oauth_id: str, exp_date: float) -> str:
        logger.debug(f"Encoding token for email: {email}")
        try:
            encoded = jwt.encode(
                {"email": email, "oauth_id": oauth_id, "exp": exp_date},
                self.token_key,
                algorithm="HS256",
            )
            logger.debug("Token successfully encoded")
            return encoded
        except Exception as e:
            logger.error(f"Failed to encode token: {str(e)}")
            raise
