FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src
COPY scripts/docker-entrypoint.sh /usr/local/bin/neuroai-workbench-entrypoint
RUN python -m pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 workbench \
    && mkdir -p /workspace \
    && chown workbench:workbench /workspace
USER workbench
ENV NEUROAI_ALLOW_NETWORK=1
VOLUME ["/workspace"]
EXPOSE 8765
ENTRYPOINT ["neuroai-workbench-entrypoint"]
CMD ["serve", "/workspace", "--host", "0.0.0.0", "--port", "8765", "--allow-network"]
