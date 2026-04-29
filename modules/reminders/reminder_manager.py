"""
Reminders and notifications module for Health Bot.
Handles scheduling and sending reminders for meals, supplements, training, and more.
"""

from typing import Dict, List, Any, Optional, Tuple, Callable
from datetime import datetime, date, time, timedelta
import logging
import asyncio

from database.manager import db_manager
from database.models import User, Supplement, MealSchedule, ScheduleItem, ReminderLog
from config import config

logger = logging.getLogger(__name__)


class ReminderType:
    """Reminder type constants."""
    MEAL = "meal"
    SUPPLEMENT = "supplement"
    TRAINING = "training"
    BODY_COMPOSITION = "body_composition"
    DAILY_SUMMARY = "daily_summary"
    WATER = "water"
    SLEEP = "sleep"
    SCREENSHOT_MORNING = "screenshot_morning"  # Morning Samsung Health screenshot
    SCREENSHOT_EVENING = "screenshot_evening"  # Evening Samsung Health screenshot
    SCREENSHOT_WEEKLY = "screenshot_weekly"    # Weekly body composition screenshot


class Reminder:
    """Reminder data class."""
    
    def __init__(
        self,
        user_id: int,
        telegram_id: str,
        reminder_type: str,
        scheduled_time: datetime,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ):
        self.user_id = user_id
        self.telegram_id = telegram_id
        self.reminder_type = reminder_type
        self.scheduled_time = scheduled_time
        self.message = message
        self.data = data or {}
        self.is_sent = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "telegram_id": self.telegram_id,
            "reminder_type": self.reminder_type,
            "scheduled_time": self.scheduled_time.isoformat(),
            "message": self.message,
            "data": self.data,
            "is_sent": self.is_sent
        }


class ReminderManager:
    """Manager for reminders and notifications."""
    
    def __init__(self):
        self.db = db_manager
        self.send_callback: Optional[Callable] = None  # Callback to send Telegram message
        self._pending_reminders: List[Reminder] = []
    
    def set_send_callback(self, callback: Callable):
        """Set callback function for sending messages."""
        self.send_callback = callback
    
    async def send_message(self, telegram_id: str, message: str, **kwargs):
        """Send message via callback."""
        if self.send_callback:
            try:
                await self.send_callback(telegram_id, message, **kwargs)
            except Exception as e:
                logger.error(f"Error sending message: {e}")
    
    def get_meal_reminders_for_day(
        self,
        user_id: int,
        target_date: date = None
    ) -> List[Reminder]:
        """
        Get meal reminders for a specific day.
        
        Args:
            user_id: User internal ID
            target_date: Date to get reminders for
        
        Returns:
            List of Reminder objects
        """
        if target_date is None:
            target_date = date.today()
        
        user = self.db.get_user_by_id(user_id)
        if not user:
            return []
        
        reminders = []
        meal_schedules = self.db.get_user_meal_schedule(user_id)
        
        for meal_schedule in meal_schedules:
            if not meal_schedule.is_active:
                continue
            
            # Parse meal time
            try:
                meal_time = datetime.strptime(meal_schedule.time, "%H:%M").time()
            except ValueError:
                continue
            
            # Calculate reminder time
            reminder_time = datetime.combine(
                target_date,
                time(
                    (meal_time.hour * 60 + meal_time.minute - meal_schedule.reminder_offset_minutes) // 60 % 24,
                    (meal_time.hour * 60 + meal_time.minute - meal_schedule.reminder_offset_minutes) % 60
                )
            )
            
            # Skip if already passed
            if reminder_time < datetime.now():
                continue
            
            # Get meal name in Russian
            meal_names = {
                "breakfast": "Завтрак",
                "lunch": "Обед",
                "second_lunch": "Второй обед",
                "snack": "Перекус",
                "dinner": "Ужин"
            }
            meal_name = meal_names.get(meal_schedule.meal_type, meal_schedule.meal_type)
            
            # Build message
            message = f"🍽️ {meal_name} через {meal_schedule.reminder_offset_minutes} минут!\n\n"
            message += f"Время: {meal_time.strftime('%H:%M')}\n\n"
            
            # Add recommendation based on remaining calories
            daily_summary = self._get_nutrition_manager().get_daily_summary(user_id, target_date)
            if daily_summary.get('remaining'):
                remaining = daily_summary['remaining']
                if remaining['calories'] > 0:
                    message += f"📊 Осталось калорий сегодня: {int(remaining['calories'])}\n"
                    message += f"   Белки: {remaining['protein']:.0f}г | Жиры: {remaining['fat']:.0f}г | Углеводы: {remaining['carbs']:.0f}г"
            
            reminder = Reminder(
                user_id=user_id,
                telegram_id=user.telegram_id,
                reminder_type=ReminderType.MEAL,
                scheduled_time=reminder_time,
                message=message,
                data={
                    "meal_type": meal_schedule.meal_type,
                    "meal_time": meal_schedule.time
                }
            )
            reminders.append(reminder)
        
        return reminders
    
    def get_supplement_reminders_for_day(
        self,
        user_id: int,
        target_date: date = None
    ) -> List[Reminder]:
        """Get supplement reminders for a specific day."""
        if target_date is None:
            target_date = date.today()
        
        user = self.db.get_user_by_id(user_id)
        if not user:
            return []
        
        reminders = []
        supplements = self.db.get_user_supplements(user_id)
        
        for supplement in supplements:
            if not supplement.is_active or not supplement.reminder_time:
                continue
            
            # Parse reminder time
            try:
                reminder_time = datetime.strptime(supplement.reminder_time, "%H:%M")
                reminder_time = reminder_time.replace(
                    year=target_date.year,
                    month=target_date.month,
                    day=target_date.day
                )
            except ValueError:
                continue
            
            # Skip if already passed
            if reminder_time < datetime.now():
                continue
            
            # Build message
            message = f"💊 Пора принять: {supplement.name}\n"
            if supplement.dosage:
                message += f"Дозировка: {supplement.dosage}\n"
            message += "\nНе забудь запить водой! 💧"
            
            reminder = Reminder(
                user_id=user_id,
                telegram_id=user.telegram_id,
                reminder_type=ReminderType.SUPPLEMENT,
                scheduled_time=reminder_time,
                message=message,
                data={
                    "supplement_id": supplement.id,
                    "supplement_name": supplement.name
                }
            )
            reminders.append(reminder)
        
        return reminders
    
    def get_training_reminders_for_day(
        self,
        user_id: int,
        target_date: date = None
    ) -> List[Reminder]:
        """Get training reminders for a specific day."""
        if target_date is None:
            target_date = date.today()
        
        user = self.db.get_user_by_id(user_id)
        if not user:
            return []
        
        reminders = []
        
        # Get day of week
        day_map = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        day_of_week = day_map[target_date.weekday()]
        
        # Get training schedule
        schedule = self.db.get_user_schedule(user_id)
        
        for item in schedule:
            if item.item_type != 'training' or not item.is_active:
                continue
            
            if day_of_week not in (item.days_of_week or []):
                continue
            
            # Parse training time
            if not item.start_time:
                continue
            
            try:
                training_time = datetime.strptime(item.start_time, "%H:%M").time()
            except ValueError:
                continue
            
            # Calculate reminder time (30 minutes before)
            reminder_minutes = 30
            reminder_time = datetime.combine(
                target_date,
                time(
                    (training_time.hour * 60 + training_time.minute - reminder_minutes) // 60 % 24,
                    (training_time.hour * 60 + training_time.minute - reminder_minutes) % 60
                )
            )
            
            # Skip if already passed
            if reminder_time < datetime.now():
                continue
            
            # Check if already trained today
            if self._get_training_manager().has_trained_today(user_id):
                continue
            
            # Build message
            message = f"💪 Тренировка через {reminder_minutes} минут!\n\n"
            message += f"Время: {training_time.strftime('%H:%M')}\n\n"
            message += "Не забудь:\n"
            message += "• Взять воду 💧\n"
            message += "• Подготовить форму 👟\n"
            message += "• Сделать разминку 🏃\n\n"
            message += "Удачи на тренировке! 🏋️"
            
            reminder = Reminder(
                user_id=user_id,
                telegram_id=user.telegram_id,
                reminder_type=ReminderType.TRAINING,
                scheduled_time=reminder_time,
                message=message,
                data={
                    "training_time": item.start_time
                }
            )
            reminders.append(reminder)
        
        return reminders
    
    def get_body_composition_reminder(
        self,
        user_id: int,
        target_date: date = None
    ) -> Optional[Reminder]:
        """Get body composition measurement reminder (weekly)."""
        if target_date is None:
            target_date = date.today()
        
        # Only remind on Mondays
        if target_date.weekday() != 0:
            return None
        
        user = self.db.get_user_by_id(user_id)
        if not user:
            return None
        
        # Set reminder for 8:00 AM
        reminder_time = datetime.combine(target_date, time(8, 0))
        
        if reminder_time < datetime.now():
            return None
        
        message = (
            "⚖️ Сегодня день замера состава тела!\n\n"
            "Что нужно сделать:\n"
            "1. Взвеситься утром натощак 🍽️\n"
            "2. Измерить процент жира 📊\n"
            "3. Записать данные в бот 📝\n\n"
            "Это поможет отслеживать прогресс!"
        )
        
        return Reminder(
            user_id=user_id,
            telegram_id=user.telegram_id,
            reminder_type=ReminderType.BODY_COMPOSITION,
            scheduled_time=reminder_time,
            message=message,
            data={}
        )
    
    def get_daily_summary_reminder(
        self,
        user_id: int,
        target_date: date = None
    ) -> Optional[Reminder]:
        """Get daily summary reminder (evening)."""
        if target_date is None:
            target_date = date.today()
        
        user = self.db.get_user_by_id(user_id)
        if not user:
            return None
        
        # Get user settings for summary time
        settings = self.db.get_user_settings(user_id)
        summary_time_str = settings.daily_summary_time if settings else "22:00"
        
        try:
            summary_time = datetime.strptime(summary_time_str, "%H:%M").time()
            reminder_time = datetime.combine(target_date, summary_time)
        except ValueError:
            return None
        
        if reminder_time < datetime.now():
            return None
        
        # Build summary message
        daily_summary = self._get_nutrition_manager().get_daily_summary(user_id, target_date)
        
        message = "📊 Ежедневная сводка\n\n"
        message += f"📅 {target_date.strftime('%d.%m.%Y')}\n\n"
        
        # Nutrition
        message += "🍽️ Питание:\n"
        message += f"   Калории: {daily_summary['calories']:.0f} ккал\n"
        message += f"   Белки: {daily_summary['protein']:.1f}г\n"
        message += f"   Жиры: {daily_summary['fat']:.1f}г\n"
        message += f"   Углеводы: {daily_summary['carbs']:.1f}г\n"
        message += f"   Прием пищи: {daily_summary['meals_count']}\n\n"
        
        # Training
        training_log = self._get_training_manager().get_training_log(user_id, target_date)
        if training_log:
            message += "💪 Тренировка:\n"
            message += f"   Длительность: {training_log.duration_minutes} мин\n"
            message += f"   Калории: {training_log.calories_burned:.0f} ккал\n\n"
        
        # Health
        latest_metrics = self._get_health_manager().get_latest_metrics(user_id)
        if latest_metrics and latest_metrics.get('weight_kg'):
            message += f"⚖️ Вес: {latest_metrics['weight_kg']:.1f} кг\n"
        
        message += "\n🌙 Хорошего вечера!"
        
        return Reminder(
            user_id=user_id,
            telegram_id=user.telegram_id,
            reminder_type=ReminderType.DAILY_SUMMARY,
            scheduled_time=reminder_time,
            message=message,
            data={}
        )
    
    def _get_nutrition_manager(self):
        """Get NutritionManager instance."""
        from modules.nutrition import nutrition_manager
        return nutrition_manager
    
    def _get_training_manager(self):
        """Get TrainingManager instance."""
        from modules.training import training_manager
        return training_manager
    
    def _get_health_manager(self):
        """Get HealthManager instance."""
        from modules.health import health_manager
        return health_manager

    def get_screenshot_morning_reminder(
        self,
        user_id: int,
        target_date: date = None
    ) -> Optional[Reminder]:
        """
        Get morning screenshot reminder (08:45-08:50).
        Request: Sleep data from previous night.
        """
        if target_date is None:
            target_date = date.today()

        user = self.db.get_user_by_id(user_id)
        if not user:
            return None

        # Set reminder for 08:45
        reminder_time = datetime.combine(target_date, time(8, 45))

        if reminder_time < datetime.now():
            return None

        message = f"""
☀️ <b>Доброе утро, {user.name}!</b>

📸 <b>Скриншот из Samsung Health</b>

Пожалуйста, отправь скриншот с данными о сне за прошлую ночь.

📱 <b>Что должно быть видно:</b>
• Длительность сна
• Время засыпания и пробуждения
• Фазы сна (глубокий/легкий/REM)
• Оценка качества

🕐 <b>Время:</b> 08:45 - 08:50

Просто отправь скриншот в этот чат 📸
"""

        return Reminder(
            user_id=user_id,
            telegram_id=user.telegram_id,
            reminder_type=ReminderType.SCREENSHOT_MORNING,
            scheduled_time=reminder_time,
            message=message,
            data={"screenshot_type": "sleep"}
        )

    def get_screenshot_evening_reminder(
        self,
        user_id: int,
        target_date: date = None
    ) -> Optional[Reminder]:
        """
        Get evening screenshot reminder (22:00-22:30).
        Request: Full day summary from Samsung Health.
        """
        if target_date is None:
            target_date = date.today()

        user = self.db.get_user_by_id(user_id)
        if not user:
            return None

        # Set reminder for 22:00
        reminder_time = datetime.combine(target_date, time(22, 0))

        if reminder_time < datetime.now():
            return None

        message = f"""
🌙 <b>Вечерняя сводка, {user.name}!</b>

📸 <b>Скриншот из Samsung Health</b>

Пожалуйста, отправь скриншот с полными данными за сегодня.

📱 <b>Что должно быть видно:</b>
• Шаги (всего за день)
• Калории (активные/всего)
• Активные минуты
• Пульс (средний/мин/макс)
• Стресс (средний)
• SpO2 (если есть)
• Вес (если измерялся)

🕐 <b>Время:</b> 22:00 - 22:30

📸 Отправь 1-2 скриншота в этот чат
"""

        return Reminder(
            user_id=user_id,
            telegram_id=user.telegram_id,
            reminder_type=ReminderType.SCREENSHOT_EVENING,
            scheduled_time=reminder_time,
            message=message,
            data={"screenshot_type": "full"}
        )

    def get_screenshot_weekly_reminder(
        self,
        user_id: int,
        target_date: date = None
    ) -> Optional[Reminder]:
        """
        Get weekly body composition reminder (Sunday 12:00).
        Request: Body composition data.
        """
        if target_date is None:
            target_date = date.today()

        # Only on Sundays
        if target_date.weekday() != 6:  # 6 = Sunday
            return None

        user = self.db.get_user_by_id(user_id)
        if not user:
            return None

        # Set reminder for 12:00
        reminder_time = datetime.combine(target_date, time(12, 0))

        if reminder_time < datetime.now():
            return None

        message = f"""
⚖️ <b>Еженедельный замер, {user.name}!</b>

📸 <b>Скриншот состава тела из Samsung Health</b>

Сегодня воскресенье - день замера состава тела!

📱 <b>Что должно быть видно:</b>
• Вес (кг)
• Процент жира (%)
• Мышечная масса (кг)
• Вода (%)
• ИМТ (BMI)
• Висцеральный жир
• Костная масса
• Белок

🕐 <b>Время:</b> 12:00

📸 Отправь скриншот из раздела "Состав тела"
"""

        return Reminder(
            user_id=user_id,
            telegram_id=user.telegram_id,
            reminder_type=ReminderType.SCREENSHOT_WEEKLY,
            scheduled_time=reminder_time,
            message=message,
            data={"screenshot_type": "body"}
        )

    def get_all_reminders_for_day(
        self,
        user_id: int,
        target_date: date = None
    ) -> List[Reminder]:
        """Get all reminders for a specific day."""
        if target_date is None:
            target_date = date.today()
        
        reminders = []
        
        # Get user settings
        user = self.db.get_user_by_id(user_id)
        if not user:
            return reminders
        
        settings = self.db.get_user_settings(user_id)
        
        # Meal reminders
        if not settings or settings.enable_meal_reminders:
            reminders.extend(self.get_meal_reminders_for_day(user_id, target_date))

        # Supplement reminders
        if not settings or settings.enable_supplement_reminders:
            reminders.extend(self.get_supplement_reminders_for_day(user_id, target_date))

        # Training reminders
        if not settings or settings.enable_training_reminders:
            reminders.extend(self.get_training_reminders_for_day(user_id, target_date))

        # Body composition reminder (weekly - Sunday 12:00)
        reminders.append(self.get_body_composition_reminder(user_id, target_date))

        # Screenshot reminders
        reminders.append(self.get_screenshot_morning_reminder(user_id, target_date))
        reminders.append(self.get_screenshot_evening_reminder(user_id, target_date))
        
        # Weekly body screenshot (Sunday)
        if target_date.weekday() == 6:  # Sunday
            reminders.append(self.get_screenshot_weekly_reminder(user_id, target_date))

        # Daily summary reminder
        if not settings or settings.enable_daily_summary:
            reminders.append(self.get_daily_summary_reminder(user_id, target_date))
        
        # Filter out None values and sort by time
        reminders = [r for r in reminders if r is not None]
        reminders.sort(key=lambda r: r.scheduled_time)
        
        return reminders
    
    def log_reminder_sent(self, reminder: Reminder) -> ReminderLog:
        """Log that a reminder was sent."""
        return self.db.log_reminder(
            user_id=reminder.user_id,
            reminder_type=reminder.reminder_type,
            scheduled_time=reminder.scheduled_time,
            message_text=reminder.message,
            is_sent=True
        )
    
    async def process_due_reminders(self, reminders: List[Reminder]):
        """
        Process and send due reminders.
        
        Args:
            reminders: List of reminders to process
        """
        now = datetime.now()
        
        for reminder in reminders:
            if reminder.is_sent:
                continue
            
            # Check if reminder is due (within 1 minute window)
            time_diff = (reminder.scheduled_time - now).total_seconds()
            if -60 <= time_diff <= 60:
                try:
                    # Send message
                    await self.send_message(
                        reminder.telegram_id,
                        reminder.message,
                        data=reminder.data
                    )
                    
                    # Mark as sent
                    reminder.is_sent = True
                    
                    # Log
                    self.log_reminder_sent(reminder)
                    
                    logger.info(
                        f"Sent {reminder.reminder_type} reminder to user {reminder.user_id}"
                    )
                    
                except Exception as e:
                    logger.error(f"Error sending reminder: {e}")
    
    def start_reminder_scheduler(self, check_interval: int = 60):
        """
        Start background reminder scheduler.
        
        Args:
            check_interval: How often to check for due reminders (seconds)
        """
        async def scheduler_loop():
            while True:
                try:
                    # Get all users
                    users = self.db.get_all_users()
                    
                    for user in users:
                        # Get reminders for today and tomorrow
                        for target_date in [date.today(), date.today() + timedelta(days=1)]:
                            reminders = self.get_all_reminders_for_day(user.id, target_date)
                            await self.process_due_reminders(reminders)
                    
                except Exception as e:
                    logger.error(f"Error in reminder scheduler: {e}")
                
                await asyncio.sleep(check_interval)
        
        return scheduler_loop


# Global instance
reminder_manager = ReminderManager()
