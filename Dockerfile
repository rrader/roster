FROM python:3.11

WORKDIR /app

# Set environment varibles
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN apt-get update && apt install -y language-pack-uk && apt-get clean
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN python3 manage.py collectstatic

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
