"""
Nutrition tracking module for Health Bot.
Handles food recognition, calorie counting, and meal logging.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import date, datetime
import logging
import json

from database.manager import db_manager
from database.models import NutritionLog, DailyCalorieTarget

logger = logging.getLogger(__name__)


class NutritionManager:
    """Manager for nutrition tracking and food analysis."""
    
    def __init__(self):
        self.db = db_manager
    
    def get_daily_summary(self, user_id: int, target_date: date = None) -> Dict[str, Any]:
        """
        Get daily nutrition summary.
        
        Returns:
            Dictionary with daily totals and progress towards goals
        """
        if target_date is None:
            target_date = date.today()
        
        # Get nutrition logs for the day
        daily_data = self.db.get_daily_nutrition(user_id, target_date)
        
        # Get calorie target
        calorie_target = self.db.get_daily_calorie_target(user_id, target_date)
        
        totals = {
            'date': target_date.isoformat(),
            'calories': daily_data['total_calories'],
            'protein': daily_data['total_protein'],
            'fat': daily_data['total_fat'],
            'carbs': daily_data['total_carbs'],
            'meals_count': len(daily_data['meals']),
            'meals': daily_data['meals']
        }
        
        if calorie_target:
            totals['targets'] = {
                'calories': calorie_target.calorie_target,
                'protein': calorie_target.protein_target,
                'fat': calorie_target.fat_target,
                'carbs': calorie_target.carb_target
            }
            
            # Calculate percentages
            totals['progress'] = {
                'calories_percent': round(
                    (daily_data['total_calories'] / calorie_target.calorie_target) * 100, 1
                ) if calorie_target.calorie_target > 0 else 0,
                'protein_percent': round(
                    (daily_data['total_protein'] / calorie_target.protein_target) * 100, 1
                ) if calorie_target.protein_target > 0 else 0,
                'fat_percent': round(
                    (daily_data['total_fat'] / calorie_target.fat_target) * 100, 1
                ) if calorie_target.fat_target > 0 else 0,
                'carbs_percent': round(
                    (daily_data['total_carbs'] / calorie_target.carb_target) * 100, 1
                ) if calorie_target.carb_target > 0 else 0
            }
            
            # Calculate remaining
            totals['remaining'] = {
                'calories': round(calorie_target.calorie_target - daily_data['total_calories'], 0),
                'protein': round(calorie_target.protein_target - daily_data['total_protein'], 1),
                'fat': round(calorie_target.fat_target - daily_data['total_fat'], 1),
                'carbs': round(calorie_target.carb_target - daily_data['total_carbs'], 1)
            }
        else:
            totals['targets'] = None
            totals['progress'] = None
            totals['remaining'] = None
        
        return totals
    
    def log_meal(
        self,
        user_id: int,
        meal_type: str,
        food_items: List[Dict[str, Any]],
        photo_path: Optional[str] = None,
        is_ai_recognized: bool = False
    ) -> Tuple[bool, NutritionLog, str]:
        """
        Log a meal with food items.
        
        Args:
            user_id: User internal ID
            meal_type: Type of meal (breakfast, lunch, etc.)
            food_items: List of food items with nutrition data
            photo_path: Path to photo if available
            is_ai_recognized: Whether food was recognized by AI
        
        Returns:
            Tuple of (success, nutrition_log, message)
        """
        try:
            # Calculate totals
            total_calories = sum(item.get('calories', 0) for item in food_items)
            total_protein = sum(item.get('protein', 0) for item in food_items)
            total_fat = sum(item.get('fat', 0) for item in food_items)
            total_carbs = sum(item.get('carbs', 0) for item in food_items)
            
            # Add nutrition log
            nutrition_log = self.db.add_nutrition_log(
                user_id=user_id,
                date=date.today(),
                meal_type=meal_type,
                food_items=food_items,
                total_calories=total_calories,
                total_protein=total_protein,
                total_fat=total_fat,
                total_carbs=total_carbs,
                photo_path=photo_path,
                is_ai_recognized=is_ai_recognized
            )
            
            return True, nutrition_log, "✅ Прием пищи записан"
            
        except Exception as e:
            logger.error(f"Error logging meal: {e}")
            return False, None, f"❌ Ошибка при записи приема пищи: {e}"
    
    def update_meal(
        self,
        user_id: int,
        meal_type: str,
        food_items: List[Dict[str, Any]],
        target_date: date = None
    ) -> Tuple[bool, str]:
        """
        Update an existing meal log.
        
        Args:
            user_id: User internal ID
            meal_type: Type of meal to update
            food_items: Updated list of food items
            target_date: Date of meal (default: today)
        
        Returns:
            Tuple of (success, message)
        """
        if target_date is None:
            target_date = date.today()
        
        try:
            with self.db.session_scope() as session:
                # Find existing log
                existing_log = session.query(NutritionLog).filter(
                    NutritionLog.user_id == user_id,
                    NutritionLog.date == target_date,
                    NutritionLog.meal_type == meal_type
                ).first()
                
                if not existing_log:
                    return False, "❌ Прием пищи не найден"
                
                # Update food items
                existing_log.food_items = food_items
                existing_log.is_manually_edited = True
                
                # Recalculate totals
                existing_log.total_calories = sum(
                    item.get('calories', 0) for item in food_items
                )
                existing_log.total_protein = sum(
                    item.get('protein', 0) for item in food_items
                )
                existing_log.total_fat = sum(
                    item.get('fat', 0) for item in food_items
                )
                existing_log.total_carbs = sum(
                    item.get('carbs', 0) for item in food_items
                )
                existing_log.updated_at = datetime.utcnow()
                
                return True, "✅ Прием пищи обновлен"
                
        except Exception as e:
            logger.error(f"Error updating meal: {e}")
            return False, f"❌ Ошибка при обновлении: {e}"
    
    def delete_meal(self, user_id: int, meal_type: str, target_date: date = None) -> Tuple[bool, str]:
        """Delete a meal log."""
        if target_date is None:
            target_date = date.today()
        
        try:
            with self.db.session_scope() as session:
                log = session.query(NutritionLog).filter(
                    NutritionLog.user_id == user_id,
                    NutritionLog.date == target_date,
                    NutritionLog.meal_type == meal_type
                ).first()
                
                if log:
                    session.delete(log)
                    return True, "✅ Прием пищи удален"
                return False, "❌ Прием пищи не найден"
                
        except Exception as e:
            logger.error(f"Error deleting meal: {e}")
            return False, f"❌ Ошибка при удалении: {e}"
    
    def get_meal_by_type(self, user_id: int, meal_type: str, target_date: date = None) -> Optional[NutritionLog]:
        """Get meal log by type and date."""
        if target_date is None:
            target_date = date.today()
        
        with self.db.session_scope() as session:
            return session.query(NutritionLog).filter(
                NutritionLog.user_id == user_id,
                NutritionLog.date == target_date,
                NutritionLog.meal_type == meal_type
            ).first()
    
    def calculate_calorie_target(
        self,
        user_id: int,
        target_date: date = None,
        force_recalculate: bool = False
    ) -> DailyCalorieTarget:
        """
        Calculate and set daily calorie target for user.
        
        Args:
            user_id: User internal ID
            target_date: Date for target
            force_recalculate: Force recalculation even if target exists
        
        Returns:
            DailyCalorieTarget object
        """
        if target_date is None:
            target_date = date.today()
        
        # Check if target already exists
        existing_target = self.db.get_daily_calorie_target(user_id, target_date)
        if existing_target and not force_recalculate:
            return existing_target
        
        # Get user
        user = self.db.get_user_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Calculate BMR (Mifflin-St Jeor)
        weight = user.weight_kg
        height = user.height_cm
        age = user.get_age()
        
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
        
        # Activity multiplier
        training_days = self._get_training_days_per_week(user_id)
        
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
        
        tdee = bmr * activity_multiplier
        
        # Adjust based on goal
        goal = user.goal
        if goal and goal.value == "weight_loss":
            tdee *= 0.85
        elif goal and goal.value == "muscle_gain":
            tdee *= 1.1
        
        # Calculate macros
        protein = weight * 2.0  # 2g per kg
        fat = weight * 1.0  # 1g per kg
        protein_calories = protein * 4
        fat_calories = fat * 9
        carbs = (tdee - protein_calories - fat_calories) / 4
        
        # Set target
        target = self.db.set_daily_calorie_target(
            user_id=user_id,
            date=target_date,
            calorie_target=tdee,
            protein_target=protein,
            fat_target=fat,
            carb_target=carbs
        )
        
        return target
    
    def _get_training_days_per_week(self, user_id: int) -> int:
        """Get number of training days per week for user."""
        schedule = self.db.get_user_schedule(user_id)
        for item in schedule:
            if item.item_type == "training":
                return len(item.days_of_week)
        return 0
    
    def get_weekly_summary(self, user_id: int, week_start: date = None) -> Dict[str, Any]:
        """
        Get weekly nutrition summary.
        
        Args:
            user_id: User internal ID
            week_start: Start of week (default: most recent Monday)
        
        Returns:
            Dictionary with weekly statistics
        """
        from datetime import timedelta
        
        if week_start is None:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
        
        week_end = week_start + timedelta(days=6)
        
        daily_summaries = []
        current_date = week_start
        
        while current_date <= week_end:
            daily_summary = self.get_daily_summary(user_id, current_date)
            daily_summaries.append(daily_summary)
            current_date += timedelta(days=1)
        
        # Calculate weekly averages
        valid_days = [d for d in daily_summaries if d['meals_count'] > 0]
        
        weekly_avg = {
            'calories': sum(d['calories'] for d in valid_days) / len(valid_days) if valid_days else 0,
            'protein': sum(d['protein'] for d in valid_days) / len(valid_days) if valid_days else 0,
            'fat': sum(d['fat'] for d in valid_days) / len(valid_days) if valid_days else 0,
            'carbs': sum(d['carbs'] for d in valid_days) / len(valid_days) if valid_days else 0
        }
        
        return {
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
            'daily_summaries': daily_summaries,
            'weekly_averages': weekly_avg,
            'days_logged': len(valid_days),
            'total_days': 7
        }
    
    def get_food_database(self) -> Dict[str, Dict[str, Any]]:
        """
        Get basic food database for quick lookups.
        This is a simplified version - can be expanded or replaced with API calls.
        
        Returns:
            Dictionary of food items with nutrition data (per 100g)
        """
        return {
            "chicken_breast": {
                "name": "Куриная грудка",
                "calories": 165,
                "protein": 31,
                "fat": 3.6,
                "carbs": 0
            },
            "rice": {
                "name": "Рис белый",
                "calories": 130,
                "protein": 2.7,
                "fat": 0.3,
                "carbs": 28
            },
            "egg": {
                "name": "Яйцо куриное",
                "calories": 155,
                "protein": 13,
                "fat": 11,
                "carbs": 1.1
            },
            "oatmeal": {
                "name": "Овсянка",
                "calories": 68,
                "protein": 2.4,
                "fat": 1.4,
                "carbs": 12
            },
            "banana": {
                "name": "Банан",
                "calories": 89,
                "protein": 1.1,
                "fat": 0.3,
                "carbs": 23
            },
            "salmon": {
                "name": "Лосось",
                "calories": 208,
                "protein": 20,
                "fat": 13,
                "carbs": 0
            },
            "potato": {
                "name": "Картофель",
                "calories": 77,
                "protein": 2,
                "fat": 0.1,
                "carbs": 17
            },
            "broccoli": {
                "name": "Брокколи",
                "calories": 34,
                "protein": 2.8,
                "fat": 0.4,
                "carbs": 7
            },
            "cottage_cheese": {
                "name": "Творог 5%",
                "calories": 121,
                "protein": 17,
                "fat": 5,
                "carbs": 1.8
            },
            "bread": {
                "name": "Хлеб цельнозерновой",
                "calories": 250,
                "protein": 13,
                "fat": 3.5,
                "carbs": 45
            }
        }


# Global instance
nutrition_manager = NutritionManager()
