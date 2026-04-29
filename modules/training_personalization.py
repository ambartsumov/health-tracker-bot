"""
Advanced training module for Health Bot.
Progressive overload tracking, RPE/RIR, personal records, deload management.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import date, datetime, timedelta
import logging

from database.manager import db_manager
from database.models import TrainingLog, PersonalRecord, User, DeloadSchedule

logger = logging.getLogger(__name__)


class TrainingPersonalizationManager:
    """Manager for advanced training personalization."""

    def __init__(self):
        self.db = db_manager

    # ==================== PROGRESSIVE OVERLOAD TRACKING ====================

    def calculate_training_volume(self, exercises: List[Dict]) -> float:
        """
        Calculate total training volume (tons).
        
        Args:
            exercises: List of exercises with sets, reps, weight
            
        Returns:
            Total volume in tons
        """
        total_volume = 0
        
        for exercise in exercises:
            sets = exercise.get("sets", 0)
            reps = exercise.get("reps", 0)
            weight = exercise.get("weight", 0)  # in kg
            
            total_volume += sets * reps * weight
        
        return round(total_volume / 1000, 2)  # Convert to tons

    def get_previous_workout(self, user_id: int, exercise_name: str = None) -> Optional[TrainingLog]:
        """
        Get user's previous workout.
        
        Args:
            user_id: User internal ID
            exercise_name: Optional specific exercise to find
            
        Returns:
            Previous TrainingLog or None
        """
        # Get last 2 workouts
        with self.db.session_scope() as session:
            query = session.query(TrainingLog).filter(
                TrainingLog.user_id == user_id
            ).order_by(TrainingLog.date.desc()).limit(2)
            
            workouts = query.all()
            
            if len(workouts) < 2:
                return workouts[0] if workouts else None
            
            # If looking for specific exercise, find it
            if exercise_name:
                for workout in workouts:
                    for muscle_group in (workout.muscle_groups or []):
                        for exercise in (muscle_group.get("exercises", []) or []):
                            if exercise_name.lower() in exercise.get("name", "").lower():
                                return workout
            
            return workouts[0]

    def calculate_volume_change(self, user_id: int, current_volume: float) -> float:
        """
        Calculate volume change vs last workout.
        
        Returns:
            Percentage change (-100 to +100)
        """
        previous = self.get_previous_workout(user_id)
        
        if not previous or previous.total_volume == 0:
            return 0
        
        change = ((current_volume - previous.total_volume) / previous.total_volume) * 100
        return round(change, 1)

    def get_progressive_overload_suggestion(
        self,
        user_id: int,
        exercise_name: str,
        current_sets: int,
        current_reps: int,
        current_weight: float
    ) -> Dict[str, Any]:
        """
        Get progressive overload suggestion for next workout.
        
        Based on:
        - If reps >= target: increase weight
        - If reps < target but close: maintain weight, try more reps
        - If reps << target: reduce weight or deload
        
        Returns:
            Suggestion dictionary
        """
        # Get PR for this exercise
        pr = self.db.get_pr_for_exercise(user_id, exercise_name)
        
        # Get last workout for this exercise
        previous = self.get_previous_workout(user_id, exercise_name)
        
        suggestion = {
            "exercise": exercise_name,
            "current": {
                "sets": current_sets,
                "reps": current_reps,
                "weight": current_weight
            },
            "recommended": {
                "sets": current_sets,
                "reps": current_reps,
                "weight": current_weight
            },
            "action": "maintain",
            "message": ""
        }
        
        # If hit rep target, suggest weight increase
        if current_reps >= 8:
            weight_increase = 2.5 if current_weight < 100 else 5.0
            suggestion["recommended"]["weight"] = current_weight + weight_increase
            suggestion["recommended"]["reps"] = max(4, current_reps - 2)  # Reset reps lower
            suggestion["action"] = "increase_weight"
            suggestion["message"] = f"💪 Отлично! Увеличь вес на {weight_increase}кг (до {current_weight + weight_increase}кг)"
        
        # If reps are low, suggest maintaining weight
        elif current_reps < 4:
            suggestion["recommended"]["reps"] = current_reps + 1
            suggestion["action"] = "build_reps"
            suggestion["message"] = f"📈 Попробуй сделать на 1 повторение больше ({current_reps + 1}) с тем же весом"
        
        # Moderate reps - suggest small progression
        else:
            suggestion["recommended"]["reps"] = current_reps + 1
            suggestion["action"] = "add_reps"
            suggestion["message"] = f"🎯 Цель: {current_reps + 1} повторений. Когда достигнешь 8+ — добавь вес"
        
        # Check if this would be a PR
        if pr:
            if current_weight > pr.max_weight:
                suggestion["is_pr_potential"] = True
                suggestion["message"] += f"\n🏆 Это может быть новый рекорд! (текущий: {pr.max_weight}кг)"
        
        return suggestion

    # ==================== RPE/RIR TRACKING ====================

    def calculate_rpe_from_reps(
        self,
        performed_reps: int,
        estimated_max_reps: int
    ) -> float:
        """
        Calculate RPE based on reps performed vs estimated max.
        
        RPE Scale:
        - 10: Maximum effort, 0 reps in reserve
        - 9: 1 rep in reserve
        - 8: 2 reps in reserve
        - 7: 3 reps in reserve
        etc.
        
        Returns:
            RPE value (1-10)
        """
        if performed_reps >= estimated_max_reps:
            return 10.0
        
        reps_in_reserve = estimated_max_reps - performed_reps
        rpe = 10 - reps_in_reserve
        
        return max(1.0, min(10.0, rpe))

    def log_workout_with_rpe(
        self,
        user_id: int,
        duration_minutes: int,
        muscle_groups: List[Dict],
        average_rpe: float,
        rir: int = None,
        training_type: str = "strength",
        notes: str = ""
    ) -> Tuple[bool, TrainingLog, str]:
        """
        Log workout with RPE/RIR data.
        
        Args:
            user_id: User internal ID
            duration_minutes: Workout duration
            muscle_groups: List of muscle groups with exercises
            average_rpe: Average RPE for the workout (1-10)
            rir: Reps in Reserve (0-5)
            training_type: Type of training
            notes: Additional notes
            
        Returns:
            Tuple of (success, training_log, message)
        """
        try:
            # Calculate total volume
            total_volume = self.calculate_training_volume([
                ex for mg in muscle_groups for ex in mg.get("exercises", [])
            ])
            
            # Calculate volume change
            volume_change = self.calculate_volume_change(user_id, total_volume)
            
            # Check for PR
            is_pr_day = self._check_for_prs(user_id, muscle_groups)
            
            # Calculate RIR if not provided
            if rir is None:
                rir = max(0, int(10 - average_rpe))
            
            training_log = self.db.add_training_log(
                user_id=user_id,
                date=date.today(),
                duration_minutes=duration_minutes,
                training_type=training_type,
                muscle_groups=muscle_groups,
                total_volume=total_volume,
                average_rpe=average_rpe,
                rir=rir,
                volume_change_percent=volume_change,
                is_pr_day=is_pr_day,
                notes=notes
            )
            
            # Update deload schedule
            self._update_deload_schedule(user_id)
            
            message = f"✅ Тренировка записана!\n"
            message += f"📊 Объем: {total_volume} тонн\n"
            if volume_change != 0:
                message += f"📈 Изменение: {volume_change:+.1f}%\n"
            if is_pr_day:
                message += f"🏆 ЛИЧНЫЙ РЕКОРД!\n"
            if average_rpe >= 9:
                message += f"⚠️ Очень высокая интенсивность! Восстанавливайся хорошо."
            
            return True, training_log, message
            
        except Exception as e:
            logger.error(f"Error logging workout with RPE: {e}")
            return False, None, f"❌ Ошибка: {e}"

    def _check_for_prs(self, user_id: int, muscle_groups: List[Dict]) -> bool:
        """Check if any exercise was a PR."""
        is_pr_day = False
        
        for muscle_group in muscle_groups:
            for exercise in (muscle_group.get("exercises", []) or []):
                name = exercise.get("name", "")
                weight = exercise.get("weight", 0)
                reps = exercise.get("reps", 1)
                
                # Update PR
                if weight > 0:
                    pr = self.db.add_personal_record(
                        user_id=user_id,
                        exercise_name=name,
                        max_weight=weight,
                        reps=reps
                    )
                    if pr and pr.max_weight == weight:
                        is_pr_day = True
        
        return is_pr_day

    def get_workout_intensity_analysis(self, rpe: float, rir: int) -> Dict[str, str]:
        """
        Analyze workout intensity.
        
        Returns:
            Analysis dictionary
        """
        if rpe >= 9.5:
            intensity = "maximal"
            advice = "⚠️ Максимальная нагрузка! Следующая тренировка должна быть легче."
        elif rpe >= 8:
            intensity = "high"
            advice = "💪 Хорошая интенсивность для прогресса."
        elif rpe >= 6:
            intensity = "moderate"
            advice = "👍 Умеренная интенсивность. Можно добавить вес."
        else:
            intensity = "low"
            advice = "📊 Низкая интенсивность. Увеличь нагрузку для прогресса."
        
        if rir == 0:
            advice += " В следующий раз оставь 1-2 повторения в запасе."
        elif rir >= 3:
            advice += " Ты мог бы сделать больше! Увеличь вес."
        
        return {
            "intensity": intensity,
            "rpe_rating": rpe,
            "rir_rating": rir,
            "advice": advice
        }

    # ==================== DELOAD MANAGEMENT ====================

    def _update_deload_schedule(self, user_id: int):
        """Update deload schedule after workout."""
        # Get current cycle
        current = self.db.get_current_deload_week(user_id)
        
        if not current:
            # Start new cycle
            self.db.add_deload_schedule(
                user_id=user_id,
                cycle_start_date=date.today(),
                cycle_week_number=1,
                is_deload_week=False
            )
        else:
            # Check if we need to advance week
            weeks_since_start = (date.today() - current.cycle_start_date).days // 7
            new_week = weeks_since_start + 1
            
            # Deload every 6 weeks
            is_deload = (new_week % 6) == 0
            
            if new_week > current.cycle_week_number:
                self.db.add_deload_schedule(
                    user_id=user_id,
                    cycle_start_date=date.today(),
                    cycle_week_number=new_week,
                    is_deload_week=is_deload
                )

    def get_deload_status(self, user_id: int) -> Dict[str, Any]:
        """
        Get current deload status.
        
        Returns:
            Deload status dictionary
        """
        current = self.db.get_current_deload_week(user_id)
        
        if not current:
            return {
                "week": 1,
                "is_deload_week": False,
                "weeks_until_deload": 5,
                "message": "📅 Начни тренировочный цикл!"
            }
        
        weeks_until_deload = 6 - (current.cycle_week_number % 6)
        if weeks_until_deload == 6:
            weeks_until_deload = 0
        
        message = f"📊 Неделя {current.cycle_week_number} из 6\n"
        
        if current.is_deload_week:
            message += "⚠️ СЕЙЧАС DELOAD WEEK!\n"
            message += "📉 Снизь объем на 50% и веса на 20-30%\n"
            message += "🎯 Цель: активное восстановление"
        else:
            message += f"📈 Обычная тренировочная неделя\n"
            if weeks_until_deload == 1:
                message += "⚠️ Следующая неделя — разгрузочная!"
            else:
                message += f"⏰ До разгрузки: {weeks_until_deload} нед."
        
        return {
            "week": current.cycle_week_number,
            "is_deload_week": current.is_deload_week,
            "weeks_until_deload": weeks_until_deload,
            "message": message
        }

    def get_deload_recommendations(self, user_id: int) -> List[str]:
        """
        Get deload week recommendations.
        
        Returns:
            List of recommendations
        """
        status = self.get_deload_status(user_id)
        
        if not status["is_deload_week"]:
            return []
        
        return [
            "📉 Снизь рабочий вес на 20-30%",
            "🔽 Уменьши количество подходов на 40-50%",
            "🏃 Добавь легкое кардио и мобильность",
            "😴 Удели больше внимания сну и питанию",
            "🧘 Рассмотрим массаж или сауну",
            "📊 Не тестируй максимумы на этой неделе"
        ]

    # ==================== PERSONAL RECORDS ====================

    def get_all_prs(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all personal records for user."""
        records = self.db.get_personal_records(user_id)
        
        prs = []
        for pr in records:
            # Calculate estimated 1RM using Epley formula
            estimated_1rm = pr.max_weight * (1 + pr.reps / 30)
            
            prs.append({
                "exercise": pr.exercise_name,
                "max_weight": pr.max_weight,
                "reps": pr.reps,
                "date": pr.date_achieved.isoformat(),
                "estimated_1rm": round(estimated_1rm, 1)
            })
        
        return sorted(prs, key=lambda x: x["estimated_1rm"], reverse=True)

    def check_pr_achieved(
        self,
        user_id: int,
        exercise_name: str,
        weight: float,
        reps: int = 1
    ) -> Tuple[bool, Optional[PersonalRecord]]:
        """
        Check if a new PR was achieved.
        
        Returns:
            Tuple of (is_new_pr, personal_record)
        """
        existing_pr = self.db.get_pr_for_exercise(user_id, exercise_name)
        
        if not existing_pr:
            # First record
            pr = self.db.add_personal_record(user_id, exercise_name, weight, reps)
            return True, pr
        
        if weight > existing_pr.max_weight:
            # New PR!
            pr = self.db.add_personal_record(user_id, exercise_name, weight, reps)
            return True, pr
        
        return False, existing_pr

    def get_pr_progression(self, user_id: int, exercise_name: str) -> List[Dict]:
        """
        Get PR progression history for an exercise.
        
        Returns:
            List of PR records with dates
        """
        # This would need a history table - for now return current PR
        pr = self.db.get_pr_for_exercise(user_id, exercise_name)
        
        if not pr:
            return []
        
        return [{
            "exercise": pr.exercise_name,
            "weight": pr.max_weight,
            "reps": pr.reps,
            "date": pr.date_achieved.isoformat()
        }]


# Global instance
training_personalization_manager = TrainingPersonalizationManager()
