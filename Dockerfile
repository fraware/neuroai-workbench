FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src
RUN python -m pip install --no-cache-dir .
RUN useradd --create-home --uid 10001 workbench
USER workbench
VOLUME ["/workspace"]
EXPOSE 8765
ENTRYPOINT ["neuroai-workbench"]
CMD ["serve", "/workspace", "--host", "0.0.0.0", "--port", "8765"]
