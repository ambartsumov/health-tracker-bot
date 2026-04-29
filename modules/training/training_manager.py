"""
Training tracking module for Health Bot.
Handles workout logging, daily surveys, and training analysis.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import date, datetime, timedelta
import logging

from database.manager import db_manager
from database.models import TrainingLog, User, ScheduleItem

logger = logging.getLogger(__name__)


class TrainingManager:
    """Manager for training tracking and analysis."""
    
    def __init__(self):
        self.db = db_manager
    
    # Muscle groups for tracking
    MUSCLE_GROUPS = {
        "chest": "Грудные мышцы",
        "back": "Спина",
        "shoulders": "Плечи",
        "biceps": "Бицепсы",
        "triceps": "Трицепсы",
        "forearms": "Предплечья",
        "abs": "Пресс",
        "quads": "Квадрицепсы",
        "hamstrings": "Бицепсы бедер",
        "glutes": "Ягодицы",
        "calves": "Икры",
        "traps": "Трапеции",
        "lats": "Широчайшие",
        "core": "Кор"
    }
    
    # Common exercises by muscle group
    EXERCISES_BY_MUSCLE = {
        "chest": ["Жим лежа", "Жим на наклонной", "Отжимания", "Разводка", "Жим в хаммере"],
        "back": ["Становая тяга", "Подтягивания", "Тяга штанги в наклоне", "Тяга верхнего блока"],
        "shoulders": ["Жим штанги стоя", "Махи гантелями", "Тяга к подбородку", "Жим в Смите"],
        "biceps": ["Подъем штанги на бицепс", "Молотки", "Подъем гантелей сидя"],
        "triceps": ["Французский жим", "Отжимания на брусьях", "Разгибания на блоке"],
        "quads": ["Приседания", "Жим ногами", "Разгибания ног", "Выпады"],
        "hamstrings": ["Румынская тяга", "Сгибания ног", "Гиперэкстензия"],
        "glutes": ["Ягодичный мост", "Отведения ног", "Приседания сумо"],
        "abs": ["Скручивания", "Планка", "Подъем ног", "Русский твист"]
    }
    
    def log_training_from_survey(
        self,
        user_id: int,
        survey_data: Dict[str, Any]
    ) -> Tuple[bool, TrainingLog, str]:
        """
        Log training from daily survey responses.
        
        Args:
            user_id: User internal ID
            survey_data: Survey responses containing:
                - trained: bool (whether user trained)
                - duration_minutes: int
                - muscle_groups: list of muscle group data
                - notes: optional string
        
        Returns:
            Tuple of (success, training_log, message)
        """
        try:
            if not survey_data.get('trained', False):
                return False, None, "❌ Тренировка не записана (пользователь не тренировался)"
            
            duration = survey_data.get('duration_minutes', 0)
            muscle_groups = survey_data.get('muscle_groups', [])
            notes = survey_data.get('notes', '')
            
            # Calculate total volume
            total_volume = self._calculate_training_volume(muscle_groups)
            
            # Create training log
            training_log = self.db.add_training_log(
                user_id=user_id,
                date=date.today(),
                duration_minutes=duration,
                muscle_groups=muscle_groups,
                calories_burned=self._estimate_calories_burned(duration, muscle_groups),
                notes=notes,
                is_from_daily_survey=True
            )
            
            return True, training_log, "✅ Тренировка записана"
            
        except Exception as e:
            logger.error(f"Error logging training from survey: {e}")
            return False, None, f"❌ Ошибка при записи тренировки: {e}"
    
    def _calculate_training_volume(self, muscle_groups: List[Dict]) -> float:
        """Calculate total training volume (weight × reps × sets)."""
        total_volume = 0.0
        
        for group in muscle_groups:
            exercises = group.get('exercises', [])
            for exercise in exercises:
                weight = exercise.get('weight', 0)
                reps = exercise.get('reps', 0)
                sets = exercise.get('sets', 0)
                total_volume += weight * reps * sets
        
        return total_volume
    
    def _estimate_calories_burned(self, duration_minutes: int, muscle_groups: List[Dict]) -> float:
        """Estimate calories burned during training."""
        # Base MET values for different training intensities
        base_met = 6.0  # Moderate weight training
        
        # Adjust based on volume
        total_sets = sum(
            len(group.get('exercises', [])) * 
            sum(ex.get('sets', 0) for ex in group.get('exercises', []))
            for group in muscle_groups
        )
        
        if total_sets > 20:
            base_met = 8.0  # High intensity
        elif total_sets > 10:
            base_met = 7.0  # Moderate-high intensity
        
        # Rough estimate: MET × weight (kg) × duration (hours)
        # Using average weight of 80kg for estimation
        hours = duration_minutes / 60
        return round(base_met * 80 * hours, 0)
    
    def get_training_log(self, user_id: int, target_date: date = None) -> Optional[TrainingLog]:
        """Get training log for specific date."""
        if target_date is None:
            target_date = date.today()
        
        return self.db.get_training_log(user_id, target_date)
    
    def has_trained_today(self, user_id: int) -> bool:
        """Check if user has logged training today."""
        log = self.get_training_log(user_id)
        return log is not None
    
    def get_training_schedule_for_day(
        self,
        user_id: int,
        day_of_week: str = None
    ) -> Optional[ScheduleItem]:
        """
        Get scheduled training for a specific day of week.
        
        Args:
            user_id: User internal ID
            day_of_week: Day abbreviation (mon, tue, etc.) or None for today
        
        Returns:
            ScheduleItem if training is scheduled, None otherwise
        """
        if day_of_week is None:
            day_map = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
            day_of_week = day_map[date.today().weekday()]
        
        schedule = self.db.get_user_schedule(user_id)
        
        for item in schedule:
            if item.item_type == 'training' and day_of_week in (item.days_of_week or []):
                return item
        
        return None
    
    def should_ask_about_training(self, user_id: int) -> bool:
        """
        Check if we should ask user about training today.
        Based on schedule and whether already logged.
        """
        # Don't ask if already logged
        if self.has_trained_today(user_id):
            return False
        
        # Check if training is scheduled for today
        scheduled_training = self.get_training_schedule_for_day(user_id)
        if scheduled_training:
            return True
        
        return False
    
    def get_daily_survey_questions(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Generate daily training survey questions.
        
        Returns:
            List of question dictionaries
        """
        questions = [
            {
                "id": "trained_today",
                "type": "boolean",
                "question": "💪 Тренировался ли ты сегодня?",
                "required": True
            }
        ]
        
        # If user trained, add follow-up questions
        questions.extend([
            {
                "id": "duration",
                "type": "number",
                "question": "⏱️ Сколько длилась тренировка (в минутах)?",
                "required": True,
                "condition": {"field": "trained_today", "equals": True}
            },
            {
                "id": "muscle_groups",
                "type": "multiple_select",
                "question": "🎯 Какие группы мышц ты прорабатывал?",
                "options": [
                    {"value": "chest", "label": "Грудные"},
                    {"value": "back", "label": "Спина"},
                    {"value": "shoulders", "label": "Плечи"},
                    {"value": "arms", "label": "Руки"},
                    {"value": "legs", "label": "Ноги"},
                    {"value": "abs", "label": "Пресс"}
                ],
                "required": True,
                "condition": {"field": "trained_today", "equals": True}
            },
            {
                "id": "notes",
                "type": "text",
                "question": "📝 Есть ли что добавить о тренировке? (опционально)",
                "required": False,
                "condition": {"field": "trained_today", "equals": True}
            }
        ])
        
        return questions
    
    def get_weekly_training_summary(
        self,
        user_id: int,
        week_start: date = None
    ) -> Dict[str, Any]:
        """
        Get weekly training summary.
        
        Args:
            user_id: User internal ID
            week_start: Start of week (default: most recent Monday)
        
        Returns:
            Dictionary with weekly training statistics
        """
        if week_start is None:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
        
        week_end = week_start + timedelta(days=6)
        
        with self.db.session_scope() as session:
            logs = session.query(TrainingLog).filter(
                TrainingLog.user_id == user_id,
                TrainingLog.date >= week_start,
                TrainingLog.date <= week_end
            ).all()
        
        if not logs:
            return {
                'week_start': week_start.isoformat(),
                'week_end': week_end.isoformat(),
                'total_workouts': 0,
                'total_duration_minutes': 0,
                'total_volume': 0,
                'total_calories_burned': 0,
                'muscle_groups_trained': {},
                'workout_days': []
            }
        
        # Aggregate data
        total_duration = sum(log.duration_minutes for log in logs)
        total_volume = sum(self._calculate_training_volume(log.muscle_groups or []) for log in logs)
        total_calories = sum(log.calories_burned or 0 for log in logs)
        
        # Muscle groups frequency
        muscle_frequency = {}
        for log in logs:
            for group in (log.muscle_groups or []):
                group_name = group.get('group', 'unknown')
                muscle_frequency[group_name] = muscle_frequency.get(group_name, 0) + 1
        
        # Workout days
        workout_days = [
            {
                'date': log.date.isoformat(),
                'duration_minutes': log.duration_minutes,
                'muscle_groups': [g.get('group', '') for g in (log.muscle_groups or [])],
                'notes': log.notes
            }
            for log in logs
        ]
        
        return {
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
            'total_workouts': len(logs),
            'total_duration_minutes': total_duration,
            'avg_duration_minutes': round(total_duration / len(logs), 0),
            'total_volume': round(total_volume, 0),
            'total_calories_burned': round(total_calories, 0),
            'muscle_groups_trained': muscle_frequency,
            'workout_days': workout_days
        }
    
    def get_monthly_training_summary(self, user_id: int, year: int = None, month: int = None) -> Dict[str, Any]:
        """Get monthly training summary."""
        from datetime import timedelta
        
        if year is None or month is None:
            today = date.today()
            year = today.year
            month = today.month
        
        # First and last day of month
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)
        
        with self.db.session_scope() as session:
            logs = session.query(TrainingLog).filter(
                TrainingLog.user_id == user_id,
                TrainingLog.date >= month_start,
                TrainingLog.date <= month_end
            ).all()
        
        total_workouts = len(logs)
        total_duration = sum(log.duration_minutes for log in logs) if logs else 0
        
        return {
            'year': year,
            'month': month,
            'month_start': month_start.isoformat(),
            'month_end': month_end.isoformat(),
            'total_workouts': total_workouts,
            'total_duration_minutes': total_duration,
            'avg_workouts_per_week': round(total_workouts / 4.3, 1),
            'total_calories_burned': round(sum(log.calories_burned or 0 for log in logs), 0),
            'consistency_rate': round((total_workouts / 12) * 100, 0)  # Assuming 12 workouts/month goal
        }
    
    def get_training_recommendations(self, user_id: int) -> List[str]:
        """
        Generate training recommendations based on history.
        
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        # Get user
        user = self.db.get_user_by_id(user_id)
        if not user:
            return recommendations
        
        # Get recent training history (last 4 weeks)
        four_weeks_ago = date.today() - timedelta(weeks=4)
        
        with self.db.session_scope() as session:
            recent_logs = session.query(TrainingLog).filter(
                TrainingLog.user_id == user_id,
                TrainingLog.date >= four_weeks_ago
            ).order_by(TrainingLog.date.desc()).all()
        
        if not recent_logs:
            recommendations.append("💡 Начни тренироваться регулярно для достижения целей")
            return recommendations
        
        # Analyze frequency
        workouts_last_week = len([
            log for log in recent_logs 
            if log.date >= date.today() - timedelta(weeks=1)
        ])
        
        if workouts_last_week < 2:
            recommendations.append("📈 Попробуй увеличить частоту тренировок до 3 раз в неделю")
        elif workouts_last_week > 5:
            recommendations.append("😌 Убедись, что ты достаточно отдыхаешь для восстановления")
        
        # Analyze muscle group balance
        muscle_frequency = {}
        for log in recent_logs:
            for group in (log.muscle_groups or []):
                group_name = group.get('group', 'unknown')
                muscle_frequency[group_name] = muscle_frequency.get(group_name, 0) + 1
        
        if muscle_frequency:
            max_trained = max(muscle_frequency.values())
            min_trained = min(muscle_frequency.values())
            
            if max_trained > min_trained * 3:
                undertrained = [g for g, c in muscle_frequency.items() if c == min_trained]
                recommendations.append(
                    f"⚖️ Обрати внимание на отстающие группы: {', '.join(undertrained)}"
                )
        
        # Check progression
        if len(recent_logs) >= 4:
            first_half = recent_logs[len(recent_logs)//2:]
            second_half = recent_logs[:len(recent_logs)//2]
            
            avg_volume_first = sum(
                self._calculate_training_volume(log.muscle_groups or []) 
                for log in first_half
            ) / len(first_half)
            
            avg_volume_second = sum(
                self._calculate_training_volume(log.muscle_groups or []) 
                for log in second_half
            ) / len(second_half)
            
            if avg_volume_second <= avg_volume_first:
                recommendations.append("📊 Попробуй увеличить тренировочный объем для прогресса")
        
        return recommendations
    
    def import_from_samsung_health(
        self,
        user_id: int,
        samsung_data: Dict[str, Any],
        workout_date: date
    ) -> Tuple[bool, Optional[TrainingLog], str]:
        """
        Import training data from Samsung Health.
        
        Args:
            user_id: User internal ID
            samsung_data: Data from Samsung Health API
            workout_date: Date of workout
        
        Returns:
            Tuple of (success, training_log, message)
        """
        try:
            # Check if already imported
            existing = self.get_training_log(user_id, workout_date)
            if existing and existing.is_from_samsung_health:
                return False, existing, "ℹ️ Тренировка уже импортирована из Samsung Health"
            
            # Parse Samsung Health data
            duration = samsung_data.get('duration_minutes', 0)
            workout_type = samsung_data.get('workout_type', 'general')
            calories = samsung_data.get('calories_burned', 0)
            
            # Map Samsung Health workout types to muscle groups
            muscle_group_mapping = {
                'running': ['quads', 'hamstrings', 'calves', 'glutes'],
                'cycling': ['quads', 'hamstrings', 'calves'],
                'weight_training': ['chest', 'back', 'shoulders', 'arms'],
                'swimming': ['chest', 'back', 'shoulders', 'core'],
                'yoga': ['core', 'shoulders', 'back'],
                'general': []
            }
            
            muscle_groups = [
                {'group': mg, 'exercises': []} 
                for mg in muscle_group_mapping.get(workout_type, [])
            ]
            
            # Create log
            training_log = self.db.add_training_log(
                user_id=user_id,
                date=workout_date,
                duration_minutes=duration,
                muscle_groups=muscle_groups,
                calories_burned=calories,
                notes=f"Импортировано из Samsung Health ({workout_type})",
                is_from_samsung_health=True
            )
            
            return True, training_log, "✅ Тренировка импортирована из Samsung Health"
            
        except Exception as e:
            logger.error(f"Error importing from Samsung Health: {e}")
            return False, None, f"❌ Ошибка импорта: {e}"


# Global instance
training_manager = TrainingManager()
