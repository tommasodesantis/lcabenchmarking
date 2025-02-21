import time
import streamlit as st
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from .token_manager import AuthTokenManager

class Authenticator:
    def __init__(
        self,
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
        
        self.redirect_uri = redirect_uri
        self.auth_token_manager = AuthTokenManager(
            cookie_name=cookie_name,
            token_key=token_key,
            token_duration_days=token_duration_days,
        )
        self.cookie_name = cookie_name

    def _initialize_flow(self) -> google_auth_oauthlib.flow.Flow:
        print("[OAuth] Initializing flow with redirect URI:", self.redirect_uri)
        client_config = {
            "web": {
                "client_id": st.secrets.google_oauth.client_id,
                "client_secret": st.secrets.google_oauth.client_secret,
                "auth_uri": st.secrets.google_oauth.auth_uri,
                "token_uri": st.secrets.google_oauth.token_uri,
                "auth_provider_x509_cert_url": st.secrets.google_oauth.auth_provider_x509_cert_url,
                "redirect_uris": [self.redirect_uri]  # Use environment-specific redirect URI
            }
        }
        print("[OAuth] Client config:", {
            "client_id": st.secrets.google_oauth.client_id,
            "auth_uri": st.secrets.google_oauth.auth_uri,
            "redirect_uris": [self.redirect_uri]
        })
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
        print("[OAuth] Generating auth URL with redirect URI:", self.redirect_uri)
        flow = self._initialize_flow()
        auth_url, _ = flow.authorization_url(
            access_type="offline", include_granted_scopes="true"
        )
        print("[OAuth] Generated auth URL:", auth_url)
        return auth_url

    def check_password_auth(self, username: str, password: str) -> bool:
        usernames = st.secrets.usernames
        passwords = st.secrets.passwords
        if username in usernames:
            idx = usernames.index(username)
            if password == passwords[idx]:
                # Set auth token for password authentication
                self.auth_token_manager.set_token(username, "pwd_auth")
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
                        time.sleep(1)  # Give the CookieManager time to set the cookie
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
            else:
                auth_url = self.get_auth_url()
                st.markdown(
                    f"""
                    <style>
                    .stButton>a {{
                        width: 100%;
                        display: inline-flex;
                        -webkit-box-align: center;
                        align-items: center;
                        -webkit-box-pack: center;
                        justify-content: center;
                        font-weight: 400;
                        padding: calc(0.75em - 1px) 1.5em;
                        border-radius: 0.25rem;
                        margin: 0px;
                        line-height: 1.6;
                        color: inherit;
                        width: auto;
                        background-color: rgb(255, 255, 255);
                        border: 1px solid rgba(49, 51, 63, 0.2);
                        text-decoration: none;
                    }}
                    .stButton>a:hover {{
                        border-color: rgb(49, 51, 63);
                        color: inherit;
                        text-decoration: none;
                    }}
                    </style>
                    <div class="stButton">
                        <a href="{auth_url}" target="_self">Login with Google</a>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    def check_auth(self):
        if st.session_state.connected:
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
            print("[OAuth] Received auth code:", auth_code[:5] + "..." if auth_code else None)
            print("[OAuth] Current redirect URI:", self.redirect_uri)
            flow = self._initialize_flow()
            try:
                flow.fetch_token(code=auth_code)
                creds = flow.credentials

                oauth_service = build(serviceName="oauth2", version="v2", credentials=creds)
                user_info = oauth_service.userinfo().get().execute()
                oauth_id = user_info.get("id")
                email = user_info.get("email")

                self.auth_token_manager.set_token(email, oauth_id)
                st.session_state.connected = True
                st.session_state.user_info = {
                    "oauth_id": oauth_id,
                    "email": email,
                }
            except Exception as e:
                error_msg = str(e)
                print("[OAuth Error] Authentication failed:", str(e))
                print("[OAuth Error] Redirect URI:", self.redirect_uri)
                if "redirect_uri_mismatch" in error_msg.lower():
                    st.error(f"OAuth Error: Redirect URI mismatch")
                    st.error(f"Configured redirect URI: {self.redirect_uri}")
                    st.error("Please ensure your Google OAuth client configuration matches your environment settings.")
                else:
                    st.error(f"Authentication failed: {error_msg}")
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
