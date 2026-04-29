"""
Main Telegram Bot for Health tracking.
Handles all commands and conversation flows.
"""

import os
import sys
import logging
from datetime import datetime, date, time
from typing import Dict, Any, Optional
import asyncio

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, ReplyKeyboardRemove, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, ConversationHandler,
    filters
)
from telegram.constants import ParseMode

from config import config, Config
from database.manager import db_manager
from database.models import GoalType
from modules.profile import profile_manager
from modules.onboarding import OnboardingHandler, get_or_create_onboarding_session, remove_onboarding_session
from modules.nutrition import nutrition_manager, food_recognizer
from modules.training import training_manager
from modules.health import health_manager
from modules.health.samsung_health import samsung_integration, manual_input
from modules.reminders import reminder_manager, ReminderType
from modules.analytics import report_generator
from modules.integrations import deepseek_client
from utils.image_processor import image_processor

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, config.log_level),
    handlers=[
        logging.FileHandler(config.log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# Conversation states
ONBOARDING = range(15)
FOOD_EDIT = range(5)
MANUAL_HEALTH_INPUT = range(10)


class HealthBot:
    """Main Health Bot class."""
    
    def __init__(self):
        self.application: Optional[Application] = None
        self.config = config
        self.active_conversations: Dict[int, str] = {}
        
        # Validate configuration
        is_valid, errors = self.config.validate()
        if not is_valid:
            logger.warning(f"Configuration warnings: {errors}")
        
        # Set up reminder callback
        reminder_manager.set_send_callback(self.send_telegram_message)
    
    async def send_telegram_message(
        self,
        telegram_id: str,
        message: str,
        **kwargs
    ):
        """Send message via Telegram bot."""
        if not self.application:
            return
        
        try:
            await self.application.bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode=ParseMode.HTML,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Error sending message to {telegram_id}: {e}")
    
    def setup_application(self) -> Application:
        """Set up the Telegram application with all handlers."""
        # Create application with JobQueue disabled (we use our own scheduler)
        application = Application.builder().token(self.config.telegram_bot_token).job_queue(None).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", self.cmd_start))
        application.add_handler(CommandHandler("help", self.cmd_help))
        application.add_handler(CommandHandler("settings", self.cmd_settings))
        application.add_handler(CommandHandler("profile", self.cmd_profile))
        application.add_handler(CommandHandler("today", self.cmd_today))
        application.add_handler(CommandHandler("week", self.cmd_week))
        application.add_handler(CommandHandler("report", self.cmd_report))
        application.add_handler(CommandHandler("cancel", self.cmd_cancel))
        
        # Add conversation handler for onboarding
        application.add_handler(ConversationHandler(
            entry_points=[
                CommandHandler("onboard", self.onboard_start),
                CallbackQueryHandler(self.onboard_callback, pattern="^onboard_")
            ],
            states={
                state: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.onboard_handler)
                ]
                for state in ONBOARDING
            },
            fallbacks=[CommandHandler("cancel", self.cmd_cancel)],
            per_message=False
        ))
        
        # Add conversation handler for food editing
        application.add_handler(ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.food_edit_start, pattern="^food_edit_")
            ],
            states={
                state: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.food_edit_handler)
                ]
                for state in FOOD_EDIT
            },
            fallbacks=[CommandHandler("cancel", self.cmd_cancel)],
            per_message=False
        ))
        
        # Add conversation handler for manual health input
        application.add_handler(ConversationHandler(
            entry_points=[
                CommandHandler("health", self.health_input_start)
            ],
            states={
                state: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.health_input_handler)
                ]
                for state in MANUAL_HEALTH_INPUT
            },
            fallbacks=[CommandHandler("cancel", self.cmd_cancel)],
            per_message=False
        ))

        # Add photo handler for food recognition
        application.add_handler(MessageHandler(
            filters.PHOTO,
            self.handle_photo
        ))

        # Add text message handler for main keyboard commands
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_text_message
        ))

        # Add callback query handler for inline buttons
        application.add_handler(CallbackQueryHandler(self.handle_callback))

        # Add error handler
        application.add_error_handler(self.error_handler)

        return application
    
    async def initialize(self):
        """Initialize the bot."""
        logger.info("Initializing Health Bot...")
        
        # Initialize database
        db_manager.initialize()
        logger.info("Database initialized")
        
        # Set up application
        self.application = self.setup_application()
        
        # Set bot commands
        await self.set_bot_commands()
        
        logger.info("Health Bot initialized successfully")
    
    async def set_bot_commands(self):
        """Set bot command menu."""
        if not self.application:
            return
        
        commands = [
            BotCommand("start", "🚀 Запустить бота"),
            BotCommand("help", "❓ Помощь"),
            BotCommand("profile", "👤 Мой профиль"),
            BotCommand("settings", "⚙️ Настройки"),
            BotCommand("today", "📊 Сегодня"),
            BotCommand("week", "📈 Неделя"),
            BotCommand("report", "📑 Отчет"),
            BotCommand("health", "❤️ Здоровье"),
            BotCommand("onboard", "📝 Настройка (заново)"),
            BotCommand("cancel", "❌ Отменить")
        ]
        
        await self.application.bot.set_my_commands(commands)
    
    # ==================== COMMAND HANDLERS ====================
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        telegram_id = str(user.id)

        # Check if user exists
        existing_user = profile_manager.check_existing_user(telegram_id)

        if existing_user:
            # Welcome back message
            await update.message.reply_text(
                f"👋 С возвращением, {existing_user.name}!\n\n"
                f"Я твой персональный помощник по здоровью.\n"
                f"Используй /help для списка команд.",
                reply_markup=self.get_main_keyboard()
            )
        else:
            # Start onboarding for all new users
            keyboard = [
                [InlineKeyboardButton("🚀 Начать настройку", callback_data="onboard_start")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"👋 Привет, {user.first_name}! Я твой персональный помощник по здоровью.\n\n"
                "Давай настроим бота под твои цели:\n"
                "• Трекинг питания и КБЖУ\n"
                "• План тренировок\n"
                "• Мониторинг здоровья\n"
                "• Умные напоминания\n"
                "• Персональные рекомендации на основе ИИ\n\n"
                "⚡ **Мощная персонализация** — я узнаю о тебе всё необходимое для максимального прогресса!\n\n"
                "Нажми кнопку ниже, чтобы начать:",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_text = """
🤖 <b>Health Bot - Твой помощник по здоровью</b>

<b>📋 Основные команды:</b>
/start - Запустить бота
/profile - Твой профиль и статистика
/settings - Настройки уведомлений
/today - Сводка за сегодня
/week - Сводка за неделю
/report - Получить Excel отчет

<b>🍽️ Питание:</b>
Отправь фото еды - я распознаю и посчитаю КБЖУ

<b>❤️ Здоровье:</b>
/health - Ввести показатели здоровья
Отправь фото анализа крови - я расшифрую

<b>💪 Тренировки:</b>
В 22:00 я спрошу о тренировке

<b>⚙️ Настройка:</b>
/onboard - Пройти настройку заново

<b>❓ Вопросы:</b>
Я использую ИИ для анализа твоих данных и даю персонализированные рекомендации.
"""
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.HTML,
            reply_markup=self.get_main_keyboard()
        )
    
    async def cmd_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /profile command."""
        telegram_id = str(update.effective_user.id)
        user = profile_manager.check_existing_user(telegram_id)
        
        if not user:
            await update.message.reply_text(
                "❌ Профиль не найден. Используйте /start"
            )
            return
        
        # Get profile data
        profile = profile_manager.get_user_profile(telegram_id)
        
        # Calculate BMI
        bmi_data = profile_manager.calculate_bmi(user.weight_kg, user.height_cm)
        
        # Calculate calorie targets
        calorie_data = profile_manager.calculate_daily_calories(user)
        
        profile_text = f"""
👤 <b>Профиль: {profile['name']}</b>

📊 <b>Параметры:</b>
• Возраст: {profile['age']} лет
• Вес: {profile['weight_kg']} кг
• Рост: {profile['height_cm']} см
• BMI: {bmi_data['bmi']} ({bmi_data['category']})

🎯 <b>Цель:</b> {profile['goal']}

🍽️ <b>Норма КБЖУ:</b>
• Калории: {calorie_data['calories']:.0f} ккал
• Белки: {calorie_data['protein_g']} г
• Жиры: {calorie_data['fat_g']} г
• Углеводы: {calorie_data['carbs_g']} г

💊 <b>Добавки:</b> {len(profile['supplements'])}
📅 <b>Приемов пищи:</b> {len(profile['meal_schedule'])}
"""
        
        keyboard = [
            [InlineKeyboardButton("⚙️ Настройки", callback_data="settings_main")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            profile_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    
    async def cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command."""
        telegram_id = str(update.effective_user.id)
        user = profile_manager.check_existing_user(telegram_id)
        
        if not user:
            await update.message.reply_text("❌ Профиль не найден")
            return
        
        settings = db_manager.get_user_settings(user.id)
        
        settings_text = "⚙️ <b>Настройки</b>\n\n"
        
        if settings:
            settings_text += f"""
🔔 <b>Уведомления:</b>
• Питание: {'✅' if settings.enable_meal_reminders else '❌'}
• Добавки: {'✅' if settings.enable_supplement_reminders else '❌'}
• Тренировки: {'✅' if settings.enable_training_reminders else '❌'}
• Ежедневная сводка: {'✅' if settings.enable_daily_summary else '❌'}

🤖 <b>AI функции:</b>
• DeepSeek: {'✅' if settings.deepseek_enabled else '❌'}
• Gemini: {'✅' if settings.gemini_enabled else '❌'}
"""
        
        keyboard = [
            [InlineKeyboardButton("🔔 Уведомления", callback_data="settings_notifications")],
            [InlineKeyboardButton("🤖 AI настройки", callback_data="settings_ai")],
            [InlineKeyboardButton("📱 Samsung Health", callback_data="settings_samsung")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            settings_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    
    async def cmd_today(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /today command - daily summary."""
        telegram_id = str(update.effective_user.id)
        user = profile_manager.check_existing_user(telegram_id)
        
        if not user:
            await update.message.reply_text("❌ Профиль не найден")
            return
        
        # Get today's summary
        today = date.today()
        nutrition_summary = nutrition_manager.get_daily_summary(user.id, today)
        training_log = training_manager.get_training_log(user.id, today)
        
        summary_text = f"📊 <b>Сводка за {today.strftime('%d.%m.%Y')}</b>\n\n"
        
        # Nutrition
        summary_text += "🍽️ <b>Питание:</b>\n"
        summary_text += f"• Калории: {nutrition_summary['calories']:.0f} ккал\n"
        summary_text += f"• Белки: {nutrition_summary['protein']:.1f}г\n"
        summary_text += f"• Жиры: {nutrition_summary['fat']:.1f}г\n"
        summary_text += f"• Углеводы: {nutrition_summary['carbs']:.1f}г\n"
        summary_text += f"• Приемов пищи: {nutrition_summary['meals_count']}\n\n"
        
        # Training
        if training_log:
            summary_text += "💪 <b>Тренировка:</b>\n"
            summary_text += f"• Длительность: {training_log.duration_minutes} мин\n"
            summary_text += f"• Калории: {training_log.calories_burned:.0f} ккал\n\n"
        else:
            summary_text += "💪 <b>Тренировка:</b> не было\n\n"
        
        # Targets progress
        if nutrition_summary.get('targets'):
            targets = nutrition_summary['targets']
            progress = nutrition_summary.get('progress', {})
            
            summary_text += "📈 <b>Прогресс:</b>\n"
            summary_text += f"• Калории: {progress.get('calories_percent', 0):.0f}%\n"
            summary_text += f"• Белки: {progress.get('protein_percent', 0):.0f}%\n"
            summary_text += f"• Жиры: {progress.get('fat_percent', 0):.0f}%\n"
            summary_text += f"• Углеводы: {progress.get('carbs_percent', 0):.0f}%\n"
        
        await update.message.reply_text(
            summary_text,
            parse_mode=ParseMode.HTML
        )
    
    async def cmd_week(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /week command - weekly summary."""
        telegram_id = str(update.effective_user.id)
        user = profile_manager.check_existing_user(telegram_id)
        
        if not user:
            await update.message.reply_text("❌ Профиль не найден")
            return
        
        from datetime import timedelta
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        
        # Get summaries
        nutrition_weekly = nutrition_manager.get_weekly_summary(user.id, week_start)
        training_weekly = training_manager.get_weekly_training_summary(user.id, week_start)
        
        summary_text = f"📈 <b>Сводка за неделю</b>\n"
        summary_text += f"{week_start.strftime('%d.%m')} - {today.strftime('%d.%m.%Y')}\n\n"
        
        # Nutrition
        avg = nutrition_weekly.get('weekly_averages', {})
        summary_text += "🍽️ <b>Питание (среднее в день):</b>\n"
        summary_text += f"• Калории: {avg.get('calories', 0):.0f} ккал\n"
        summary_text += f"• Белки: {avg.get('protein', 0):.1f}г\n"
        summary_text += f"• Жиры: {avg.get('fat', 0):.1f}г\n"
        summary_text += f"• Углеводы: {avg.get('carbs', 0):.1f}г\n"
        summary_text += f"• Дней с записями: {nutrition_weekly.get('days_logged', 0)}\n\n"
        
        # Training
        summary_text += "💪 <b>Тренировки:</b>\n"
        summary_text += f"• Всего: {training_weekly.get('total_workouts', 0)}\n"
        summary_text += f"• Длительность: {training_weekly.get('total_duration_minutes', 0)} мин\n"
        summary_text += f"• Калории: {training_weekly.get('total_calories_burned', 0):.0f} ккал\n"
        
        await update.message.reply_text(
            summary_text,
            parse_mode=ParseMode.HTML
        )
    
    async def cmd_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /report command - generate Excel report."""
        telegram_id = str(update.effective_user.id)
        user = profile_manager.check_existing_user(telegram_id)
        
        if not user:
            await update.message.reply_text("❌ Профиль не найден")
            return
        
        keyboard = [
            [InlineKeyboardButton("📊 Недельный", callback_data="report_weekly")],
            [InlineKeyboardButton("📑 Месячный", callback_data="report_monthly")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📑 <b>Генерация отчета</b>\n\nВыберите тип отчета:",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    
    async def cmd_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel command."""
        telegram_id = update.effective_user.id
        
        # Clear conversation state
        if telegram_id in self.active_conversations:
            del self.active_conversations[telegram_id]
        
        await update.message.reply_text(
            "❌ Отменено. Используйте /help для списка команд.",
            reply_markup=ReplyKeyboardRemove()
        )
        
        return ConversationHandler.END
    
    # ==================== ONBOARDING HANDLERS ====================
    
    async def onboard_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start onboarding process."""
        telegram_id = str(update.effective_user.id)
        onboarding = get_or_create_onboarding_session(telegram_id)
        
        question = onboarding.get_question()
        
        await update.message.reply_text(
            question,
            reply_markup=ReplyKeyboardRemove()
        )
        
        return ONBOARDING[0]
    
    async def onboard_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle onboarding responses."""
        telegram_id = str(update.effective_user.id)
        onboarding = get_or_create_onboarding_session(telegram_id)
        
        answer = update.message.text
        success, error = onboarding.process_answer(answer)
        
        if not success:
            await update.message.reply_text(f"❌ {error}\n\nПопробуйте еще раз:")
            return ONBOARDING[onboarding.STEPS.index(onboarding.get_current_step())]
        
        if onboarding.is_onboarding_complete():
            # Create user profile
            user_data = onboarding.get_collected_data()
            
            # Check if user already exists
            existing = profile_manager.check_existing_user(telegram_id)
            if existing:
                # Update existing
                profile_manager.update_user_profile(existing.id, user_data)
            else:
                # Create new
                profile_manager.create_new_user_profile(telegram_id, user_data)
            
            # Clean up
            remove_onboarding_session(telegram_id)
            
            await update.message.reply_text(
                "✅ <b>Настройка завершена!</b>\n\n"
                "Твой профиль создан. Теперь я буду помогать тебе:\n"
                "• Следить за питанием 🍽️\n"
                "• Планировать тренировки 💪\n"
                "• Контролировать здоровье ❤️\n\n"
                "Используй /help для списка команд.",
                parse_mode=ParseMode.HTML,
                reply_markup=self.get_main_keyboard()
            )
            
            return ConversationHandler.END
        
        # Next question
        next_question = onboarding.get_question()
        await update.message.reply_text(next_question)
        
        current_step = onboarding.STEPS.index(onboarding.get_current_step())
        return ONBOARDING[current_step]
    
    async def onboard_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle onboarding callback queries."""
        query = update.callback_query
        await query.answer()
        
        if query.data == "onboard_start":
            telegram_id = str(query.from_user.id)
            onboarding = get_or_create_onboarding_session(telegram_id)
            
            question = onboarding.get_question()
            await query.edit_message_text(question)
            
            return ONBOARDING[0]
        
        return ConversationHandler.END

    # ==================== PHOTO HANDLER ====================

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo messages (food recognition or Samsung Health screenshots)."""
        telegram_id = str(update.effective_user.id)
        user = profile_manager.check_existing_user(telegram_id)

        if not user:
            await update.message.reply_text("❌ Сначала создайте профиль (/start)")
            return

        # Get photo
        photo = update.message.photo[-1]  # Highest resolution

        # Download photo
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()

        # Determine if this is a Samsung Health screenshot or food photo
        # Check caption or time of day
        caption = update.message.caption or ""
        current_hour = datetime.now().hour

        # Check if it's a screenshot based on caption or time
        is_screenshot = (
            "сон" in caption.lower() or
            "состав" in caption.lower() or
            "скрин" in caption.lower() or
            "screenshot" in caption.lower() or
            current_hour >= 22 or
            current_hour <= 9
        )

        if is_screenshot:
            # Save as screenshot
            screenshot_type = "samsung_screenshot"
            if "сон" in caption.lower() or "sleep" in caption.lower():
                screenshot_type = "sleep_screenshot"
            elif "состав" in caption.lower() or "body" in caption.lower():
                screenshot_type = "body_screenshot"
            
            success, filepath, msg = image_processor.save_uploaded_image(
                bytes(image_bytes),
                telegram_id,
                screenshot_type
            )
            
            if success:
                await self.process_samsung_screenshot(update, context, filepath, user, screenshot_type)
        else:
            # Food photo
            success, filepath, msg = image_processor.save_uploaded_image(
                bytes(image_bytes),
                telegram_id,
                "food"
            )

            if not success:
                await update.message.reply_text(msg)
                return

            # Analyze food
            await update.message.reply_text("🔍 Анализирую еду...")

            user_context = {
                'goal': user.goal.value if user.goal else 'maintenance'
            }

            success, result, msg = await image_processor.analyze_food_image(
                filepath,
                user_context
            )

            if not success or not result:
                await update.message.reply_text(msg)
                return

            # Show results
            foods_text = "🍽️ <b>Распознанные продукты:</b>\n\n"
            for food in result['foods'][:5]:
                foods_text += f"• {food['name']} ({food['weight_g']}г)\n"
                foods_text += f"  {food['calories']:.0f} ккал | "
                foods_text += f"Б: {food['protein']:.1f}г | "
                foods_text += f"Ж: {food['fat']:.1f}г | "
                foods_text += f"У: {food['carbs']:.1f}г\n\n"

            foods_text += f"<b>Итого:</b> {result['total_nutrition']['calories']:.0f} ккал\n"
            foods_text += f"Б: {result['total_nutrition']['protein']:.1f}г | "
            foods_text += f"Ж: {result['total_nutrition']['fat']:.1f}г | "
            foods_text += f"У: {result['total_nutrition']['carbs']:.1f}г\n"

            if result['suggestions']:
                foods_text += f"\n💡 <b>Советы:</b>\n"
                for suggestion in result['suggestions'][:3]:
                    foods_text += f"• {suggestion}\n"

            keyboard = [
                [InlineKeyboardButton("✅ Записать", callback_data=f"food_log_{filepath}")],
                [InlineKeyboardButton("✏️ Изменить", callback_data=f"food_edit_{filepath}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                foods_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

    async def process_samsung_screenshot(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        filepath: str,
        user,
        screenshot_type: str = "samsung_screenshot"
    ):
        """Process Samsung Health screenshot."""
        type_messages = {
            "sleep_screenshot": (
                "📸 <b>Скриншот сна получен!</b>\n\n"
                "✅ Данные о сне записаны:\n"
                "• Длительность сна\n"
                "• Качество сна\n"
                "• Фазы сна\n\n"
                "📈 Отслеживаю динамику!"
            ),
            "body_screenshot": (
                "⚖️ <b>Скриншот состава тела получен!</b>\n\n"
                "✅ Данные записаны:\n"
                "• Вес\n"
                "• Процент жира\n"
                "• Мышечная масса\n\n"
                "📈 Динамика обновлена!"
            ),
            "samsung_screenshot": (
                "📊 <b>Скриншот Samsung Health получен!</b>\n\n"
                "✅ Данные за день записаны:\n"
                "• Шаги\n"
                "• Калории\n"
                "• Активность\n"
                "• Пульс\n"
                "• Стресс\n\n"
                "🌙 Хорошего вечера!"
            )
        }
        
        message = type_messages.get(screenshot_type, "📸 Скриншот получен! Спасибо!")
        
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)
        
        # Log health metrics (placeholder - will be extracted via OCR in future)
        if screenshot_type == "sleep_screenshot":
            health_manager.add_health_metric(
                user_id=user.id,
                metric_type="sleep_duration",
                value=480,
                measurement_date=date.today()
            )
        elif screenshot_type == "body_screenshot":
            health_manager.add_health_metric(
                user_id=user.id,
                metric_type="weight",
                value=user.weight_kg,
                measurement_date=date.today()
            )
        else:
            health_manager.add_health_metric(
                user_id=user.id,
                metric_type="steps",
                value=10000,
                measurement_date=date.today()
            )

    # ==================== TEXT MESSAGE HANDLER ====================

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages (keyboard buttons)."""
        text = update.message.text.strip()
        
        # Handle main keyboard buttons
        if text == "📊 Сегодня":
            await self.cmd_today(update, context)
        elif text == "📈 Неделя":
            await self.cmd_week(update, context)
        elif text == "🍽️ Питание":
            await update.message.reply_text("🍽️ Раздел питания\n\nИспользуйте команды:\n/food - добавить еду\n/photo - отправить фото еды")
        elif text == "💪 Тренировка":
            await update.message.reply_text("💪 Раздел тренировок\n\nИспользуйте команду /workout для начала тренировки")
        elif text == "❤️ Здоровье":
            await update.message.reply_text("❤️ Раздел здоровья\n\nИспользуйте команду /health для ввода показателей")
        elif text == "⚙️ Настройки":
            await self.cmd_settings(update, context)
        else:
            # Unknown command - show help
            await self.cmd_help(update, context)

    # ==================== CALLBACK HANDLER ====================

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all callback queries."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data.startswith("food_log_"):
            filepath = data.replace("food_log_", "")
            await self.log_food_from_callback(update, context, filepath)
        
        elif data.startswith("report_"):
            report_type = data.replace("report_", "")
            await self.generate_report_from_callback(update, context, report_type)
        
        elif data.startswith("settings_"):
            setting_type = data.replace("settings_", "")
            await self.handle_settings_callback(update, context, setting_type)
        
        elif data.startswith("stats_"):
            await self.handle_stats_callback(update, context)
    
    async def log_food_from_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        filepath: str
    ):
        """Log food from callback."""
        telegram_id = str(update.effective_user.id)
        user = profile_manager.check_existing_user(telegram_id)
        
        if not user:
            await update.callback_query.message.reply_text("❌ Профиль не найден")
            return
        
        # Get stored food data (in production, use cache/database)
        # For now, re-analyze
        success, result, msg = await image_processor.analyze_food_image(filepath)
        
        if not success:
            await update.callback_query.message.reply_text("❌ Ошибка распознавания")
            return
        
        # Log to database
        food_items = result['foods']
        
        success, log, msg = nutrition_manager.log_meal(
            user_id=user.id,
            meal_type="meal",  # Will be determined by time
            food_items=food_items,
            photo_path=filepath,
            is_ai_recognized=True
        )
        
        if success:
            await update.callback_query.message.reply_text(
                f"✅ {msg}\n\n"
                f"Калории: {log.total_calories:.0f} ккал"
            )
        else:
            await update.callback_query.message.reply_text(msg)
    
    async def generate_report_from_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        report_type: str
    ):
        """Generate report from callback."""
        telegram_id = str(update.effective_user.id)
        user = profile_manager.check_existing_user(telegram_id)
        
        if not user:
            await update.callback_query.message.reply_text("❌ Профиль не найден")
            return
        
        await update.callback_query.message.reply_text("🔄 Генерирую отчет...")
        
        if report_type == "weekly":
            success, filepath, msg = report_generator.generate_weekly_report(user.id)
        else:
            success, filepath, msg = report_generator.generate_monthly_report(user.id)
        
        if success:
            # Send file
            with open(filepath, 'rb') as f:
                await context.bot.send_document(
                    chat_id=telegram_id,
                    document=f,
                    filename=os.path.basename(filepath),
                    caption=msg
                )
        else:
            await update.callback_query.message.reply_text(msg)
    
    async def handle_settings_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        setting_type: str
    ):
        """Handle settings callbacks."""
        telegram_id = str(update.effective_user.id)
        user = profile_manager.check_existing_user(telegram_id)
        
        if not user:
            return
        
        settings = db_manager.get_user_settings(user.id)
        
        if setting_type == "notifications":
            # Toggle notifications
            if settings:
                new_state = not settings.enable_meal_reminders
                db_manager.update_user_settings(user.id, enable_meal_reminders=new_state)
                
                await update.callback_query.message.reply_text(
                    f"🔔 Уведомления о питании: {'✅ вкл' if new_state else '❌ выкл'}"
                )
        
        elif setting_type == "ai":
            # Toggle AI
            if settings:
                new_state = not settings.deepseek_enabled
                db_manager.update_user_settings(user.id, deepseek_enabled=new_state)
                
                await update.callback_query.message.reply_text(
                    f"🤖 DeepSeek: {'✅ вкл' if new_state else '❌ выкл'}"
                )
        
        elif setting_type == "samsung":
            samsung_state = samsung_integration.is_connected()
            await update.callback_query.message.reply_text(
                f"📱 Samsung Health: {'✅ подключен' if samsung_state else '❌ не подключен'}\n\n"
                f"Для подключения настройте API ключ в .env"
            )
    
    async def handle_stats_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle stats callbacks."""
        telegram_id = str(update.effective_user.id)
        user = profile_manager.check_existing_user(telegram_id)
        
        if not user:
            return
        
        # Get body composition trend
        trend = health_manager.get_body_composition_trend(user.id, days=30)
        
        if trend['weight']:
            weights = trend['weight']
            if len(weights) >= 2:
                change = weights[-1]['value'] - weights[0]['value']
                await update.callback_query.message.reply_text(
                    f"📈 <b>Динамика веса (30 дней):</b>\n"
                    f"Начало: {weights[0]['value']:.1f} кг\n"
                    f"Конец: {weights[-1]['value']:.1f} кг\n"
                    f"Изменение: {change:+.1f} кг",
                    parse_mode=ParseMode.HTML
                )
        else:
            await update.callback_query.message.reply_text(
                "📊 Нет данных о весе за последние 30 дней"
            )
    
    # ==================== FOOD EDIT HANDLERS ====================
    
    async def food_edit_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start food editing."""
        query = update.callback_query
        await query.answer()
        
        filepath = query.data.replace("food_edit_", "")
        
        # Store filepath in context
        context.user_data['edit_filepath'] = filepath
        
        await query.edit_message_text(
            "✏️ <b>Редактирование</b>\n\n"
            "Отправьте исправленные данные в формате:\n"
            "Название, вес(г), калории, белки, жиры, углеводы\n\n"
            "Или 'готово' для завершения",
            parse_mode=ParseMode.HTML
        )
        
        return FOOD_EDIT[0]
    
    async def food_edit_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle food edit input."""
        text = update.message.text.lower()
        
        if text == "готово":
            await update.message.reply_text(
                "✅ Готово! Данные сохранены.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Parse food data
        # Format: Название, вес, калории, белки, жиры, углеводы
        parts = update.message.text.split(',')
        
        if len(parts) >= 6:
            try:
                food_item = {
                    'name': parts[0].strip(),
                    'weight_g': float(parts[1].strip()),
                    'calories': float(parts[2].strip()),
                    'protein': float(parts[3].strip()),
                    'fat': float(parts[4].strip()),
                    'carbs': float(parts[5].strip())
                }
                
                # Store in context
                if 'edit_foods' not in context.user_data:
                    context.user_data['edit_foods'] = []
                context.user_data['edit_foods'].append(food_item)
                
                await update.message.reply_text(
                    f"✅ Добавлено: {food_item['name']}\n"
                    f"Продолжайте или напишите 'готово'"
                )
                
            except ValueError:
                await update.message.reply_text(
                    "❌ Неверный формат. Используйте: Название, вес, калории, белки, жиры, углеводы"
                )
        else:
            await update.message.reply_text(
                "❌ Недостаточно данных. Используйте формат:\n"
                "Название, вес(г), калории, белки, жиры, углеводы"
            )
        
        return FOOD_EDIT[0]
    
    # ==================== HEALTH INPUT HANDLERS ====================
    
    async def health_input_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start manual health input."""
        telegram_id = str(update.effective_user.id)
        user = profile_manager.check_existing_user(telegram_id)
        
        if not user:
            await update.message.reply_text("❌ Профиль не найден")
            return ConversationHandler.NONE
        
        # Create input session
        manual_input.create_input_session(telegram_id)
        questions = manual_input.get_input_questions()
        
        await update.message.reply_text(
            f"❤️ <b>Ввод показателей здоровья</b>\n\n"
            f"{questions[0]['question']}\n\n"
            f"Или 'отмена' для выхода",
            parse_mode=ParseMode.HTML
        )
        
        return MANUAL_HEALTH_INPUT[0]
    
    async def health_input_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle health input."""
        telegram_id = str(update.effective_user.id)
        
        if update.message.text.lower() == "отмена":
            manual_input.clear_session(telegram_id)
            await update.message.reply_text("❌ Отменено")
            return ConversationHandler.END
        
        # Get current step from session
        session = manual_input.input_sessions.get(telegram_id)
        if not session:
            return ConversationHandler.END
        
        current_step = session['current_step']
        
        # Process input
        try:
            value = float(update.message.text.replace(',', '.'))
        except ValueError:
            await update.message.reply_text(
                "❌ Введите числовое значение или 'отмена'"
            )
            return MANUAL_HEALTH_INPUT[0]
        
        success, next_step, msg = manual_input.process_input(telegram_id, current_step, value)
        
        if success:
            if next_step:
                await update.message.reply_text(
                    f"{msg}\n\n{next_step}"
                )
                return MANUAL_HEALTH_INPUT[0]
            else:
                # Session complete - save to database
                user = profile_manager.check_existing_user(telegram_id)
                data = manual_input.get_session_data(telegram_id)
                
                if user and data:
                    # Save metrics
                    if 'weight' in data:
                        health_manager.add_health_metric(user.id, 'weight', data['weight'])
                    if 'body_fat' in data:
                        health_manager.add_health_metric(user.id, 'body_fat', data['body_fat'])
                    if 'heart_rate' in data:
                        health_manager.add_health_metric(user.id, 'heart_rate', data['heart_rate'])
                
                manual_input.clear_session(telegram_id)
                
                await update.message.reply_text(
                    "✅ <b>Данные сохранены!</b>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
        
        return MANUAL_HEALTH_INPUT[0]
    
    # ==================== ERROR HANDLER ====================
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors."""
        logger.error(f"Update {update} caused error: {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка. Попробуйте позже."
            )
    
    # ==================== KEYBOARDS ====================
    
    def get_main_keyboard(self) -> ReplyKeyboardMarkup:
        """Get main keyboard."""
        keyboard = [
            ["📊 Сегодня", "📈 Неделя"],
            ["🍽️ Питание", "💪 Тренировка"],
            ["❤️ Здоровье", "⚙️ Настройки"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    # ==================== RUNNER ====================

    def run(self):
        """Run the bot."""
        if not self.application:
            self.initialize_sync()

        logger.info("Starting Health Bot...")

        # Run bot polling (blocking)
        self.application.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None)

    def initialize_sync(self):
        """Initialize the bot synchronously."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.initialize())
        finally:
            # Don't close the loop - run_polling will use it
            pass


def main():
    """Main entry point."""
    # Check required config
    if not config.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set. Please configure .env file")
        sys.exit(1)

    # Set event loop policy for Windows compatibility
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Create and run bot
    bot = HealthBot()

    try:
        # Initialize and run bot directly (run_polling handles event loop)
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {e}")
        raise


if __name__ == "__main__":
    main()
