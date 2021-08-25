FROM python:3.7-alpine

RUN apk update && apk add gcc musl-dev python3-dev libffi-dev openssl-dev cargo

WORKDIR /app
COPY ./requirements.txt /app/
RUN pip install -r /app/requirements.txt
RUN apk del gcc musl-dev libffi-dev openssl-dev cargo

ENV AZURE_CLIENT_ID ""
ENV AZURE_CLIENT_SECRET ""
ENV AZURE_TENANT_ID ""

COPY ./azure_vault_map.py /app/
RUN chmod +x /app/azure_vault_map.py

CMD ["python", "azure_vault_map.py"]
