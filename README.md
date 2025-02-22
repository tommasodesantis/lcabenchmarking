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
- `R2R_API_KEY`: Your R2R API key
- `REQUESTY_API_KEY`: Your Requesty API key
- `OPENROUTER_API_KEY`: Your OpenRouter API key
- `TOKEN_KEY`: Your token key for authentication
- `ENVIRONMENT`: Set to `development` or `production`

3. Create a `.streamlit/secrets.toml` file with the same variables:
```toml
R2R_API_KEY = "your_key_here"
REQUESTY_API_KEY = "your_key_here"
OPENROUTER_API_KEY = "your_key_here"
TOKEN_KEY = "your_key_here"
ENVIRONMENT = "development"
```

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
