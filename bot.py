import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler
import supabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase_client = supabase.create_client(supabase_url, supabase_key)

# Conversation states
SELECTING_ACTION, CREATING_COLLAB, SELECTING_COLLAB_TYPE, ENTERING_COLLAB_TITLE, ENTERING_COLLAB_DESC = range(5)

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and register the user."""
    user = update.effective_user
    
    # Check if user exists in database
    response = supabase_client.table("users").select("*").eq("telegram_id", str(user.id)).execute()
    
    if not response.data:
        # Register new user
        new_user = {
            "telegram_id": str(user.id),
            "name": user.full_name,
            "handle": user.username
        }
        supabase_client.table("users").insert(new_user).execute()
        logger.info(f"New user registered: {user.full_name}")
    
    # Create keyboard with options
    keyboard = [
        [InlineKeyboardButton("Browse Collaborations", callback_data="browse")],
        [InlineKeyboardButton("My Collaborations", callback_data="my_collabs")],
        [InlineKeyboardButton("Host a Collaboration", callback_data="host_collab")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Welcome to CollabRoom, {user.full_name}! 👋\n\n"
        "I'm here to help you discover and manage collaborations with other Web3 brands.\n\n"
        "What would you like to do?",
        reply_markup=reply_markup
    )
    
    return SELECTING_ACTION

async def my_collabs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show user's collaborations."""
    user = update.effective_user
    
    # Get user ID from database
    user_response = supabase_client.table("users").select("id").eq("telegram_id", str(user.id)).execute()
    
    if not user_response.data:
        await update.message.reply_text("You need to register first. Please use /start command.")
        return ConversationHandler.END
    
    user_id = user_response.data[0]["id"]
    
    # Get user's collaborations
    collabs_response = supabase_client.table("collaborations").select("*").or_(f"host_id.eq.{user_id},applicant_id.eq.{user_id}").execute()
    
    if not collabs_response.data:
        keyboard = [[InlineKeyboardButton("Host a Collaboration", callback_data="host_collab")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "You don't have any collaborations yet.\n\n"
            "Would you like to host one?",
            reply_markup=reply_markup
        )
    else:
        # Group collaborations by status
        hosted = []
        applied = []
        
        for collab in collabs_response.data:
            if collab["host_id"] == user_id:
                hosted.append(collab)
            else:
                applied.append(collab)
        
        # Create message
        message = "🔍 *Your Collaborations*\n\n"
        
        if hosted:
            message += "*Collaborations you're hosting:*\n"
            for collab in hosted:
                status_emoji = "🟢" if collab["status"] == "active" else "🟠"
                message += f"{status_emoji} *{collab['title']}* - {collab['status'].capitalize()}\n"
            message += "\n"
        
        if applied:
            message += "*Collaborations you've applied to:*\n"
            for collab in applied:
                status_emoji = "🟢" if collab["status"] == "active" else "🟠"
                message += f"{status_emoji} *{collab['title']}* - {collab['status'].capitalize()}\n"
        
        keyboard = [
            [InlineKeyboardButton("Host a New Collaboration", callback_data="host_collab")],
            [InlineKeyboardButton("Back to Main Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    return SELECTING_ACTION

async def host_collab(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the collaboration hosting process."""
    query = update.callback_query
    if query:
        await query.answer()
        
    # Get user's companies
    user = update.effective_user
    user_response = supabase_client.table("users").select("id").eq("telegram_id", str(user.id)).execute()
    
    if not user_response.data:
        await update.message.reply_text("You need to register first. Please use /start command.")
        return ConversationHandler.END
    
    user_id = user_response.data[0]["id"]
    
    companies_response = supabase_client.table("user_company_relations").select("companies(*)").eq("user_id", user_id).execute()
    
    if not companies_response.data:
        await update.message.reply_text(
            "You need to have a company profile to host a collaboration.\n\n"
            "Please create a company profile on our web dashboard first: https://collabroom.vercel.app/dashboard/companies/new"
        )
        return ConversationHandler.END
    
    # Ask for collaboration type
    keyboard = [
        [
            InlineKeyboardButton("AMA Session", callback_data="collab_type_ama"),
            InlineKeyboardButton("Twitter Space", callback_data="collab_type_twitter")
        ],
        [
            InlineKeyboardButton("Podcast Guest", callback_data="collab_type_podcast"),
            InlineKeyboardButton("Guest Blog", callback_data="collab_type_blog")
        ],
        [
            InlineKeyboardButton("Cross Promotion", callback_data="collab_type_promo"),
            InlineKeyboardButton("Other", callback_data="collab_type_other")
        ],
        [InlineKeyboardButton("Cancel", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(
            "What type of collaboration would you like to host?",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "What type of collaboration would you like to host?",
            reply_markup=reply_markup
        )
    
    return SELECTING_COLLAB_TYPE

async def select_collab_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle collaboration type selection."""
    query = update.callback_query
    await query.answer()
    
    collab_type = query.data.replace("collab_type_", "")
    context.user_data["collab_type"] = collab_type
    
    await query.edit_message_text(
        f"You selected: {collab_type.capitalize()}\n\n"
        "Please enter a title for your collaboration:"
    )
    
    return ENTERING_COLLAB_TITLE

async def enter_collab_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle collaboration title input."""
    title = update.message.text
    context.user_data["collab_title"] = title
    
    await update.message.reply_text(
        f"Title: {title}\n\n"
        "Now, please provide a detailed description of the collaboration:"
    )
    
    return ENTERING_COLLAB_DESC

async def enter_collab_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle collaboration description input and create the collaboration."""
    description = update.message.text
    user = update.effective_user
    
    # Get user data from context
    collab_type = context.user_data.get("collab_type")
    collab_title = context.user_data.get("collab_title")
    
    # Get user ID from database
    user_response = supabase_client.table("users").select("id").eq("telegram_id", str(user.id)).execute()
    user_id = user_response.data[0]["id"]
    
    # Get user's first company
    companies_response = supabase_client.table("user_company_relations").select("company_id").eq("user_id", user_id).execute()
    company_id = companies_response.data[0]["company_id"]
    
    # Create collaboration
    new_collab = {
        "title": collab_title,
        "description": description,
        "type": collab_type,
        "host_id": user_id,
        "company_id": company_id,
        "status": "active",
        "is_featured": False
    }
    
    response = supabase_client.table("collaborations").insert(new_collab).execute()
    
    if response.data:
        keyboard = [
            [InlineKeyboardButton("View My Collaborations", callback_data="my_collabs")],
            [InlineKeyboardButton("Back to Main Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🎉 Collaboration created successfully!\n\n"
            f"*{collab_title}*\n"
            f"Type: {collab_type.capitalize()}\n\n"
            "Your collaboration is now live and visible to other users.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "❌ There was an error creating your collaboration. Please try again later."
        )
    
    # Clear user data
    context.user_data.clear()
    
    return SELECTING_ACTION

async def browse_collabs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Browse available collaborations."""
    query = update.callback_query
    await query.answer()
    
    # Get active collaborations
    collabs_response = supabase_client.table("collaborations").select("*, companies(name)").eq("status", "active").limit(5).execute()
    
    if not collabs_response.data:
        keyboard = [[InlineKeyboardButton("Back to Main Menu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "There are no active collaborations at the moment.\n\n"
            "Check back later or host your own collaboration!",
            reply_markup=reply_markup
        )
    else:
        message = "🔍 *Available Collaborations*\n\n"
        
        for collab in collabs_response.data:
            message += f"*{collab['title']}*\n"
            message += f"Type: {collab['type'].capitalize()}\n"
            message += f"Hosted by: {collab['companies']['name']}\n"
            message += f"Description: {collab['description'][:100]}...\n\n"
        
        keyboard = []
        for collab in collabs_response.data:
            keyboard.append([InlineKeyboardButton(f"Apply to: {collab['title']}", callback_data=f"apply_{collab['id']}")])
        
        keyboard.append([InlineKeyboardButton("Back to Main Menu", callback_data="back_to_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    return SELECTING_ACTION

async def apply_to_collab(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Apply to a collaboration."""
    query = update.callback_query
    await query.answer()
    
    collab_id = query.data.replace("apply_", "")
    user = update.effective_user
    
    # Get user ID from database
    user_response = supabase_client.table("users").select("id").eq("telegram_id", str(user.id)).execute()
    user_id = user_response.data[0]["id"]
    
    # Update collaboration
    response = supabase_client.table("collaborations").update({"applicant_id": user_id, "status": "pending"}).eq("id", collab_id).execute()
    
    if response.data:
        collab = response.data[0]
        
        # Get host's telegram_id
        host_response = supabase_client.table("users").select("telegram_id").eq("id", collab["host_id"]).execute()
        host_telegram_id = host_response.data[0]["telegram_id"]
        
        # Notify the host (in a real bot, you would send a message to the host)
        logger.info(f"Notifying host with telegram_id {host_telegram_id} about new application")
        
        keyboard = [[InlineKeyboardButton("Back to Main Menu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "✅ Application submitted successfully!\n\n"
            f"You've applied to: *{collab['title']}*\n\n"
            "The host will be notified and can approve or reject your application.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            "❌ There was an error applying to this collaboration. Please try again later."
        )
    
    return SELECTING_ACTION

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Return to the main menu."""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("Browse Collaborations", callback_data="browse")],
        [InlineKeyboardButton("My Collaborations", callback_data="my_collabs")],
        [InlineKeyboardButton("Host a Collaboration", callback_data="host_collab")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "What would you like to do?",
        reply_markup=reply_markup
    )
    
    return SELECTING_ACTION

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("Operation cancelled.")
    else:
        await update.message.reply_text("Operation cancelled.")
    
    # Clear user data
    context.user_data.clear()
    
    return ConversationHandler.END

def main() -> None:
    """Run the bot."""
    # Create the Application
    application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    
    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECTING_ACTION: [
                CallbackQueryHandler(browse_collabs, pattern="^browse$"),
                CallbackQueryHandler(my_collabs, pattern="^my_collabs$"),
                CallbackQueryHandler(host_collab, pattern="^host_collab$"),
                CallbackQueryHandler(apply_to_collab, pattern="^apply_"),
                CallbackQueryHandler(back_to_menu, pattern="^back_to_menu$"),
            ],
            SELECTING_COLLAB_TYPE: [
                CallbackQueryHandler(select_collab_type, pattern="^collab_type_"),
                CallbackQueryHandler(cancel, pattern="^cancel$"),
            ],
            ENTERING_COLLAB_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_collab_title),
            ],
            ENTERING_COLLAB_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_collab_desc),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    application.add_handler(conv_handler)
    
    # Add command handlers
    application.add_handler(CommandHandler("my_collabs", my_collabs))
    application.add_handler(CommandHandler("host_collab", host_collab))
    
    # Start the Bot
    application.run_polling()

if __name__ == "__main__":
    main()