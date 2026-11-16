# syntax=docker/dockerfile:1
# Browser image for the Playwright smoke test (tests/e2e). Chromium only, so it stays small;
# the version matches @playwright/test in package.json.
FROM node:24-bookworm-slim
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN npx -y playwright@1.64.1 install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/* /root/.npm
WORKDIR /app
