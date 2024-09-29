# bot.py

import asyncio
import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters
)
from db import init_db, get_user_filters, set_user_filters, reset_user_filters
from db import has_user_received_listing, mark_listing_as_sent
from olx_api import fetch_listings, fetch_districts
from telegram.helpers import escape_markdown
import difflib
from bs4 import BeautifulSoup

load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Initialize the database before any database access
init_db()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

SET_MIN_PRICE, SET_MAX_PRICE, ADD_LOCATION, REMOVE_LOCATION = range(4)

def escape_text(text):
    """
    Escape text for Telegram's Markdown V1 to prevent formatting issues.
    """
    if text is None:
        return ''
    return escape_markdown(str(text), version=1)

def replace_html_tags(text):
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(separator=' ')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_user_filters(user_id) is None:
        set_user_filters(user_id, min_price=None, max_price=None, districts=[])

    await update.message.reply_text(
        "Welcome to the OLX Apartment Bot! Use the /help command to see available options."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Available commands:\n"
        "/start - Start the bot and show the main menu.\n"
        "/help - Show available commands.\n"
        "/setprice - Set the price range.\n"
        "/addlocation - Add a district to search.\n"
        "/removelocation - Remove a district from the search.\n"
        "/getfilters - Show current filters.\n"
        "/resetfilters - Reset all filters to default.\n"
        "/search - Start searching for new listings.\n"
        "/stop - Stop searching for new listings."
    )
    await update.message.reply_text(help_text)

async def set_price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please enter the minimum price:")
    return SET_MIN_PRICE

async def set_min_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    min_price = update.message.text
    if not min_price.isdigit():
        await update.message.reply_text("Please enter a valid number for the minimum price.")
        return SET_MIN_PRICE
    context.user_data['min_price'] = int(min_price)
    await update.message.reply_text("Great! Now, please enter the maximum price:")
    return SET_MAX_PRICE

async def set_max_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    max_price = update.message.text
    if not max_price.isdigit():
        await update.message.reply_text("Please enter a valid number for the maximum price.")
        return SET_MAX_PRICE

    min_price = context.user_data.get('min_price')
    max_price = int(max_price)

    if min_price > max_price:
        await update.message.reply_text("Maximum price should be greater than minimum price.")
        return SET_MAX_PRICE

    user_id = update.effective_user.id
    filters = get_user_filters(user_id)

    if filters is None:
        filters = {'min_price': None, 'max_price': None, 'districts': []}

    set_user_filters(user_id, min_price=min_price, max_price=max_price, districts=filters.get('districts', []))
    await update.message.reply_text(f"Price range successfully set to {min_price} - {max_price} zł.")
    return ConversationHandler.END

async def add_location_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please enter the district names you want to add (separated by commas):")
    return ADD_LOCATION

async def add_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    input_text = update.message.text.lower()
    district_names = [d.strip() for d in input_text.split(',')]
    district_name_to_id = context.bot_data.get('district_name_to_id', {})

    added_districts = []
    invalid_districts = []

    for district in district_names:
        if district in district_name_to_id:
            district_id = district_name_to_id[district]
            filters = get_user_filters(user_id)
            if district_id not in filters['districts']:
                filters['districts'].append(district_id)
                set_user_filters(user_id, min_price=filters['min_price'], max_price=filters['max_price'],
                                 districts=filters['districts'])
                added_districts.append(district.title())
            else:
                continue
        else:
            invalid_districts.append(district.title())

    if added_districts:
        await update.message.reply_text(f"Added locations: {', '.join(added_districts)}")
    if invalid_districts:
        suggestions = []
        for invalid_district in invalid_districts:
            matches = difflib.get_close_matches(invalid_district.lower(), district_name_to_id.keys(), n=3, cutoff=0.6)
            if matches:
                suggestions.append(f"{invalid_district}: {', '.join([m.title() for m in matches])}")
            else:
                suggestions.append(f"{invalid_district}: No suggestions")

        await update.message.reply_text(
            "Some districts were not recognized:\n" + "\n".join(suggestions)
        )
    return ConversationHandler.END

async def remove_location_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please enter the district names you want to remove (separated by commas):")
    return REMOVE_LOCATION

async def remove_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    input_text = update.message.text.lower()
    district_names = [d.strip() for d in input_text.split(',')]
    district_name_to_id = context.bot_data.get('district_name_to_id', {})

    removed_districts = []
    invalid_districts = []

    for district in district_names:
        district_id = district_name_to_id.get(district)
        if district_id:
            filters = get_user_filters(user_id)
            if district_id in filters['districts']:
                filters['districts'].remove(district_id)
                set_user_filters(user_id, min_price=filters['min_price'], max_price=filters['max_price'],
                                 districts=filters['districts'])
                removed_districts.append(district.title())
            else:
                invalid_districts.append(district.title())
        else:
            invalid_districts.append(district.title())

    if removed_districts:
        await update.message.reply_text(f"Removed locations: {', '.join(removed_districts)}")
    if invalid_districts:
        await update.message.reply_text(f"Could not remove unrecognized or unlisted districts: {', '.join(invalid_districts)}")
    return ConversationHandler.END

async def reset_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    reset_user_filters(user_id)
    await update.message.reply_text("All filters have been reset.")

async def get_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    filters = get_user_filters(user_id)

    if filters is None:
        await update.message.reply_text("You haven't set any filters yet.")
        return

    message = "Current filters:\n"
    message += f"Price range: {filters.get('min_price', 'Not set')} - {filters.get('max_price', 'Not set')} zł\n"

    if filters['districts']:
        district_name_to_id = context.bot_data.get('district_name_to_id', {})
        id_to_district_name = {v: k for k, v in district_name_to_id.items()}
        districts = [id_to_district_name.get(id, 'Unknown').title() for id in filters['districts']]
        message += "Locations: " + ', '.join(districts)
    else:
        message += "Locations: All"

    await update.message.reply_text(message)

async def send_listing(context: ContextTypes.DEFAULT_TYPE, user_id, listing):
    description = escape_text(replace_html_tags(listing.get('description', '')))

    if len(description) > 200:
        description = description[:200] + '...'

    rent_additional = escape_text(listing.get('rent_additional', 'No czynsz') or 'No czynsz')
    district = escape_text(listing.get('district_name', 'District not provided') or 'District not provided')
    area = escape_text(listing.get('area', 'N/A') or 'N/A')
    rooms = escape_text(listing.get('rooms', 'N/A') or 'N/A')
    is_owner = 'Yes' if not listing['is_business'] else 'No'
    is_owner = escape_text(is_owner)

    # Escape constants that contain special characters
    title_const = "*Title:*"
    price_const = "*Price:*"
    district_const = "*District:*"
    area_const = "*Area:*"
    rooms_const = "*Rooms:*"
    czynsz_const = "*Czynsz (additional):*"
    from_owner_const = "From owner:"
    view_listing_const = "View Listing"

    message = (
        f"{title_const} {escape_text(listing['title'])}\n"
        f"💰 {price_const} {escape_text(listing['price'])} - {district_const} {district}\n"
        f"📐 {area_const} {area}, {rooms_const} {rooms}\n"
        f"💸 {czynsz_const} {rent_additional}\n"
        f"📝 {description}\n"
        f"{from_owner_const} {is_owner}\n"
        f"🔗 [{escape_text(view_listing_const)}]({escape_text(listing['url'])})"
    )

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode='Markdown',
            disable_web_page_preview=False
        )
    except Exception as e:
        logger.error(f"Error sending message to user {user_id}: {e}")
        await context.bot.send_message(
            chat_id=user_id,
            text="An error occurred while sending a listing. Please try again later."
        )

async def check_new_listings(context: ContextTypes.DEFAULT_TYPE):
    try:
        job = context.job
        user_id = job.data['user_id']
        filters = get_user_filters(user_id)
        if filters is None:
            return
        search_filters = {
            'min_price': filters['min_price'],
            'max_price': filters['max_price'],
            'district_ids': filters['districts']
        }
        listings = fetch_listings(search_filters)
        if not listings:
            await context.bot.send_message(chat_id=user_id, text="No new listings found matching your criteria.")
            return
        for listing in listings:
            listing_id = listing['id']
            if not has_user_received_listing(user_id, listing_id):
                await send_listing(context, user_id, listing)
                mark_listing_as_sent(user_id, listing_id)
    except Exception as e:
        logger.error(f"Error in check_new_listings: {e}")
        await context.bot.send_message(chat_id=user_id, text="An error occurred while checking for new listings.")

async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_jobs = context.job_queue.get_jobs_by_name(str(user_id))
    if current_jobs:
        await update.message.reply_text("Search is already running.")
        return
    context.job_queue.run_repeating(
        check_new_listings,
        interval=10,  # check every 5 minutes
        first=0,
        data={'user_id': user_id},
        name=str(user_id)
    )
    await update.message.reply_text("Started searching for new listings.")

async def stop_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_jobs = context.job_queue.get_jobs_by_name(str(user_id))
    if not current_jobs:
        await update.message.reply_text("No active search to stop.")
        return
    for job in current_jobs:
        job.schedule_removal()
    await update.message.reply_text("Stopped searching for new listings.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling an update:", exc_info=context.error)
    if update and hasattr(update, 'message') and update.message:
        await update.message.reply_text("An error occurred. Please try again later.")

def main():
    district_name_to_id = fetch_districts()
    if not district_name_to_id:
        logger.error("Failed to fetch district mapping.")
        return

    application = ApplicationBuilder().token(TOKEN).build()

    application.bot_data['district_name_to_id'] = district_name_to_id

    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('getfilters', get_filters))
    application.add_handler(CommandHandler('resetfilters', reset_filters))
    application.add_handler(CommandHandler('search', start_search))
    application.add_handler(CommandHandler('stop', stop_search))

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('setprice', set_price_command),
            CommandHandler('addlocation', add_location_command),
            CommandHandler('removelocation', remove_location_command),
        ],
        states={
            SET_MIN_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_min_price)],
            SET_MAX_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_max_price)],
            ADD_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_location)],
            REMOVE_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_location)],
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)],
    )
    application.add_handler(conv_handler)

    # Add error handler
    application.add_error_handler(error_handler)

    application.run_polling()

if __name__ == '__main__':
    main()
