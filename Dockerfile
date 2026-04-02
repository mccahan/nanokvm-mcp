FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir fastapi uvicorn httpx websockets pycryptodome pillow

# Copy application
COPY nanokvm_mcp/ ./nanokvm_mcp/

# Install the package
RUN pip install --no-cache-dir -e .

# Default environment variables
ENV NANOKVM_HOST=10.0.1.117 \
    NANOKVM_USERNAME=admin \
    NANOKVM_PASSWORD=admin \
    NANOKVM_SCREEN_WIDTH=1920 \
    NANOKVM_SCREEN_HEIGHT=1080 \
    NANOKVM_USE_HTTPS=false \
    API_HOST=0.0.0.0 \
    API_PORT=8080

EXPOSE 8080

CMD ["python", "-m", "nanokvm_mcp.api"]
