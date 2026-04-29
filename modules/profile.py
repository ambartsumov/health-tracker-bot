"""
User profile module for Health Bot.
Handles user onboarding, profile management, and settings.
"""

from datetime import datetime, date
from typing import Optional, Dict, List, Any
from decimal import Decimal
import logging

from database.manager import db_manager
from database.models import User, UserSettings, GoalType, Supplement, ScheduleItem, MealSchedule

logger = logging.getLogger(__name__)


class UserProfileManager:
    """Manager for user profiles and onboarding."""

    def __init__(self):
        self.db = db_manager

    def check_existing_user(self, telegram_id: str) -> Optional[User]:
        """Check if user exists in database."""
        return self.db.get_user_by_telegram_id(telegram_id)

    def create_new_user_profile(self, telegram_id: str, user_data: Dict[str, Any]) -> User:
        """
        Create a new user profile from onboarding data.
        
        Args:
            telegram_id: Telegram user ID
            user_data: Dictionary containing user information from onboarding
        
        Returns:
            Created User object
        """
        # Parse date of birth
        dob = user_data.get("date_of_birth")
        if isinstance(dob, str):
            dob = datetime.strptime(dob, "%Y-%m-%d").date()
        
        # Parse goal
        goal_str = user_data.get("goal", "aesthetic_and_health")
        goal_map = {
            "weight_loss": GoalType.WEIGHT_LOSS,
            "muscle_gain": GoalType.MUSCLE_GAIN,
            "aesthetic_and_health": GoalType.AESTHETIC_AND_HEALTH,
            "endurance": GoalType.ENDURANCE,
            "maintenance": GoalType.MAINTENANCE
        }
        goal = goal_map.get(goal_str, GoalType.AESTHETIC_AND_HEALTH)
        
        # Create user
        user = self.db.create_user(
            telegram_id=telegram_id,
            name=user_data.get("name", "User"),
            date_of_birth=dob,
            weight_kg=float(user_data.get("weight_kg", 0)),
            height_cm=float(user_data.get("height_cm", 0)),
            goal=goal,
            is_default_user=False
        )
        
        # Add health conditions
        health_conditions = user_data.get("health_conditions", [])
        if health_conditions:
            self.db.update_user(user.id, health_conditions=health_conditions)
        
        # Add supplements
        for supplement in user_data.get("supplements", []):
            self.db.add_supplement(
                user_id=user.id,
                name=supplement.get("name", ""),
                dosage=supplement.get("dosage", ""),
                reminder_time=supplement.get("reminder_time")
            )
        
        # Add schedule items
        for schedule_item in user_data.get("schedule_items", []):
            self.db.add_schedule_item(
                user_id=user.id,
                item_type=schedule_item.get("type", ""),
                name=schedule_item.get("name", ""),
                days_of_week=schedule_item.get("days_of_week", []),
                start_time=schedule_item.get("start_time"),
                end_time=schedule_item.get("end_time"),
                duration_minutes=schedule_item.get("duration_minutes", 0)
            )
        
        # Add meal schedule
        for meal in user_data.get("meal_schedule", []):
            self.db.set_meal_schedule(
                user_id=user.id,
                meal_type=meal.get("meal_type", ""),
                time=meal.get("time", ""),
                reminder_offset_minutes=meal.get("reminder_offset", 30)
            )
        
        logger.info(f"Created new user profile: {user.name} (telegram_id: {telegram_id})")
        return user
    
    def update_user_profile(self, user_id: int, updates: Dict[str, Any]) -> Optional[User]:
        """
        Update user profile data.
        
        Args:
            user_id: User internal ID
            updates: Dictionary of fields to update
        
        Returns:
            Updated User object or None
        """
        # Convert date strings to date objects
        if "date_of_birth" in updates and isinstance(updates["date_of_birth"], str):
            updates["date_of_birth"] = datetime.strptime(
                updates["date_of_birth"], "%Y-%m-%d"
            ).date()
        
        # Convert goal string to enum
        if "goal" in updates and isinstance(updates["goal"], str):
            goal_map = {
                "weight_loss": GoalType.WEIGHT_LOSS,
                "muscle_gain": GoalType.MUSCLE_GAIN,
                "aesthetic_and_health": GoalType.AESTHETIC_AND_HEALTH,
                "endurance": GoalType.ENDURANCE,
                "maintenance": GoalType.MAINTENANCE
            }
            updates["goal"] = goal_map.get(updates["goal"], GoalType.AESTHETIC_AND_HEALTH)
        
        return self.db.update_user(user_id, **updates)
    
    def get_user_profile(self, telegram_id: str) -> Optional[Dict[str, Any]]:
        """
        Get complete user profile data.
        
        Args:
            telegram_id: Telegram user ID
        
        Returns:
            Dictionary with complete user profile or None
        """
        user = self.db.get_user_by_telegram_id(telegram_id)
        if not user:
            return None
        
        return {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "name": user.name,
            "age": user.get_age(),
            "date_of_birth": user.date_of_birth.isoformat(),
            "weight_kg": user.weight_kg,
            "height_cm": user.height_cm,
            "goal": user.goal.value if user.goal else None,
            "health_conditions": user.health_conditions or [],
            "supplements": [
                {
                    "id": s.id,
                    "name": s.name,
                    "dosage": s.dosage,
                    "reminder_time": s.reminder_time,
                    "is_active": s.is_active
                }
                for s in self.db.get_user_supplements(user.id)
            ],
            "schedule": [
                {
                    "id": s.id,
                    "type": s.item_type,
                    "name": s.name,
                    "days_of_week": s.days_of_week,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "duration_minutes": s.duration_minutes
                }
                for s in self.db.get_user_schedule(user.id)
            ],
            "meal_schedule": [
                {
                    "id": m.id,
                    "meal_type": m.meal_type,
                    "time": m.time,
                    "reminder_offset_minutes": m.reminder_offset_minutes
                }
                for m in self.db.get_user_meal_schedule(user.id)
            ],
            "settings": self._get_settings_dict(user.id)
        }
    
    def _get_settings_dict(self, user_id: int) -> Dict[str, Any]:
        """Get user settings as dictionary."""
        settings = self.db.get_user_settings(user_id)
        if not settings:
            return {}
        
        return {
            "enable_meal_reminders": settings.enable_meal_reminders,
            "enable_supplement_reminders": settings.enable_supplement_reminders,
            "enable_training_reminders": settings.enable_training_reminders,
            "enable_daily_summary": settings.enable_daily_summary,
            "daily_summary_time": settings.daily_summary_time,
            "language": settings.language,
            "timezone": settings.timezone,
            "samsung_health_enabled": settings.samsung_health_enabled,
            "deepseek_enabled": settings.deepseek_enabled,
            "gemini_enabled": settings.gemini_enabled
        }
    
    def update_user_settings(self, user_id: int, settings_updates: Dict[str, Any]) -> bool:
        """
        Update user settings.
        
        Args:
            user_id: User internal ID
            settings_updates: Dictionary of settings to update
        
        Returns:
            True if successful
        """
        result = self.db.update_user_settings(user_id, **settings_updates)
        return result is not None
    
    def calculate_bmi(self, weight_kg: float, height_cm: float) -> Optional[float]:
        """Calculate Body Mass Index."""
        if not weight_kg or not height_cm or height_cm <= 0:
            return None
        height_m = height_cm / 100
        return round(weight_kg / (height_m ** 2), 2)
    
    def calculate_daily_calories(self, user: User) -> Dict[str, float]:
        """
        Calculate daily calorie and macro requirements using Mifflin-St Jeor equation.
        
        Returns:
            Dictionary with calorie and macro targets
        """
        weight = user.weight_kg
        height = user.height_cm
        age = user.get_age()
        
        # BMR calculation (Mifflin-St Jeor)
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
        
        # Activity multiplier (based on training schedule)
        schedule = self.db.get_user_schedule(user.id)
        training_days = 0
        for item in schedule:
            if item.item_type == "training":
                training_days = len(item.days_of_week)
                break
        
        if training_days == 0:
            activity_multiplier = 1.2
        elif training_days <= 2:
            activity_multiplier = 1.375
        elif training_days <= 4:
            activity_multiplier = 1.55
        elif training_days <= 6:
            activity_multiplier = 1.725
        else:
            activity_multiplier = 1.9
        
        # TDEE
        tdee = bmr * activity_multiplier
        
        # Adjust based on goal
        goal = user.goal
        if goal == GoalType.WEIGHT_LOSS:
            tdee *= 0.85  # 15% deficit
        elif goal == GoalType.MUSCLE_GAIN:
            tdee *= 1.1  # 10% surplus
        # AESTHETIC_AND_HEALTH and MAINTENANCE use maintenance calories
        
        # Macro calculation
        protein_per_kg = 2.0  # grams per kg for athletic goals
        protein = weight * protein_per_kg
        protein_calories = protein * 4
        
        fat_per_kg = 1.0  # grams per kg
        fat = weight * fat_per_kg
        fat_calories = fat * 9
        
        # Remaining calories for carbs
        remaining_calories = tdee - protein_calories - fat_calories
        carbs = remaining_calories / 4
        
        return {
            "calories": round(tdee, 0),
            "protein_g": round(protein, 1),
            "fat_g": round(fat, 1),
            "carbs_g": round(carbs, 1),
            "bmr": round(bmr, 0),
            "tdee": round(tdee, 0)
        }


# Global instance
profile_manager = UserProfileManager()
