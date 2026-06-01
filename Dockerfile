FROM python:3.11-slim

WORKDIR /app

# Install uv for fast dependency management
RUN pip install uv

# Copy dependency specifications
COPY pyproject.toml requirements.txt ./

# Install dependencies using uv directly into the system environment
RUN uv pip install --system -r requirements.txt
RUN uv pip install --system -e .

# Copy the rest of the application code
COPY . .

# Expose the port that Streamlit uses
EXPOSE 8501

# Healthcheck to ensure the container is running properly
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Command to run the Streamlit application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
