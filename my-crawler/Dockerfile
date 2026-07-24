# First, specify the base Docker image.
# You can see the Docker images from Apify at https://hub.docker.com/r/apify/.
# You can also use any other image from Docker Hub.


FROM apify/actor-python-playwright:3.13-1.60.0

RUN apt update && apt install -yq git && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

ENV UV_PROJECT_ENVIRONMENT="/usr/local"

COPY pyproject.toml uv.lock ./

RUN echo "Python version:" \
    && python --version \
    && echo "Installing dependencies:" \
    && uv sync --frozen --no-install-project --no-editable --quiet --no-dev --inexact \
    && echo "All installed Python packages:" \
    && pip freeze
# Pin playwright to the version baked into the base image so it matches the browser binaries.
RUN uv pip install --system --reinstall --no-deps "playwright==1.60.0"
# Next, copy the remaining files and directories with the source code.
# Since we do this after installing the dependencies, quick build will be really fast
# for most source file changes.
COPY . ./

# Use compileall to ensure the runnability of the Actor Python code.
RUN python -m compileall -q .

# Specify how to launch the source code of your Actor.
CMD ["python", "-m", "my_crawler"]
