# 사내 폐쇄망이라면 FROM 주소를 사내 레지스트리 미러로 바꾸세요.
FROM python:3.11-slim

WORKDIR /srv

# 사내 PyPI 미러(Nexus 등)를 쓸 때는 아래 build-arg 로 넘기면 됩니다.
#   docker compose build --build-arg PIP_INDEX_URL=https://nexus.내부/repository/pypi/simple
ARG PIP_INDEX_URL=""
ARG PIP_TRUSTED_HOST=""
ENV PIP_INDEX_URL=${PIP_INDEX_URL} PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/srv
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
