# bot.py

import asyncio
import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from db import (
    init_db, get_user_filters, set_user_filters, reset_user_filters,
    has_user_received_listing, mark_listing_as_sent, set_user_active,
    get_active_users, save_listings_to_db, get_listings_from_db,
    clean_old_listings
)
from olx_api import fetch_listings, fetch_districts
from telegram.helpers import escape_markdown
import difflib
from bs4 import BeautifulSoup
from unidecode import unidecode
import datetime

load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
last_listing_time = None

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
        "Welcome to the OLX Apartment Bot! Use the /help command to see available options, or simply use /search to start."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Available commands:\n"
        "/start - Start the bot and show the main menu.\n"
        "/help - Show available commands.\n"
        "/search - Start searching for new listings.\n"
        "/stop - Stop searching for new listings.\n"
        "/setprice - Set the price range.\n"
        "/listdistricts - Display available districts.\n"
        "/setfromowner - Toggle 'From Owner' setting.\n"
        "/usetotalprice - Toggle using total price (price + czynsz).\n"
        "/getfilters - Show current filters.\n"
        "/resetfilters - Reset all filters to default."
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
    # await update.message.reply_text("Please enter the district names you want to add (separated by commas):")
    # return ADD_LOCATION
    await update.message.reply_text("Please use /listdistricts to add or remove locations using the interactive menu.")
    return ConversationHandler.END


# async def add_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_id = update.effective_user.id
#     input_text = unidecode(update.message.text.lower())
#     district_names = [d.strip() for d in input_text.split(',')]
#     district_name_to_id = context.bot_data.get('district_name_to_id', {})
#
#     added_districts = []
#     invalid_districts = []
#
#     for district in district_names:
#         normalized_district = unidecode(district)
#         if normalized_district in district_name_to_id:
#             district_id = district_name_to_id[normalized_district]
#             filters = get_user_filters(user_id)
#             if district_id not in filters['districts']:
#                 filters['districts'].append(district_id)
#                 set_user_filters(user_id, min_price=filters['min_price'], max_price=filters['max_price'],
#                                  districts=filters['districts'])
#                 added_districts.append(district.title())
#             else:
#                 continue
#         else:
#             invalid_districts.append(district.title())
#
#     if added_districts:
#         await update.message.reply_text(f"Added locations: {', '.join(added_districts)}")
#     if invalid_districts:
#         suggestions = []
#         for invalid_district in invalid_districts:
#             matches = difflib.get_close_matches(unidecode(invalid_district), district_name_to_id.keys(), n=3, cutoff=0.6)
#             if matches:
#                 suggestions.append(f"{invalid_district}: {', '.join([m.title() for m in matches])}")
#             else:
#                 suggestions.append(f"{invalid_district}: No suggestions")
#
#         await update.message.reply_text(
#             "Some districts were not recognized:\n" + "\n".join(suggestions)
#         )
#     return ConversationHandler.END

async def remove_location_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # await update.message.reply_text("Please enter the district names you want to remove (separated by commas):")
    # return REMOVE_LOCATION
    await update.message.reply_text("Please use /listdistricts to add or remove locations using the interactive menu.")
    return ConversationHandler.END


# async def remove_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_id = update.effective_user.id
#     input_text = unidecode(update.message.text.lower())
#     district_names = [d.strip() for d in input_text.split(',')]
#     district_name_to_id = context.bot_data.get('district_name_to_id', {})
#
#     removed_districts = []
#     invalid_districts = []
#
#     for district in district_names:
#         normalized_district = unidecode(district)
#         district_id = district_name_to_id.get(normalized_district)
#         if district_id:
#             filters = get_user_filters(user_id)
#             if district_id in filters['districts']:
#                 filters['districts'].remove(district_id)
#                 set_user_filters(user_id, min_price=filters['min_price'], max_price=filters['max_price'],
#                                  districts=filters['districts'])
#                 removed_districts.append(district.title())
#             else:
#                 invalid_districts.append(district.title())
#         else:
#             invalid_districts.append(district.title())
#
#     if removed_districts:
#         await update.message.reply_text(f"Removed locations: {', '.join(removed_districts)}")
#     if invalid_districts:
#         suggestions = []
#         for invalid_district in invalid_districts:
#             matches = difflib.get_close_matches(unidecode(invalid_district), district_name_to_id.keys(), n=3, cutoff=0.6)
#             if matches:
#                 suggestions.append(f"{invalid_district}: {', '.join([m.title() for m in matches])}")
#             else:
#                 suggestions.append(f"{invalid_district}: No suggestions")
#
#         await update.message.reply_text(
#             "Some districts were not recognized or not in your filters:\n" + "\n".join(suggestions)
#         )
#     return ConversationHandler.END

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
        message += "Locations: " + ', '.join(districts) + "\n"
    else:
        message += "Locations: All\n"

    from_owner = filters.get('from_owner', False)
    use_total_price = filters.get('use_total_price', False)
    message += f"From owner only: {'Yes' if from_owner else 'No'}\n"
    message += f"Use total price (price + czynsz): {'Yes' if use_total_price else 'No'}\n"
    await update.message.reply_text(message)


async def set_from_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    filters = get_user_filters(user_id)
    if filters is None:
        await update.message.reply_text("Please set your filters before setting the 'From owner' preference.")
        return

    current_setting = filters.get('from_owner', False)
    new_setting = not current_setting
    set_user_filters(user_id, from_owner=new_setting)

    status = "now only" if new_setting else "no longer"
    await update.message.reply_text(f"You will {status} receive listings from owners.")


async def use_total_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    filters = get_user_filters(user_id)
    if filters is None:
        await update.message.reply_text("Please set your filters before setting the price preference.")
        return

    current_setting = filters.get('use_total_price', False)
    new_setting = not current_setting
    set_user_filters(user_id, use_total_price=new_setting)

    status = "now" if new_setting else "no longer"
    await update.message.reply_text(f"You will {status} use the total price (price + czynsz) for filtering.")


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
        f"🧭 {area_const} {area}, {rooms_const} {rooms}\n"
        f"🐙 {czynsz_const} {rent_additional}\n"
        f"📝 {description}\n"
        f"🥸 {from_owner_const} {is_owner}\n"
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


def parse_price(price_str):
    if price_str is None:
        return None
    price_str = price_str.replace(' ', '').replace('zł', '')
    try:
        return int(''.join(filter(str.isdigit, price_str)))
    except ValueError:
        return None

def get_total_price(listing):
    price_value = parse_price(listing.get('price', ''))
    rent_value = parse_price(listing.get('rent_additional', '0'))
    if price_value is None:
        return None
    return price_value + (rent_value or 0)

def filter_listings_for_user(listings, filters):
    filtered_listings = []
    for listing in listings:
        # Apply price filter
        use_total_price = filters.get('use_total_price', False)
        if use_total_price:
            price_value = get_total_price(listing)
        else:
            price_value = parse_price(listing.get('price', ''))

        if price_value is None:
            continue
        min_price = filters.get('min_price')
        max_price = filters.get('max_price')
        if min_price is not None and price_value < min_price:
            continue
        if max_price is not None and price_value > max_price:
            continue

        # Apply district filter
        district_ids = filters.get('districts')
        if district_ids:
            listing_district_id = listing.get('district_id')
            if listing_district_id not in district_ids:
                continue

        # Apply 'from_owner' filter
        from_owner = filters.get('from_owner', False)
        if from_owner and listing['is_business']:
            continue

        filtered_listings.append(listing)
    return filtered_listings


async def global_check_new_listings(context: ContextTypes.DEFAULT_TYPE):
    global last_listing_time
    try:
        active_user_ids = get_active_users()

        # Fetch listings with the time filter to avoid duplicates
        plistings, last_fetched_time = fetch_listings({}, time_filter=last_listing_time)

        if not plistings:
            logger.info("No new listings found.")
            return

        # Update the last_listing_time to avoid fetching duplicates in the next run
        last_listing_time = last_fetched_time

        # Save fetched listings to the database
        save_listings_to_db(plistings)

        for user_id in active_user_ids:
            filters = get_user_filters(user_id)
            if filters is None:
                continue

            user_listings = filter_listings_for_user(plistings, filters)

            for listing in user_listings:
                listing_id = listing['id']
                if not has_user_received_listing(user_id, listing_id):
                    await send_listing(context, user_id, listing)
                    mark_listing_as_sent(user_id, listing_id)

    except Exception as e:
        logger.error(f"Error in global_check_new_listings: {e}")

async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    filters = get_user_filters(user_id)
    if filters is None:
        await update.message.reply_text("Please set your filters before starting the search.")
        return

    set_user_active(user_id, True)
    await update.message.reply_text("Started searching for new listings.")
    await send_accumulated_listings(context, user_id)


async def send_accumulated_listings(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    try:
        filters = get_user_filters(user_id)
        if filters is None:
            return

        # Fetch listings from the database
        listings = get_listings_from_db()
        if not listings:
            logger.info("No listings found in the database.")
            return

        user_listings = filter_listings_for_user(listings, filters)

        for listing in user_listings:
            listing_id = listing['id']
            if not has_user_received_listing(user_id, listing_id):
                await send_listing(context, user_id, listing)
                mark_listing_as_sent(user_id, listing_id)
                await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"Error in send_accumulated_listings: {e}")


async def stop_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    set_user_active(user_id, False)
    await update.message.reply_text("Stopped searching for new listings.")


# Constants for pagination
ITEMS_PER_PAGE = 10


async def list_districts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    district_name_to_id = context.bot_data.get('district_name_to_id', {})

    if not district_name_to_id:
        await update.message.reply_text("No districts found. Please try again later.")
        return

    page = int(context.args[0]) if context.args else 0
    total_pages = (len(district_name_to_id) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    if page < 0 or page >= total_pages:
        await update.message.reply_text(f"Invalid page number. Total pages available: {total_pages}.")
        return

    # Get user's current districts
    filters = get_user_filters(user_id)
    user_districts = filters.get('districts', [])

    # Create buttons for each district (2 per line)
    districts = list(district_name_to_id.items())
    districts.sort()  # Sort districts alphabetically
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_districts = districts[start_idx:end_idx]

    keyboard = []
    for i in range(0, len(page_districts), 2):
        row = []
        for district_name, district_id in page_districts[i:i + 2]:
            # Check if the district is in user's filters
            if district_id in user_districts:
                display_name = f"✅ {district_name.title()}"
            else:
                display_name = district_name.title()
            row.append(InlineKeyboardButton(display_name, callback_data=f"toggle_district_{district_id}_{page}"))
        keyboard.append(row)

    # Add pagination buttons if necessary
    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"page_{page - 1}"))
    if end_idx < len(districts):
        navigation_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page + 1}"))

    if navigation_buttons:
        keyboard.append(navigation_buttons)

    # Add the 'Close' button
    keyboard.append([InlineKeyboardButton("Close", callback_data="close_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    new_text = f"Choose districts to add/remove (Page {page + 1}/{total_pages}):"

    if update.message:
        await update.message.reply_text(new_text, reply_markup=reply_markup)
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.message.edit_text(new_text, reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    filters = get_user_filters(user_id)
    user_districts = filters.get('districts', [])
    district_name_to_id = context.bot_data.get('district_name_to_id', {})

    # Handle closing the menu
    if query.data == "close_menu":
        await query.edit_message_text("Menu closed.")
        return

    # Handle pagination
    if query.data.startswith("page_"):
        page = int(query.data.split("_")[1])
        context.args = [str(page)]
        await list_districts(update, context)
        return

    # Handle toggling districts
    if query.data.startswith("toggle_district_"):
        parts = query.data.split("_")
        district_id = parts[2]
        page = int(parts[3]) if len(parts) > 3 else 0

        # Toggle the district in user's filters
        if district_id in user_districts:
            user_districts.remove(district_id)
            action = "removed from"
        else:
            user_districts.append(district_id)
            action = "added to"

        # Update the filters
        set_user_filters(user_id, min_price=filters['min_price'], max_price=filters['max_price'],
                         districts=user_districts)

        # Send feedback to the user
        # district_name = next((name for name, id in district_name_to_id.items() if id == district_id), "Unknown")
        # await query.message.reply_text(f"District '{district_name.title()}' has been {action} your filters.")

        # Refresh the menu
        context.args = [str(page)]
        await list_districts(update, context)
        return


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling an update:", exc_info=context.error)
    if update and hasattr(update, 'message') and update.message:
        await update.message.reply_text("An error occurred. Please try again later.")

async def clean_old_listings_job(context: ContextTypes.DEFAULT_TYPE):
    clean_old_listings()
    logger.info("Old listings cleaned from the database.")


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
    application.add_handler(CommandHandler('setfromowner', set_from_owner))
    application.add_handler(CommandHandler('usetotalprice', use_total_price))
    application.add_handler(CommandHandler('listdistricts', list_districts))
    application.add_handler(CallbackQueryHandler(button_handler))

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('setprice', set_price_command),
            CommandHandler('addlocation', add_location_command),
            CommandHandler('removelocation', remove_location_command),
        ],
        states={
            SET_MIN_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_min_price)],
            SET_MAX_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_max_price)],
            # ADD_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_location)],
            # REMOVE_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_location)],
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)],
    )
    application.add_handler(conv_handler)

    # Add error handler
    application.add_error_handler(error_handler)

    # Schedule the global job
    application.job_queue.run_repeating(global_check_new_listings, interval=10, first=0)
    # Schedule the cleaning job to run every day at midnight
    application.job_queue.run_daily(clean_old_listings_job, time=datetime.time(hour=0, minute=0, second=0))
    application.run_polling()


if __name__ == '__main__':
    main()
