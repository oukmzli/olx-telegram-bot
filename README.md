# OLX Telegram Bot

This bot monitors OLX for new apartment listings in Krakow and notifies users via Telegram. It now uses the OLX API for data retrieval and includes enhanced features for a better user experience.

## Features

- Monitors OLX for new apartment listings using the OLX API.
- Allows users to set filters: price range, locations.
- Reset filters to default.
- Provides a command selection menu for easy navigation.
- Sends new listings to users with details.
- Users can start and stop the search.

## Commands

- `/start` - Start the bot and show the main menu.
- `/menu` - Display the main command menu.
- `/help` - Show available commands.
- `/setprice` - Set the price range.
- `/addlocation` - Add a district to search.
- `/removelocation` - Remove a district from the search.
- `/getfilters` - Show current filters.
- `/resetfilters` - Reset all filters to default.
- `/search` - Start searching for new listings.
- `/stop` - Stop searching for new listings.

## Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/oukmzli/olx-telegram-bot.git
   cd olx-telegram-bot
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Create a `.env` file and add your Telegram bot token:**

   ```bash
   echo "TELEGRAM_BOT_TOKEN=your_bot_token_here" > .env
   ```

4. **Run the bot:**

   ```bash
   python bot.py
   ```

## Docker Deployment

1. **Build the Docker image:**

   ```bash
   docker build -t olx-telegram-bot .
   ```

2. **Run the Docker container with database volume and environment variable:**

   ```bash
   docker run -d \
   --name olx-bot \
   --env TELEGRAM_BOT_TOKEN=your_bot_token_here \
   -v /path/on/host/listings.db:/app/listings.db \
   olx-telegram-bot
   ```
   Replace /path/on/host/listings.db with the actual path on your host machine where you want to store the database.

   Ensure that when running the Docker container, you pass the TELEGRAM_BOT_TOKEN via the --env flag as per your instructions.



olx-telegram-bot/
├── bot.py
├── db.py
├── olx_scraper.py
├── districts.py
├── requirements.txt
├── .gitignore
├── Dockerfile
├── .env (not included in version control)
└── README.md