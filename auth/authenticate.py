import time
import streamlit as st
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from .token_manager import AuthTokenManager
import logging

logger = logging.getLogger('auth.authenticate')

class Authenticator:
    def __init__(
        self,
        allowed_users: list,
        secret_path: str,
        redirect_uri: str,
        token_key: str,
        cookie_name: str = "auth_jwt",
        token_duration_days: int = 1,
    ):
        logger.debug("Initializing Authenticator")
        # Initialize session state variables
        if 'auth_method' not in st.session_state:
            logger.debug("Initializing auth_method in session state")
            st.session_state.auth_method = None
        if 'connected' not in st.session_state:
            logger.debug("Initializing connected state in session state")
            st.session_state.connected = False
        if 'user_info' not in st.session_state:
            logger.debug("Initializing user_info in session state")
            st.session_state.user_info = None
        
        self.allowed_users = allowed_users
        self.secret_path = secret_path
        self.redirect_uri = redirect_uri
        self.auth_token_manager = AuthTokenManager(
            cookie_name=cookie_name,
            token_key=token_key,
            token_duration_days=token_duration_days,
        )
        self.cookie_name = cookie_name

    def _initialize_flow(self) -> google_auth_oauthlib.flow.Flow:
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            self.secret_path,
            scopes=[
                "openid",
                "https://www.googleapis.com/auth/userinfo.profile",
                "https://www.googleapis.com/auth/userinfo.email",
            ],
            redirect_uri=self.redirect_uri,
        )
        return flow

    def get_auth_url(self) -> str:
        flow = self._initialize_flow()
        auth_url, _ = flow.authorization_url(
            access_type="offline", include_granted_scopes="true"
        )
        return auth_url

    def check_password_auth(self, username: str, password: str) -> bool:
        """Handle username/password authentication"""
        logger.debug(f"Attempting password authentication for user: {username}")
        usernames = st.secrets.usernames
        passwords = st.secrets.passwords
        if username in usernames:
            idx = usernames.index(username)
            if password == passwords[idx]:
                logger.info(f"Password authentication successful for user: {username}")
                # Set auth token for password authentication
                self.auth_token_manager.set_token(username, "pwd_auth")
                st.session_state.connected = True
                st.session_state.user_info = {"email": username}
                return True
        logger.warning(f"Password authentication failed for user: {username}")
        return False

    def login(self):
        """Display login interface with both authentication methods"""
        if not st.session_state.connected:
            auth_method = st.radio(
                "Choose login method:",
                ["Username/Password", "Google Account"],
                key="auth_method_radio"
            )

            if auth_method == "Username/Password":
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                if st.button("Login", key="pwd_login"):
                    if self.check_password_auth(username, password):
                        time.sleep(1)  # Give the CookieManager time to set the cookie
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
            else:
                auth_url = self.get_auth_url()
                st.link_button("Login with Google", auth_url)

    def check_auth(self):
        """Check authentication status and handle Google OAuth flow"""
        logger.debug("Checking authentication status")
        
        if st.session_state.connected:
            logger.debug("User is already authenticated")
            st.toast(":green[user is authenticated]")
            return

        if st.session_state.get("logout"):
            logger.debug("User is logged out")
            st.toast(":green[user logged out]")
            return

        # Check for existing token
        logger.debug("Checking for existing token")
        token = self.auth_token_manager.get_decoded_token()
        if token is not None:
            logger.info(f"Valid token found for user: {token.get('email')}")
            st.query_params.clear()
            st.session_state.connected = True
            st.session_state.user_info = {
                "email": token["email"],
                "oauth_id": token["oauth_id"],
            }
            st.rerun()

        time.sleep(1)  # important for the token to be set correctly

        # Handle Google OAuth callback
        auth_code = st.query_params.get("code")
        st.query_params.clear()
        if auth_code:
            logger.debug("Processing OAuth callback")
            flow = self._initialize_flow()
            try:
                flow.fetch_token(code=auth_code)
                creds = flow.credentials
                logger.debug("OAuth token fetched successfully")

                oauth_service = build(serviceName="oauth2", version="v2", credentials=creds)
                user_info = oauth_service.userinfo().get().execute()
                oauth_id = user_info.get("id")
                email = user_info.get("email")
                logger.debug(f"Retrieved user info for email: {email}")

                if email in self.allowed_users:
                    logger.info(f"Authorizing OAuth user: {email}")
                    self.auth_token_manager.set_token(email, oauth_id)
                    st.session_state.connected = True
                    st.session_state.user_info = {
                        "oauth_id": oauth_id,
                        "email": email,
                    }
                else:
                    logger.warning(f"Unauthorized OAuth attempt from: {email}")
                    st.toast(":red[access denied: Unauthorized user]")
            except Exception as e:
                logger.error(f"OAuth flow error: {str(e)}")
                st.toast(":red[OAuth authentication failed]")

    def logout(self):
        """Handle logout for both authentication methods"""
        logger.debug("Processing logout request")
        # Delete the auth token cookie first
        self.auth_token_manager.delete_token()
        
        # Set logout flag in session state
        st.session_state.connected = False
        st.session_state.user_info = None
        st.session_state.auth_method = None
        st.session_state.logout = True
        
        # Clear query parameters
        st.query_params.clear()
        logger.info("User successfully logged out")
