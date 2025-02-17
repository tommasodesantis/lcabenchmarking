import time
import streamlit as st
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from .token_manager import AuthTokenManager

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
        # Initialize session state variables
        if 'auth_method' not in st.session_state:
            st.session_state.auth_method = None
        if 'connected' not in st.session_state:
            st.session_state.connected = False
        if 'user_info' not in st.session_state:
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
        usernames = st.secrets.usernames
        passwords = st.secrets.passwords
        if username in usernames:
            idx = usernames.index(username)
            if password == passwords[idx]:
                st.session_state.connected = True
                st.session_state.user_info = {"email": username}
                return True
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
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
            else:
                auth_url = self.get_auth_url()
                st.link_button("Login with Google", auth_url)

    def check_auth(self):
        """Check authentication status and handle Google OAuth flow"""
        if st.session_state.connected:
            st.toast(":green[user is authenticated]")
            return

        if st.session_state.get("logout"):
            st.toast(":green[user logged out]")
            return

        # Check for existing token
        token = self.auth_token_manager.get_decoded_token()
        if token is not None:
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
            flow = self._initialize_flow()
            flow.fetch_token(code=auth_code)
            creds = flow.credentials

            oauth_service = build(serviceName="oauth2", version="v2", credentials=creds)
            user_info = oauth_service.userinfo().get().execute()
            oauth_id = user_info.get("id")
            email = user_info.get("email")

            if email in self.allowed_users:
                self.auth_token_manager.set_token(email, oauth_id)
                st.session_state.connected = True
                st.session_state.user_info = {
                    "oauth_id": oauth_id,
                    "email": email,
                }
            else:
                st.toast(":red[access denied: Unauthorized user]")

    def logout(self):
        """Handle logout for both authentication methods"""
        st.session_state.logout = True
        st.session_state.user_info = None
        st.session_state.connected = False
        st.session_state.auth_method = None
        self.auth_token_manager.delete_token()
