FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY install_toolbox.py .
RUN python install_toolbox.py
COPY cascade_analyst ./cascade_analyst
COPY grant_advisor ./grant_advisor
COPY evidence_reviewer ./evidence_reviewer
COPY neighborhood_context ./neighborhood_context
COPY corridor_coordinator ./corridor_coordinator
COPY setup.py service.py start_service.py ./
EXPOSE 8080
CMD ["python", "start_service.py"]
