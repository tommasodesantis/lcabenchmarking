FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip3 install -r requirements.txt

# Copy application code
COPY . .

# Create .streamlit directory and config
RUN mkdir -p .streamlit

# Script to generate secrets.toml from environment variables
RUN echo '#!/bin/sh\n\
echo "ENVIRONMENT = \"$ENVIRONMENT\"\n\
\n\
R2R_API_KEY = \"$R2R_API_KEY\"\n\
OPENROUTER_API_KEY = \"$OPENROUTER_API_KEY\"\n\
REQUESTY_API_KEY = \"$REQUESTY_API_KEY\"\n\
\n\
TOKEN_KEY = \"$TOKEN_KEY\"\n\
\n\
SUPABASE_URL = \"$SUPABASE_URL\"\n\
SUPABASE_KEY = \"$SUPABASE_KEY\"\n\
\n\
usernames = $USERNAMES\n\
passwords = $PASSWORDS\n\
\n\
[google_oauth]\n\
client_id = \"$GOOGLE_OAUTH_CLIENT_ID\"\n\
client_secret = \"$GOOGLE_OAUTH_CLIENT_SECRET\"\n\
project_id = \"$GOOGLE_OAUTH_PROJECT_ID\"\n\
auth_uri = \"https://accounts.google.com/o/oauth2/auth\"\n\
token_uri = \"https://oauth2.googleapis.com/token\"\n\
auth_provider_x509_cert_url = \"https://www.googleapis.com/oauth2/v1/certs\"\n\
redirect_uris = [\"http://localhost:8501/\"]" > .streamlit/secrets.toml' > /app/generate_secrets.sh

RUN chmod +x /app/generate_secrets.sh

# Expose Streamlit port
EXPOSE 8501

# Add health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Run the application
ENTRYPOINT ["/bin/sh", "-c", "/app/generate_secrets.sh && streamlit run app_ui.py --server.port=8501 --server.address=0.0.0.0"]
