# LCA Benchmarking Tool

A Streamlit web application for life-cycle assessment (LCA) benchmarking and retrieval.

## Docker Setup

### Prerequisites
- Docker installed on your system
- Environment variables configured (see Configuration section)

### Building the Docker Image
To build the Docker image, run:
```bash
docker build -t lca-benchmarker .
```

### Running the Container
To run the container:
```bash
docker run -p 8501:8501 --env-file .env lca-benchmarker
```

The application will be available at `http://localhost:8501`

### Configuration

1. Create a `.env` file based on `.env.example`:
```bash
cp .env.example .env
```

2. Update the following environment variables in `.env`:

#### API Keys
```
R2R_API_KEY=your_key_here
REQUESTY_API_KEY=your_key_here
OPENROUTER_API_KEY=your_key_here
```

#### Authentication
```
TOKEN_KEY=your_key_here
ENVIRONMENT=development
```

#### Supabase Configuration
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

#### Google OAuth Configuration
```
GOOGLE_OAUTH_CLIENT_ID=your_client_id
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret
GOOGLE_OAUTH_PROJECT_ID=your_project_id
```

#### Authentication Credentials
For development only. In production, use a secure credential management system.
```
USERNAMES=["user1", "user2"]
PASSWORDS=["pass1", "pass2"]
```

The Docker container will automatically generate the required `.streamlit/secrets.toml` file from these environment variables.

### Development Workflow

1. Make changes to your code
2. Rebuild the Docker image:
```bash
docker build -t lca-benchmarker .
```
3. Run the container with the new changes:
```bash
docker run -p 8501:8501 --env-file .env lca-benchmarker
```

### Health Check
The container includes a health check that monitors the Streamlit server status. You can check the container's health status using:
```bash
docker ps
```

### Security Notes
- Never commit the `.env` file or `.streamlit/secrets.toml` to version control
- Use secure methods to manage and distribute secrets in production
- Consider using Docker secrets or a dedicated secrets management service in production
