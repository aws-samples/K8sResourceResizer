# syntax=docker/dockerfile:1

ARG TARGETPLATFORM=linux/amd64
FROM --platform=$TARGETPLATFORM python:3.12-slim AS builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app:/app/Src" \
    DEBIAN_FRONTEND=noninteractive \
    CMDSTAN="/cmdstan" \
    CMDSTAN_VERSION="2.26.1" \
    STAN_BACKEND="CMDSTANPY"

# Install system dependencies
RUN apt upgrade -y && apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    curl \
    git \
    pkg-config \
    cmake \
    gcc \
    g++ \
    libopenblas-dev \
    python3-dev \
    make \
    wget \
    python3-wheel \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
WORKDIR /app
COPY pyproject.toml ./
COPY Src ./Src/

# Upgrade pip and install Cython first
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir "Cython==3.0.8"

# Now install remaining Python packages
RUN pip install --no-cache-dir \
    "setuptools==69.2.0" \
    "numpy==1.26.4" \
    "pandas==2.2.0" \
    "prophet==1.1.6" \
    "matplotlib==3.8.3" \
    "scikit-learn==1.4.1.post1" \
    "click==8.1.8" \
    "pyyaml==6.0.2" \
    "loguru==0.7.2" \
    "boto3==1.35.99" \
    "statsmodels==0.14.1" \
    "prometheus-api-client==0.5.5" \
    "ruamel-yaml==0.18.10" \
    "requests==2.32.3" \
    "requests-aws4auth==1.3.1" \
    "python-dotenv==1.0.1" \
    "scipy==1.12.0" \
    "pmdarima==2.0.4" \
    "pyinstaller==6.12.0" \
    "GitPython==3.1.44" \
    "pygithub==2.6.0"

# Create TEMP directory with proper permissions
RUN mkdir -p /app/TEMP && chmod 777 /app/TEMP

# Install CmdStan for Prophet
RUN mkdir -p $CMDSTAN && \
    wget -q https://github.com/stan-dev/cmdstan/releases/download/v${CMDSTAN_VERSION}/cmdstan-${CMDSTAN_VERSION}.tar.gz -O cmdstan.tar.gz && \
    tar -xf cmdstan.tar.gz -C $CMDSTAN --strip-components=1 && \
    rm cmdstan.tar.gz && \
    cd $CMDSTAN && \
    make build && \
    rm -rf $CMDSTAN/*.o

# Find Prophet package location and prepare files
RUN PROPHET_PATH=$(python -c "import prophet; print(prophet.__path__[0])") && \
    echo '__version__ = "1.1.6"' > __version__.py && \
    # Create the executable using PyInstaller with all dependencies
    pyinstaller --clean --onefile \
        --add-data "Src:Src" \
        --add-data "__version__.py:prophet" \
        --add-data "$PROPHET_PATH:prophet" \
        --add-data "$PROPHET_PATH/stan_model:prophet/stan_model" \
        --hidden-import=pandas \
        --hidden-import=numpy \
        --hidden-import=setuptools \
        --hidden-import=click \
        --hidden-import=click.core \
        --hidden-import=click.decorators \
        --hidden-import=click.parser \
        --hidden-import=click.types \
        --hidden-import=pmdarima \
        --hidden-import=sklearn \
        --hidden-import=sklearn.exceptions \
        --hidden-import=sklearn.utils \
        --hidden-import=sklearn.utils._param_validation \
        --hidden-import=statsmodels \
        --hidden-import=prophet \
        --hidden-import=prophet.models \
        --hidden-import=prophet.forecaster \
        --hidden-import=Cython.Plex \
        --hidden-import=Cython.Compiler.Lexicon \
        --hidden-import=Cython.Tempita._looper \
        --hidden-import=pystan.plots \
        --hidden-import=matplotlib \
        --hidden-import=pyyaml \
        --hidden-import=loguru \
        --hidden-import=boto3 \
        --hidden-import=requests \
        --hidden-import=requests_aws4auth \
        --hidden-import=python_dotenv \
        --hidden-import=scipy \
        --hidden-import=ruamel.yaml \
        --hidden-import=prometheus_api_client \
        --collect-data prophet \
        --collect-all pyyaml \
        --collect-all loguru \
        --collect-all boto3 \
        --collect-all requests \
        --collect-all requests_aws4auth \
        --collect-all python_dotenv \
        --collect-all scipy \
        --collect-all ruamel.yaml \
        --collect-all prometheus_api_client \
        --name k8s-limits \
        Src/main.py

# Install k3d, kubectl, and argocd
COPY Docker/install.sh /install.sh
RUN chmod +x /install.sh && /install.sh

# Update and upgrade all packages
RUN apt-get update && apt-get upgrade -y

# Final stage
FROM --platform=$TARGETPLATFORM ubuntu:24.04@sha256:3afff29dffbc200d202546dc6c4f614edc3b109691e7ab4aa23d02b42ba86790

ENV TZ=Etc/UTC \
    DEBIAN_FRONTEND=noninteractive

# Install minimal required packages
RUN set -eux; \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        openssl \
        curl \
        bash \
        tzdata \
        git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/

RUN mkdir -p /app/TEMP && chmod 777 /app/TEMP

# Copy binary, tools, and libraries from builder stage
COPY --from=builder /app/dist/k8s-limits /app/
COPY --from=builder /usr/local/bin/kind /usr/local/bin/
COPY --from=builder /usr/local/bin/kubectl /usr/local/bin/
COPY --from=builder /usr/local/bin/argocd /usr/local/bin/
COPY --from=docker:dind@sha256:e0b121dfc337c0f5a9703ef0914a392864bde6db811f2ba5bdd617a6e932073e /usr/local/bin/ /usr/local/bin/

# Set working directory
WORKDIR /app

# Copy entrypoint script
COPY Docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

