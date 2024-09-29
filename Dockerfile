# Dockerfile

FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]

#docker run -d \
#  --name olx-bot \
#  --env TELEGRAM_BOT_TOKEN=your_bot_token_here \
#  -v /path/on/host/listings.db:/app/listings.db \
#  olx-telegram-bot

# Ensure that when running the Docker container,
# you pass the TELEGRAM_BOT_TOKEN via the --env flag
# as per your instructions.