FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

ENV GPT_MODEL="gpt-4o"
# ENV OPENAI_KEY=""
# ENV GUESS_DELAY=""

CMD ["python", "run.py"]