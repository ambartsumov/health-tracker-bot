"""
Database manager for Health Bot.
Handles database initialization, sessions, and CRUD operations.
"""

from contextlib import contextmanager
from typing import Optional, Generator
from sqlalchemy.orm import Session
from sqlalchemy import inspect

from config import config
from database.models import (
    Base, get_engine, get_session_factory, init_db,
    User, Supplement, ScheduleItem, MealSchedule, NutritionLog,
    DailyCalorieTarget, TrainingLog, HealthMetric, BloodTest,
    UserSettings, ReminderLog, ExcelReport, GoalType,
    SymptomLog, WaterIntake, PersonalRecord, Achievement, DeloadSchedule
)
from datetime import date, datetime, time


class DatabaseManager:
    """Database manager for Health Bot."""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or config.database_url
        self.engine = get_engine(self.database_url)
        self.SessionLocal = get_session_factory(self.engine)
    
    def initialize(self):
        """Initialize database tables."""
        init_db(self.engine)
    
    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()
    
    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    # User operations
    def get_user_by_telegram_id(self, telegram_id: str) -> Optional[User]:
        """Get user by Telegram ID."""
        with self.session_scope() as session:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                # Force load all attributes before session closes
                _ = user.id, user.name, user.telegram_id, user.goal, user.weight_kg, user.height_cm
                session.expunge(user)
            return user
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by internal ID."""
        with self.session_scope() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if user:
                # Force load all attributes before session closes
                _ = user.id, user.name, user.telegram_id, user.goal, user.weight_kg, user.height_cm
                session.expunge(user)
            return user
    
    def create_user(self, telegram_id: str, name: str, date_of_birth: date, 
                    weight_kg: float = 0.0, height_cm: float = 0.0,
                    goal: GoalType = GoalType.AESTHETIC_AND_HEALTH,
                    is_default_user: bool = False) -> User:
        """Create a new user."""
        with self.session_scope() as session:
            user = User(
                telegram_id=telegram_id,
                name=name,
                date_of_birth=date_of_birth,
                weight_kg=weight_kg,
                height_cm=height_cm,
                goal=goal,
                is_default_user=is_default_user
            )
            session.add(user)
            session.flush()
            
            # Create default settings
            settings = UserSettings(user_id=user.id)
            session.add(settings)
            
            # Force load all attributes before session closes
            _ = user.id, user.name, user.telegram_id, user.goal, user.weight_kg, user.height_cm
            session.expunge(user)
            
            return user
    
    def update_user(self, user_id: int, **kwargs) -> Optional[User]:
        """Update user data."""
        with self.session_scope() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if user:
                for key, value in kwargs.items():
                    if hasattr(user, key):
                        setattr(user, key, value)
                user.updated_at = datetime.utcnow()
                # Force load all attributes before session closes
                _ = user.id, user.name, user.telegram_id, user.goal, user.weight_kg, user.height_cm
                session.expunge(user)
                return user
            return None
    
    def delete_user(self, user_id: int) -> bool:
        """Delete user and all related data."""
        with self.session_scope() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if user:
                session.delete(user)
                return True
            return False
    
    def get_all_users(self) -> list:
        """Get all users."""
        with self.session_scope() as session:
            return session.query(User).all()
    
    # Supplement operations
    def add_supplement(self, user_id: int, name: str, dosage: str = "", 
                       reminder_time: str = None) -> Supplement:
        """Add a supplement for user."""
        with self.session_scope() as session:
            supplement = Supplement(
                user_id=user_id,
                name=name,
                dosage=dosage,
                reminder_time=reminder_time
            )
            session.add(supplement)
            return supplement
    
    def get_user_supplements(self, user_id: int) -> list:
        """Get all supplements for user."""
        with self.session_scope() as session:
            return session.query(Supplement).filter(
                Supplement.user_id == user_id,
                Supplement.is_active == True
            ).all()
    
    def delete_supplement(self, supplement_id: int) -> bool:
        """Delete a supplement."""
        with self.session_scope() as session:
            supplement = session.query(Supplement).filter(Supplement.id == supplement_id).first()
            if supplement:
                session.delete(supplement)
                return True
            return False
    
    # Schedule operations
    def add_schedule_item(self, user_id: int, item_type: str, name: str,
                          days_of_week: list, start_time: str = None,
                          end_time: str = None, duration_minutes: int = 0) -> ScheduleItem:
        """Add a schedule item."""
        with self.session_scope() as session:
            item = ScheduleItem(
                user_id=user_id,
                item_type=item_type,
                name=name,
                days_of_week=days_of_week,
                start_time=start_time,
                end_time=end_time,
                duration_minutes=duration_minutes
            )
            session.add(item)
            return item
    
    def get_user_schedule(self, user_id: int) -> list:
        """Get all schedule items for user."""
        with self.session_scope() as session:
            return session.query(ScheduleItem).filter(
                ScheduleItem.user_id == user_id,
                ScheduleItem.is_active == True
            ).all()
    
    # Meal schedule operations
    def set_meal_schedule(self, user_id: int, meal_type: str, time: str,
                          reminder_offset_minutes: int = 30) -> MealSchedule:
        """Set or update meal schedule."""
        with self.session_scope() as session:
            meal_schedule = session.query(MealSchedule).filter(
                MealSchedule.user_id == user_id,
                MealSchedule.meal_type == meal_type
            ).first()
            
            if meal_schedule:
                meal_schedule.time = time
                meal_schedule.reminder_offset_minutes = reminder_offset_minutes
            else:
                meal_schedule = MealSchedule(
                    user_id=user_id,
                    meal_type=meal_type,
                    time=time,
                    reminder_offset_minutes=reminder_offset_minutes
                )
                session.add(meal_schedule)
            
            return meal_schedule
    
    def get_user_meal_schedule(self, user_id: int) -> list:
        """Get meal schedule for user."""
        with self.session_scope() as session:
            return session.query(MealSchedule).filter(
                MealSchedule.user_id == user_id,
                MealSchedule.is_active == True
            ).order_by(MealSchedule.time).all()
    
    # Nutrition log operations
    def add_nutrition_log(self, user_id: int, date: date, meal_type: str,
                          food_items: list, total_calories: float = 0.0,
                          total_protein: float = 0.0, total_fat: float = 0.0,
                          total_carbs: float = 0.0, photo_path: str = None,
                          is_ai_recognized: bool = False) -> NutritionLog:
        """Add nutrition log entry."""
        with self.session_scope() as session:
            log = NutritionLog(
                user_id=user_id,
                date=date,
                meal_type=meal_type,
                food_items=food_items,
                total_calories=total_calories,
                total_protein=total_protein,
                total_fat=total_fat,
                total_carbs=total_carbs,
                photo_path=photo_path,
                is_ai_recognized=is_ai_recognized
            )
            session.add(log)
            return log
    
    def get_daily_nutrition(self, user_id: int, date: date) -> dict:
        """Get total nutrition for a day."""
        with self.session_scope() as session:
            logs = session.query(NutritionLog).filter(
                NutritionLog.user_id == user_id,
                NutritionLog.date == date
            ).all()
            
            return {
                'total_calories': sum(log.total_calories for log in logs),
                'total_protein': sum(log.total_protein for log in logs),
                'total_fat': sum(log.total_fat for log in logs),
                'total_carbs': sum(log.total_carbs for log in logs),
                'meals': logs
            }
    
    # Calorie target operations
    def set_daily_calorie_target(self, user_id: int, date: date,
                                  calorie_target: float, protein_target: float,
                                  fat_target: float, carb_target: float) -> DailyCalorieTarget:
        """Set daily calorie target."""
        with self.session_scope() as session:
            target = session.query(DailyCalorieTarget).filter(
                DailyCalorieTarget.user_id == user_id,
                DailyCalorieTarget.date == date
            ).first()
            
            if target:
                target.calorie_target = calorie_target
                target.protein_target = protein_target
                target.fat_target = fat_target
                target.carb_target = carb_target
                target.updated_at = datetime.utcnow()
            else:
                target = DailyCalorieTarget(
                    user_id=user_id,
                    date=date,
                    calorie_target=calorie_target,
                    protein_target=protein_target,
                    fat_target=fat_target,
                    carb_target=carb_target
                )
                session.add(target)
            
            return target
    
    def get_daily_calorie_target(self, user_id: int, date: date) -> Optional[DailyCalorieTarget]:
        """Get daily calorie target."""
        with self.session_scope() as session:
            return session.query(DailyCalorieTarget).filter(
                DailyCalorieTarget.user_id == user_id,
                DailyCalorieTarget.date == date
            ).first()
    
    # Training log operations
    def add_training_log(self, user_id: int, date: date, duration_minutes: int = 0,
                         muscle_groups: list = None, calories_burned: float = 0.0,
                         notes: str = "", is_from_samsung_health: bool = False,
                         is_from_daily_survey: bool = False, training_type: str = "strength",
                         total_volume: float = 0.0, average_rpe: float = 0.0,
                         rir: int = 0, volume_change_percent: float = 0.0,
                         is_pr_day: bool = False) -> TrainingLog:
        """Add training log entry with advanced fields."""
        with self.session_scope() as session:
            log = TrainingLog(
                user_id=user_id,
                date=date,
                duration_minutes=duration_minutes,
                muscle_groups=muscle_groups or [],
                calories_burned=calories_burned,
                notes=notes,
                is_from_samsung_health=is_from_samsung_health,
                is_from_daily_survey=is_from_daily_survey,
                training_type=training_type,
                total_volume=total_volume,
                average_rpe=average_rpe,
                rir=rir,
                volume_change_percent=volume_change_percent,
                is_pr_day=is_pr_day
            )
            session.add(log)
            return log
    
    def get_training_log(self, user_id: int, date: date) -> Optional[TrainingLog]:
        """Get training log for a specific date."""
        with self.session_scope() as session:
            return session.query(TrainingLog).filter(
                TrainingLog.user_id == user_id,
                TrainingLog.date == date
            ).first()
    
    # Health metric operations
    def add_health_metric(self, user_id: int, date: date, **kwargs) -> HealthMetric:
        """Add health metric entry."""
        with self.session_scope() as session:
            metric = HealthMetric(user_id=user_id, date=date, **kwargs)
            session.add(metric)
            return metric
    
    def get_latest_health_metrics(self, user_id: int) -> Optional[HealthMetric]:
        """Get latest health metrics for user."""
        with self.session_scope() as session:
            return session.query(HealthMetric).filter(
                HealthMetric.user_id == user_id
            ).order_by(HealthMetric.date.desc()).first()
    
    # Blood test operations
    def add_blood_test(self, user_id: int, date: date, photo_path: str = None,
                       results: list = None) -> BloodTest:
        """Add blood test entry."""
        with self.session_scope() as session:
            test = BloodTest(
                user_id=user_id,
                date=date,
                photo_path=photo_path,
                results=results or []
            )
            session.add(test)
            return test
    
    def get_blood_tests(self, user_id: int) -> list:
        """Get all blood tests for user."""
        with self.session_scope() as session:
            return session.query(BloodTest).filter(
                BloodTest.user_id == user_id
            ).order_by(BloodTest.date.desc()).all()
    
    # User settings operations
    def get_user_settings(self, user_id: int) -> Optional[UserSettings]:
        """Get user settings."""
        with self.session_scope() as session:
            return session.query(UserSettings).filter(
                UserSettings.user_id == user_id
            ).first()
    
    def update_user_settings(self, user_id: int, **kwargs) -> Optional[UserSettings]:
        """Update user settings."""
        with self.session_scope() as session:
            settings = session.query(UserSettings).filter(
                UserSettings.user_id == user_id
            ).first()
            if settings:
                for key, value in kwargs.items():
                    if hasattr(settings, key):
                        setattr(settings, key, value)
                settings.updated_at = datetime.utcnow()
                return settings
            return None
    
    # Reminder log operations
    def log_reminder(self, user_id: int, reminder_type: str, scheduled_time: datetime,
                     message_text: str = "", is_sent: bool = False) -> ReminderLog:
        """Log a reminder."""
        with self.session_scope() as session:
            log = ReminderLog(
                user_id=user_id,
                reminder_type=reminder_type,
                scheduled_time=scheduled_time,
                message_text=message_text,
                is_sent=is_sent
            )
            session.add(log)
            return log
    
    # Excel report operations
    def add_excel_report(self, user_id: int, report_type: str, period_start: date,
                         period_end: date, file_path: str) -> ExcelReport:
        """Add Excel report entry."""
        with self.session_scope() as session:
            report = ExcelReport(
                user_id=user_id,
                report_type=report_type,
                period_start=period_start,
                period_end=period_end,
                file_path=file_path
            )
            session.add(report)
            return report
    
    def get_excel_reports(self, user_id: int) -> list:
        """Get all Excel reports for user."""
        with self.session_scope() as session:
            return session.query(ExcelReport).filter(
                ExcelReport.user_id == user_id
            ).order_by(ExcelReport.generated_at.desc()).all()

    # ==================== NEW: SymptomLog operations ====================
    def add_symptom_log(self, user_id: int, date: date, **kwargs) -> SymptomLog:
        """Add symptom log entry."""
        with self.session_scope() as session:
            log = SymptomLog(user_id=user_id, date=date, **kwargs)
            session.add(log)
            return log

    def get_symptom_logs(self, user_id: int, start_date: date = None, end_date: date = None) -> list:
        """Get symptom logs for date range."""
        with self.session_scope() as session:
            query = session.query(SymptomLog).filter(SymptomLog.user_id == user_id)
            if start_date:
                query = query.filter(SymptomLog.date >= start_date)
            if end_date:
                query = query.filter(SymptomLog.date <= end_date)
            return query.order_by(SymptomLog.date.desc()).all()

    def get_latest_symptom_log(self, user_id: int) -> Optional[SymptomLog]:
        """Get latest symptom log for user."""
        with self.session_scope() as session:
            return session.query(SymptomLog).filter(
                SymptomLog.user_id == user_id
            ).order_by(SymptomLog.date.desc()).first()

    # ==================== NEW: WaterIntake operations ====================
    def add_water_intake(self, user_id: int, date: date, amount_ml: int, **kwargs) -> WaterIntake:
        """Add water intake entry."""
        with self.session_scope() as session:
            intake = WaterIntake(user_id=user_id, date=date, amount_ml=amount_ml, **kwargs)
            session.add(intake)
            return intake

    def get_daily_water_intake(self, user_id: int, date: date) -> int:
        """Get total water intake for a day."""
        with self.session_scope() as session:
            result = session.query(WaterIntake).filter(
                WaterIntake.user_id == user_id,
                WaterIntake.date == date
            ).all()
            return sum(i.amount_ml for i in result) if result else 0

    def get_water_intake_logs(self, user_id: int, start_date: date = None, end_date: date = None) -> list:
        """Get water intake logs for date range."""
        with self.session_scope() as session:
            query = session.query(WaterIntake).filter(WaterIntake.user_id == user_id)
            if start_date:
                query = query.filter(WaterIntake.date >= start_date)
            if end_date:
                query = query.filter(WaterIntake.date <= end_date)
            return query.order_by(WaterIntake.date.desc()).all()

    # ==================== NEW: PersonalRecord operations ====================
    def add_personal_record(self, user_id: int, exercise_name: str, max_weight: float,
                            reps: int = 1, date_achieved: date = None) -> PersonalRecord:
        """Add or update personal record."""
        with self.session_scope() as session:
            # Check if PR exists
            existing = session.query(PersonalRecord).filter(
                PersonalRecord.user_id == user_id,
                PersonalRecord.exercise_name == exercise_name
            ).first()
            
            if existing:
                if max_weight > existing.max_weight:
                    existing.max_weight = max_weight
                    existing.reps = reps
                    existing.date_achieved = date_achieved or date.today()
                    return existing
                return existing
            else:
                pr = PersonalRecord(
                    user_id=user_id,
                    exercise_name=exercise_name,
                    max_weight=max_weight,
                    reps=reps,
                    date_achieved=date_achieved or date.today()
                )
                session.add(pr)
                return pr

    def get_personal_records(self, user_id: int) -> list:
        """Get all personal records for user."""
        with self.session_scope() as session:
            return session.query(PersonalRecord).filter(
                PersonalRecord.user_id == user_id
            ).all()

    def get_pr_for_exercise(self, user_id: int, exercise_name: str) -> Optional[PersonalRecord]:
        """Get PR for specific exercise."""
        with self.session_scope() as session:
            return session.query(PersonalRecord).filter(
                PersonalRecord.user_id == user_id,
                PersonalRecord.exercise_name == exercise_name
            ).first()

    # ==================== NEW: Achievement operations ====================
    def add_achievement(self, user_id: int, achievement_type: str, name: str,
                        description: str = "", icon: str = "🏆",
                        target_value: int = 0) -> Achievement:
        """Add achievement entry."""
        with self.session_scope() as session:
            achievement = Achievement(
                user_id=user_id,
                achievement_type=achievement_type,
                name=name,
                description=description,
                icon=icon,
                target_value=target_value
            )
            session.add(achievement)
            return achievement

    def get_achievements(self, user_id: int) -> list:
        """Get all achievements for user."""
        with self.session_scope() as session:
            return session.query(Achievement).filter(
                Achievement.user_id == user_id
            ).all()

    def get_completed_achievements(self, user_id: int) -> list:
        """Get completed achievements."""
        with self.session_scope() as session:
            return session.query(Achievement).filter(
                Achievement.user_id == user_id,
                Achievement.is_completed == True
            ).all()

    def update_achievement_progress(self, achievement_id: int, current_value: int,
                                    is_completed: bool = False) -> Optional[Achievement]:
        """Update achievement progress."""
        with self.session_scope() as session:
            achievement = session.query(Achievement).filter(
                Achievement.id == achievement_id
            ).first()
            if achievement:
                achievement.current_value = current_value
                achievement.is_completed = is_completed
                if is_completed and not achievement.unlocked_at:
                    achievement.unlocked_at = datetime.utcnow()
                return achievement
            return None

    # ==================== NEW: DeloadSchedule operations ====================
    def add_deload_schedule(self, user_id: int, cycle_start_date: date,
                            cycle_week_number: int, is_deload_week: bool = False) -> DeloadSchedule:
        """Add deload schedule entry."""
        with self.session_scope() as session:
            deload = DeloadSchedule(
                user_id=user_id,
                cycle_start_date=cycle_start_date,
                cycle_week_number=cycle_week_number,
                is_deload_week=is_deload_week
            )
            session.add(deload)
            return deload

    def get_deload_schedule(self, user_id: int, weeks_ahead: int = 4) -> list:
        """Get deload schedule for upcoming weeks."""
        with self.session_scope() as session:
            return session.query(DeloadSchedule).filter(
                DeloadSchedule.user_id == user_id
            ).order_by(DeloadSchedule.cycle_start_date.desc()).limit(weeks_ahead).all()

    def get_current_deload_week(self, user_id: int) -> Optional[DeloadSchedule]:
        """Get current week's deload status."""
        with self.session_scope() as session:
            return session.query(DeloadSchedule).filter(
                DeloadSchedule.user_id == user_id,
                DeloadSchedule.cycle_start_date <= date.today()
            ).order_by(DeloadSchedule.cycle_start_date.desc()).first()


# Global database manager instance
db_manager = DatabaseManager()
