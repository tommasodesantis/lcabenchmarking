import time
import streamlit as st
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from .token_manager import AuthTokenManager
import logging

logger = logging.getLogger('auth.authenticator')

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
        
        # Validate token_key before proceeding
        if not token_key:
            logger.error("Token key is empty or None")
            raise ValueError("A valid token key is required for authentication")
        
        logger.debug(f"Token key type: {type(token_key)}")
        logger.debug(f"Token key value: {token_key}")
        
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
        
        try:
            logger.debug("Creating AuthTokenManager")
            self.auth_token_manager = AuthTokenManager(
                cookie_name=cookie_name,
                token_key=token_key,
                token_duration_days=token_duration_days,
            )
            logger.info("AuthTokenManager created successfully")
        except Exception as e:
            logger.error(f"Failed to create AuthTokenManager: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            raise
            
        self.cookie_name = cookie_name

    def _initialize_flow(self) -> google_auth_oauthlib.flow.Flow:
        client_config = {
            "web": {
                "client_id": st.secrets.google_oauth.client_id,
                "client_secret": st.secrets.google_oauth.client_secret,
                "auth_uri": st.secrets.google_oauth.auth_uri,
                "token_uri": st.secrets.google_oauth.token_uri,
                "auth_provider_x509_cert_url": st.secrets.google_oauth.auth_provider_x509_cert_url,
                "redirect_uris": st.secrets.google_oauth.redirect_uris
            }
        }
        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            client_config,
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
        logger.debug(f"Attempting password authentication for username: {username}")
        usernames = st.secrets.usernames
        passwords = st.secrets.passwords
        
        if username in usernames:
            idx = usernames.index(username)
            if password == passwords[idx]:
                logger.info(f"Password authentication successful for user: {username}")
                try:
                    # Set auth token for password authentication
                    logger.debug("Attempting to set auth token")
                    self.auth_token_manager.set_token(username, "pwd_auth")
                    logger.info("Auth token set successfully")
                    
                    st.session_state.connected = True
                    st.session_state.user_info = {"email": username}
                    return True
                except Exception as e:
                    logger.error(f"Failed to set auth token: {str(e)}")
                    logger.error(f"Error type: {type(e)}")
                    raise
            else:
                logger.warning(f"Invalid password for username: {username}")
        else:
            logger.warning(f"Username not found: {username}")
        return False

    def login(self):
        """Display login interface with both authentication methods"""
        if not st.session_state.connected:
            logger.debug("User not connected, displaying login interface")
            auth_method = st.radio(
                "Choose login method:",
                ["Username/Password", "Google Account"],
                key="auth_method_radio"
            )
            logger.debug(f"Selected auth method: {auth_method}")

            if auth_method == "Username/Password":
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                if st.button("Login", key="pwd_login"):
                    logger.info(f"Login attempt for username: {username}")
                    try:
                        if self.check_password_auth(username, password):
                            logger.info("Login successful, waiting for cookie setup")
                            time.sleep(1)  # Give the CookieManager time to set the cookie
                            st.rerun()
                        else:
                            logger.warning("Login failed: Invalid credentials")
                            st.error("Invalid username or password")
                    except Exception as e:
                        logger.error(f"Login error: {str(e)}")
                        st.error(f"Login error: {str(e)}")
            else:
                auth_url = self.get_auth_url()
                st.link_button("Login with Google", auth_url)

    def check_auth(self):
        logger.debug("Checking authentication status")
        
        if st.session_state.connected:
            logger.debug("User already connected")
            st.toast(":green[user is authenticated]")
            return

        if st.session_state.get("logout"):
            logger.debug("User is logged out")
            st.toast(":green[user logged out]")
            return

        # Check for existing token
        logger.debug("Checking for existing token")
        try:
            token = self.auth_token_manager.get_decoded_token()
            if token is not None:
                logger.info("Valid token found")
                logger.debug(f"Token contents: {token}")
                st.query_params.clear()
                st.session_state.connected = True
                st.session_state.user_info = {
                    "email": token["email"],
                    "oauth_id": token["oauth_id"],
                }
                st.rerun()
            else:
                logger.debug("No valid token found")
        except Exception as e:
            logger.error(f"Error checking token: {str(e)}")

        time.sleep(1)  # important for the token to be set correctly

        # Handle Google OAuth callback
        auth_code = st.query_params.get("code")
        if auth_code:
            logger.info("Processing OAuth callback")
            st.query_params.clear()
            flow = self._initialize_flow()
            try:
                logger.debug("Fetching OAuth token")
                flow.fetch_token(code=auth_code)
                creds = flow.credentials

                logger.debug("Getting user info from OAuth")
                oauth_service = build(serviceName="oauth2", version="v2", credentials=creds)
                user_info = oauth_service.userinfo().get().execute()
                oauth_id = user_info.get("id")
                email = user_info.get("email")
                logger.debug(f"OAuth user info received for email: {email}")

                if email in self.allowed_users:
                    logger.info(f"Authorized OAuth user: {email}")
                    try:
                        self.auth_token_manager.set_token(email, oauth_id)
                        st.session_state.connected = True
                        st.session_state.user_info = {
                            "oauth_id": oauth_id,
                            "email": email,
                        }
                    except Exception as e:
                        logger.error(f"Failed to set token for OAuth user: {str(e)}")
                        raise
                else:
                    logger.warning(f"Unauthorized OAuth attempt from: {email}")
                    st.toast(":red[access denied: Unauthorized user]")
            except Exception as e:
                logger.error(f"OAuth authentication failed: {str(e)}")
                st.toast(":red[OAuth authentication failed]")

    def logout(self):
        # Delete the auth token cookie first
        self.auth_token_manager.delete_token()
        
        # Set logout flag in session state
        st.session_state.connected = False
        st.session_state.user_info = None
        st.session_state.auth_method = None
        st.session_state.logout = True
        
        # Clear query parameters
        st.query_params.clear()
