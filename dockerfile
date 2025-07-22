FROM public.ecr.aws/lambda/python:3.12
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR ${LAMBDA_TASK_ROOT}

# Copy project files
COPY pyproject.toml uv.lock ./
COPY app ./app
COPY config ./config

# Install dependencies using uv pip install to system Python
RUN uv pip install --system -r <(uv export --format requirements-txt --no-hashes)

# Set the CMD to your handler
CMD [ "app.main.handler" ]