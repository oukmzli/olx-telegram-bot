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

load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

SET_MIN_PRICE, SET_MAX_PRICE, ADD_LOCATION, REMOVE_LOCATION = range(4)


def escape_text(text):
    """
    escape text for Telegram's Markdown V2 to prevent formatting issues.
    """
    return escape_markdown(text, version=2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_user_filters(user_id) is None:
        set_user_filters(user_id, min_price=None, max_price=None, districts=[])

    await update.message.reply_text(
        "welcome to the OLX Apartment Bot! Use the command menu to navigate."
    )


async def set_price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please enter the minimum price:")
    return SET_MIN_PRICE


async def set_min_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    min_price = update.message.text
    if not min_price.isdigit():
        await update.message.reply_text("Please enter a valid number.")
        return SET_MIN_PRICE
    context.user_data['min_price'] = int(min_price)
    await update.message.reply_text("Please enter the maximum price:")
    return SET_MAX_PRICE


async def set_max_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    max_price = update.message.text
    if not max_price.isdigit():
        await update.message.reply_text("Please enter a valid number.")
        return SET_MAX_PRICE
    min_price = context.user_data.get('min_price')
    max_price = int(max_price)
    if min_price > max_price:
        await update.message.reply_text("Maximum price should be greater than minimum price.")
        return SET_MAX_PRICE
    user_id = update.effective_user.id
    filters = get_user_filters(user_id)
    set_user_filters(user_id, min_price=min_price, max_price=max_price, districts=filters['districts'])
    await update.message.reply_text(f"Price range set to {min_price} - {max_price} zł")
    return ConversationHandler.END


async def add_location_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please enter the district name you want to add:")
    return ADD_LOCATION


async def add_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    district = update.message.text.lower()
    district_name_to_id = context.bot_data.get('district_name_to_id', {})
    district_id = district_name_to_id.get(district)
    if district_id:
        filters = get_user_filters(user_id)
        if district_id not in filters['districts']:
            filters['districts'].append(district_id)
            set_user_filters(user_id, min_price=filters['min_price'], max_price=filters['max_price'],
                             districts=filters['districts'])
            await update.message.reply_text(f"Added location: {district.title()}")
        else:
            await update.message.reply_text("Location already in filters.")
    else:
        await update.message.reply_text(
            "Unknown district. Please check the spelling or add the district to the mapping.")
    return ConversationHandler.END


async def remove_location_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please enter the district name you want to remove:")
    return REMOVE_LOCATION


async def remove_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    district = update.message.text.lower()
    district_name_to_id = context.bot_data.get('district_name_to_id', {})
    district_id = district_name_to_id.get(district)
    if district_id:
        filters = get_user_filters(user_id)
        if district_id in filters['districts']:
            filters['districts'].remove(district_id)
            set_user_filters(user_id, min_price=filters['min_price'], max_price=filters['max_price'],
                             districts=filters['districts'])
            await update.message.reply_text(f"Removed location: {district.title()}")
        else:
            await update.message.reply_text("Location not in your filters.")
    else:
        await update.message.reply_text("Unknown district.")
    return ConversationHandler.END


async def reset_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    reset_user_filters(user_id)
    await update.message.reply_text("All filters have been reset.")


async def get_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    filters = get_user_filters(user_id)
    message = "Current filters:\n"
    message += f"Price range: {filters['min_price']} - {filters['max_price']} zł\n"
    if filters['districts']:
        district_name_to_id = context.bot_data.get('district_name_to_id', {})
        districts = [name for name, id in district_name_to_id.items() if id in filters['districts']]
        message += "Locations: " + ', '.join([d.title() for d in districts])
    else:
        message += "Locations: All"
    await update.message.reply_text(message)


async def replace_html_tags(text):
    """
    replaces basic HTML tags for better readability
    """
    import re
    import html

    # Unescape HTML entities
    text = html.unescape(text)

    # Remove all HTML tags
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


async def send_listing(context: ContextTypes.DEFAULT_TYPE, user_id, listing):
    """
    send a formatted listing to the user
    """
    description = escape_text(replace_html_tags(listing['description']))

    if len(description) > 200:
        description = description[:200] + '...'

    rent_additional = listing.get('rent_additional', 'No czynsz')
    district = escape_text(listing.get('district_name', 'District not provided'))
    area = escape_text(listing.get('area', 'N/A'))
    rooms = escape_text(listing.get('rooms', 'N/A'))

    message = (
        f"*Title:* {escape_text(listing['title'])}\n"
        f"💰 *Price:* {escape_text(listing['price'])} - *District:* {district}\n"
        f"📐 *Area:* {area}, *Rooms:* {rooms}\n"
        f"💸 *Czynsz (additional):* {escape_text(rent_additional)}\n"
        f"📝 {description}\n"
        f"From owner: {'Yes' if not listing['is_business'] else 'No'}\n"
        f"🔗 [View Listing]({escape_text(listing['url'])})"
    )

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode='MarkdownV2',
            disable_web_page_preview=False
        )
    except Exception as e:
        logger.error(f"Error sending message to user {user_id}: {e}")


async def check_new_listings(context: ContextTypes.DEFAULT_TYPE):
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
    for listing in listings:
        listing_id = listing['id']
        if not has_user_received_listing(user_id, listing_id):
            await send_listing(context, user_id, listing)
            mark_listing_as_sent(user_id, listing_id)


async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_jobs = context.job_queue.get_jobs_by_name(str(user_id))
    if current_jobs:
        await update.message.reply_text("Search is already running.")
        return
    context.job_queue.run_repeating(
        check_new_listings,
        interval=20,  # check every 5 minutes
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


def main():
    init_db()

    district_name_to_id = fetch_districts()
    if not district_name_to_id:
        logger.error("Failed to fetch district mapping.")
        return

    application = ApplicationBuilder().token(TOKEN).build()

    application.bot_data['district_name_to_id'] = district_name_to_id

    application.add_handler(CommandHandler('start', start))
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

    # Start the bot
    application.run_polling()


if __name__ == '__main__':
    main()
