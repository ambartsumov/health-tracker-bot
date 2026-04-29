"""
Gamification module for Health Bot.
Achievements, streaks, XP system, levels, and rewards.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import date, datetime, timedelta
import logging

from database.manager import db_manager
from database.models import Achievement, User, NutritionLog, TrainingLog, WaterIntake, SymptomLog

logger = logging.getLogger(__name__)


# ==================== ACHIEVEMENT DEFINITIONS ====================

ACHIEVEMENTS = {
    # Nutrition streaks
    "nutrition_7_day": {
        "name": "Недельный питатель",
        "description": "7 дней подряд записывал питание",
        "icon": "🍽️",
        "type": "streak",
        "category": "nutrition",
        "xp_reward": 100,
        "target": 7
    },
    "nutrition_30_day": {
        "name": "Месяц питания",
        "description": "30 дней подряд записывал питание",
        "icon": "📊",
        "type": "streak",
        "category": "nutrition",
        "xp_reward": 500,
        "target": 30
    },
    "nutrition_100_day": {
        "name": "Легенда питания",
        "description": "100 дней подряд записывал питание",
        "icon": "👑",
        "type": "streak",
        "category": "nutrition",
        "xp_reward": 2000,
        "target": 100
    },
    
    # Training achievements
    "first_workout": {
        "name": "Первый шаг",
        "description": "Первая тренировка",
        "icon": "💪",
        "type": "first_time",
        "category": "training",
        "xp_reward": 50,
        "target": 1
    },
    "workout_10": {
        "name": "Десяточка",
        "description": "10 тренировок за месяц",
        "icon": "🏋️",
        "type": "milestone",
        "category": "training",
        "xp_reward": 200,
        "target": 10
    },
    "workout_50": {
        "name": "Стальной атлет",
        "description": "50 тренировок за всё время",
        "icon": "🦾",
        "type": "milestone",
        "category": "training",
        "xp_reward": 1000,
        "target": 50
    },
    
    # PR achievements
    "first_pr": {
        "name": "Новый рекорд!",
        "description": "Первый личный рекорд",
        "icon": "🏆",
        "type": "first_time",
        "category": "strength",
        "xp_reward": 150,
        "target": 1
    },
    "pr_5": {
        "name": "Силач",
        "description": "5 личных рекордов",
        "icon": "🥇",
        "type": "milestone",
        "category": "strength",
        "xp_reward": 500,
        "target": 5
    },
    
    # Hydration achievements
    "water_7_day": {
        "name": "Водный баланс",
        "description": "7 дней подряд выпивал норму воды",
        "icon": "💧",
        "type": "streak",
        "category": "hydration",
        "xp_reward": 100,
        "target": 7
    },
    "water_30_day": {
        "name": "Водный воин",
        "description": "30 дней подряд выпивал норму воды",
        "icon": "🌊",
        "type": "streak",
        "category": "hydration",
        "xp_reward": 500,
        "target": 30
    },
    
    # Symptom tracking
    "symptom_7_day": {
        "name": "Осознанный",
        "description": "7 дней подряд отслеживал симптомы",
        "icon": "🧘",
        "type": "streak",
        "category": "health",
        "xp_reward": 100,
        "target": 7
    },
    
    # Perfect macros
    "perfect_macros_day": {
        "name": "Точный расчет",
        "description": "Выполнил норму КБЖУ за день",
        "icon": "🎯",
        "type": "first_time",
        "category": "nutrition",
        "xp_reward": 75,
        "target": 1
    },
    "perfect_macros_week": {
        "name": "Макро-мастер",
        "description": "7 дней выполнил норму КБЖУ",
        "icon": "📐",
        "type": "milestone",
        "category": "nutrition",
        "xp_reward": 400,
        "target": 7
    },
    
    # Weight milestones
    "weight_loss_5kg": {
        "name": "Минус 5 кг!",
        "description": "Потерял 5 кг от начального веса",
        "icon": "⚖️",
        "type": "milestone",
        "category": "progress",
        "xp_reward": 300,
        "target": 5
    },
    "weight_loss_10kg": {
        "name": "Трансформация",
        "description": "Потерял 10 кг от начального веса",
        "icon": "🦋",
        "type": "milestone",
        "category": "progress",
        "xp_reward": 800,
        "target": 10
    },
    
    # Consistency
    "consistency_30_day": {
        "name": "Постоянство",
        "description": "30 дней активности (любые действия)",
        "icon": "🔥",
        "type": "streak",
        "category": "consistency",
        "xp_reward": 500,
        "target": 30
    },
    "consistency_90_day": {
        "name": "Образ жизни",
        "description": "90 дней активности",
        "icon": "✨",
        "type": "streak",
        "category": "consistency",
        "xp_reward": 1500,
        "target": 90
    },
}


# ==================== LEVEL SYSTEM ====================

def get_level_xp_requirement(level: int) -> int:
    """
    Calculate XP required for next level.
    Formula: 100 * level^1.5 (exponential growth)
    """
    return int(100 * (level ** 1.5))


def get_total_xp_for_level(level: int) -> int:
    """Calculate total XP needed to reach a level."""
    total = 0
    for i in range(1, level):
        total += get_level_xp_requirement(i)
    return total


def get_level_from_xp(total_xp: int) -> Tuple[int, int, int]:
    """
    Calculate level from total XP.
    
    Returns:
        Tuple of (level, current_level_xp, xp_for_next_level)
    """
    level = 1
    xp_needed = get_level_xp_requirement(level)
    xp_accumulated = 0
    
    while total_xp >= xp_accumulated + xp_needed:
        xp_accumulated += xp_needed
        level += 1
        xp_needed = get_level_xp_requirement(level)
    
    current_level_xp = total_xp - xp_accumulated
    return level, current_level_xp, xp_needed


class GamificationManager:
    """Manager for gamification features."""

    def __init__(self):
        self.db = db_manager

    # ==================== XP & LEVELING ====================

    def get_user_progress(self, user_id: int) -> Dict[str, Any]:
        """
        Get user's gamification progress.
        
        Returns:
            Dictionary with level, XP, achievements info
        """
        user = self.db.get_user_by_id(user_id)
        if not user:
            return {}
        
        # Calculate total XP from achievements
        achievements = self.db.get_achievements(user_id)
        total_xp = sum(
            ACHIEVEMENTS.get(a.achievement_type, {}).get("xp_reward", 0)
            for a in achievements if a.is_completed
        )
        
        level, current_xp, next_level_xp = get_level_from_xp(total_xp)
        
        # Get streaks
        nutrition_streak = self.get_nutrition_streak(user_id)
        water_streak = self.get_water_streak(user_id)
        workout_streak = self.get_workout_streak(user_id)
        
        return {
            "level": level,
            "total_xp": total_xp,
            "current_xp": current_xp,
            "xp_for_next_level": next_level_xp,
            "progress_percent": round((current_xp / next_level_xp) * 100, 1) if next_level_xp > 0 else 0,
            "achievements_unlocked": len([a for a in achievements if a.is_completed]),
            "total_achievements": len(ACHIEVEMENTS),
            "streaks": {
                "nutrition": nutrition_streak,
                "water": water_streak,
                "workout": workout_streak
            }
        }

    def add_xp(self, user_id: int, amount: int, reason: str = "") -> int:
        """
        Add XP to user (for tracking, actual XP comes from achievements).
        
        Returns:
            New total XP
        """
        # XP is automatically calculated from achievements
        # This method is for future use or manual awards
        return self.get_user_progress(user_id).get("total_xp", 0)

    # ==================== STREAK TRACKING ====================

    def get_nutrition_streak(self, user_id: int) -> int:
        """Get current nutrition logging streak."""
        today = date.today()
        streak = 0
        
        # Check backwards from today
        for i in range(365):  # Max 1 year streak
            check_date = today - timedelta(days=i)
            
            with self.db.session_scope() as session:
                count = session.query(NutritionLog).filter(
                    NutritionLog.user_id == user_id,
                    NutritionLog.date == check_date
                ).count()
            
            if count > 0:
                streak += 1
            elif i > 0:
                # Streak broken (except if today has no logs yet)
                break
            else:
                # Today has no logs yet, don't break streak
                pass
        
        return streak

    def get_water_streak(self, user_id: int, target_ml: int = 2000) -> int:
        """Get current water drinking streak."""
        today = date.today()
        streak = 0
        
        for i in range(365):
            check_date = today - timedelta(days=i)
            total = self.db.get_daily_water_intake(user_id, check_date)
            
            if total >= target_ml:
                streak += 1
            elif i > 0:
                break
            else:
                pass
        
        return streak

    def get_workout_streak(self, user_id: int, days_window: int = 7) -> int:
        """
        Get workout consistency streak.
        Counts weeks with at least 3 workouts.
        """
        today = date.today()
        streak_weeks = 0
        
        for week_offset in range(52):  # Max 1 year
            week_start = today - timedelta(weeks=week_offset, days=today.weekday())
            week_end = week_start + timedelta(days=6)
            
            with self.db.session_scope() as session:
                count = session.query(TrainingLog).filter(
                    TrainingLog.user_id == user_id,
                    TrainingLog.date >= week_start,
                    TrainingLog.date <= week_end
                ).count()
            
            if count >= 3:  # At least 3 workouts per week
                streak_weeks += 1
            elif week_offset > 0:
                break
        
        return streak_weeks

    # ==================== ACHIEVEMENT CHECKING ====================

    def check_achievements(self, user_id: int) -> List[Achievement]:
        """
        Check and unlock achievements for user.
        
        Returns:
            List of newly unlocked achievements
        """
        newly_unlocked = []
        user = self.db.get_user_by_id(user_id)
        if not user:
            return []
        
        existing = {a.achievement_type: a for a in self.db.get_achievements(user_id)}
        
        # Nutrition streaks
        nutrition_streak = self.get_nutrition_streak(user_id)
        for achievement_type in ["nutrition_7_day", "nutrition_30_day", "nutrition_100_day"]:
            ach = ACHIEVEMENTS[achievement_type]
            if nutrition_streak >= ach["target"]:
                newly_unlocked.extend(self._try_unlock_achievement(
                    user_id, achievement_type, existing, nutrition_streak
                ))
        
        # Water streaks
        water_streak = self.get_water_streak(user_id)
        for achievement_type in ["water_7_day", "water_30_day"]:
            ach = ACHIEVEMENTS[achievement_type]
            if water_streak >= ach["target"]:
                newly_unlocked.extend(self._try_unlock_achievement(
                    user_id, achievement_type, existing, water_streak
                ))
        
        # Workout milestones
        with self.db.session_scope() as session:
            total_workouts = session.query(TrainingLog).filter(
                TrainingLog.user_id == user_id
            ).count()
        
        if total_workouts >= 1:
            newly_unlocked.extend(self._try_unlock_achievement(
                user_id, "first_workout", existing, 1
            ))
        if total_workouts >= 10:
            newly_unlocked.extend(self._try_unlock_achievement(
                user_id, "workout_10", existing, total_workouts
            ))
        if total_workouts >= 50:
            newly_unlocked.extend(self._try_unlock_achievement(
                user_id, "workout_50", existing, total_workouts
            ))
        
        # PR achievements
        prs = self.db.get_personal_records(user_id)
        if len(prs) >= 1:
            newly_unlocked.extend(self._try_unlock_achievement(
                user_id, "first_pr", existing, len(prs)
            ))
        if len(prs) >= 5:
            newly_unlocked.extend(self._try_unlock_achievement(
                user_id, "pr_5", existing, len(prs)
            ))
        
        # Consistency
        total_active_days = self._get_total_active_days(user_id)
        if total_active_days >= 30:
            newly_unlocked.extend(self._try_unlock_achievement(
                user_id, "consistency_30_day", existing, total_active_days
            ))
        if total_active_days >= 90:
            newly_unlocked.extend(self._try_unlock_achievement(
                user_id, "consistency_90_day", existing, total_active_days
            ))
        
        return newly_unlocked

    def _try_unlock_achievement(
        self,
        user_id: int,
        achievement_type: str,
        existing: Dict[str, Achievement],
        current_value: int
    ) -> List[Achievement]:
        """Try to unlock an achievement."""
        unlocked = []
        ach_def = ACHIEVEMENTS.get(achievement_type)
        
        if not ach_def:
            return []
        
        if achievement_type in existing:
            existing_ach = existing[achievement_type]
            if not existing_ach.is_completed and current_value >= ach_def["target"]:
                self.db.update_achievement_progress(
                    existing_ach.id,
                    current_value,
                    is_completed=True
                )
                unlocked.append(existing_ach)
            elif existing_ach.is_completed:
                pass  # Already completed
            else:
                self.db.update_achievement_progress(
                    existing_ach.id,
                    current_value,
                    is_completed=False
                )
        else:
            # Create new achievement
            new_ach = self.db.add_achievement(
                user_id=user_id,
                achievement_type=achievement_type,
                name=ach_def["name"],
                description=ach_def["description"],
                icon=ach_def["icon"],
                target_value=ach_def["target"]
            )
            if current_value >= ach_def["target"]:
                self.db.update_achievement_progress(
                    new_ach.id,
                    current_value,
                    is_completed=True
                )
                unlocked.append(new_ach)
        
        return unlocked

    def _get_total_active_days(self, user_id: int) -> int:
        """Get total number of active days (any logging)."""
        with self.db.session_scope() as session:
            # Count distinct dates with any activity
            nutrition_dates = session.query(NutritionLog.date).filter(
                NutritionLog.user_id == user_id
            ).distinct().count()
            
            training_dates = session.query(TrainingLog.date).filter(
                TrainingLog.user_id == user_id
            ).distinct().count()
            
            # This is simplified - would need union for accurate count
            return max(nutrition_dates, training_dates)

    # ==================== LEVEL UP NOTIFICATION ====================

    def check_level_up(self, user_id: int) -> Tuple[bool, Optional[Dict]]:
        """
        Check if user leveled up.
        
        Returns:
            Tuple of (leveled_up, level_info)
        """
        progress = self.get_user_progress(user_id)
        current_level = progress.get("level", 1)
        
        # Get previous level
        # This would need to be stored - simplified for now
        previous_level = current_level - 1
        
        if current_level > previous_level:
            return True, {
                "new_level": current_level,
                "previous_level": previous_level,
                "message": f"🎉 Уровень {current_level}! Продолжай в том же духе!"
            }
        
        return False, None

    def get_leaderboard_text(self, user_id: int) -> str:
        """Get formatted leaderboard text."""
        progress = self.get_user_progress(user_id)
        
        text = "🎮 **Твой прогресс**\n\n"
        text += f"📊 Уровень {progress['level']}\n"
        text += f"⭐ XP: {progress['current_xp']}/{progress['xp_for_next_level']}\n"
        text += f"📈 Прогресс: {progress['progress_percent']}%\n\n"
        
        text += "🏆 **Достижения:** {}/{}\n".format(
            progress['achievements_unlocked'],
            progress['total_achievements']
        )
        
        if progress['streaks']:
            text += "\n🔥 **Серии:**\n"
            if progress['streaks'].get('nutrition', 0) > 0:
                text += f"• Питание: {progress['streaks']['nutrition']} дней\n"
            if progress['streaks'].get('water', 0) > 0:
                text += f"• Вода: {progress['streaks']['water']} дней\n"
            if progress['streaks'].get('workout', 0) > 0:
                text += f"• Тренировки: {progress['streaks']['workout']} недель\n"
        
        return text


# Global instance
gamification_manager = GamificationManager()
