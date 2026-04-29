"""
Progress Tracking & Motivational Messages Module
- Отслеживание реальных результатов
- Сравнение с целями
- Мотивационные сообщения
- Прогресс в цифрах
- Корректировки плана на основе результатов
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta
from decimal import Decimal
import logging

from database.manager import db_manager
from database.models import User, TrainingLog, NutritionLog, HealthMetric, DailyCalorieTarget
from modules.integrations.deepseek_api import deepseek_client

logger = logging.getLogger(__name__)


class ProgressTracker:
    """Track user progress and generate motivational messages."""

    def __init__(self):
        self.db = db_manager

    # ==================== PROGRESS ANALYSIS ====================

    def analyze_week_progress(self, user_id: int) -> Dict[str, Any]:
        """Analyze progress for the past week."""
        user = self.db.get_user(user_id)
        if not user:
            return {}

        # Get last 7 days data
        today = date.today()
        week_ago = today - timedelta(days=7)

        # Nutrition analysis
        nutrition_logs = self.db.get_nutrition_logs(user_id, week_ago, today)
        training_logs = self.db.get_training_logs(user_id, week_ago, today)
        health_metrics = self.db.get_health_metrics(user_id, week_ago, today)

        # Calculate stats
        avg_calories = self._calculate_avg_calories(nutrition_logs) if nutrition_logs else 0
        total_workouts = len(training_logs) if training_logs else 0
        weight_change = self._calculate_weight_change(user_id, days=7)

        # Get target
        target = self.db.get_daily_calorie_target(user_id)
        target_calories = target.daily_calories if target else 2000

        # Analysis
        calorie_adherence = (
            (avg_calories / target_calories * 100) if target_calories > 0 else 0
        )

        return {
            "period": "week",
            "dates": {"from": week_ago.isoformat(), "to": today.isoformat()},
            "nutrition": {
                "avg_calories": int(avg_calories),
                "target_calories": target_calories,
                "adherence_percent": round(calorie_adherence, 1),
                "days_logged": len(nutrition_logs)
            },
            "training": {
                "total_workouts": total_workouts,
                "target_frequency": 3,  # Should be from user.training_frequency
                "workout_adherence_percent": round((total_workouts / 3 * 100) if total_workouts <= 3 else 100, 1)
            },
            "health": {
                "weight_change_kg": round(weight_change, 2),
                "metrics_logged": len(health_metrics)
            }
        }

    def analyze_month_progress(self, user_id: int) -> Dict[str, Any]:
        """Analyze progress for the past month."""
        user = self.db.get_user(user_id)
        if not user:
            return {}

        today = date.today()
        month_ago = today - timedelta(days=30)

        nutrition_logs = self.db.get_nutrition_logs(user_id, month_ago, today)
        training_logs = self.db.get_training_logs(user_id, month_ago, today)

        avg_calories = self._calculate_avg_calories(nutrition_logs) if nutrition_logs else 0
        total_workouts = len(training_logs) if training_logs else 0
        weight_change = self._calculate_weight_change(user_id, days=30)

        return {
            "period": "month",
            "dates": {"from": month_ago.isoformat(), "to": today.isoformat()},
            "nutrition": {
                "avg_calories": int(avg_calories),
                "days_logged": len(nutrition_logs)
            },
            "training": {
                "total_workouts": total_workouts,
                "avg_per_week": round(total_workouts / 4.3, 1)
            },
            "health": {
                "weight_change_kg": round(weight_change, 2),
                "weight_change_percent": round((weight_change / user.weight_kg * 100) if user.weight_kg > 0 else 0, 2)
            }
        }

    # ==================== MOTIVATIONAL MESSAGES ====================

    async def generate_motivational_message(
        self, user_id: int, message_type: str = "daily"
    ) -> str:
        """Generate motivational message based on progress."""
        user = self.db.get_user(user_id)
        if not user:
            return "❌ Пользователь не найден"

        if message_type == "daily":
            return await self._generate_daily_motivation(user)
        elif message_type == "weekly":
            return await self._generate_weekly_motivation(user)
        elif message_type == "monthly":
            return await self._generate_monthly_motivation(user)
        else:
            return "❓ Неизвестный тип сообщения"

    async def _generate_daily_motivation(self, user: User) -> str:
        """Generate daily motivational message."""
        try:
            today = date.today()
            today_nutrition = self.db.get_nutrition_logs(user.id, today, today)
            today_training = self.db.get_training_logs(user.id, today, today)

            target = self.db.get_daily_calorie_target(user.id)
            target_calories = target.daily_calories if target else 2000

            total_logged_calories = sum(
                log.total_calories for log in today_nutrition
            ) if today_nutrition else 0

            logged_workouts = len(today_training) if today_training else 0

            # Build message
            msg = f"📊 **Сегодня ({today.strftime('%d.%m.%Y')})**\n\n"

            # Nutrition status
            if total_logged_calories > 0:
                remaining = target_calories - total_logged_calories
                percent = (total_logged_calories / target_calories * 100)

                msg += f"🍽️ **Питание:**\n"
                msg += f"Съедено: {total_logged_calories}/{target_calories} ккал"
                msg += f" ({percent:.0f}%)\n"

                if remaining > 0:
                    msg += f"Осталось: {remaining} ккал 💪\n\n"
                else:
                    msg += f"Превышение: {abs(remaining)} ккал ⚠️\n\n"
            else:
                msg += f"🍽️ **Питание:** Еще ничего не логировано\n"
                msg += f"Цели: {target_calories} ккал\n\n"

            # Training status
            if logged_workouts > 0:
                msg += f"💪 **Тренировки:** Отличная работа! ✅\n"
            else:
                msg += f"💪 **Тренировки:** Время тренировки? 🏋️\n"

            msg += f"\n💬 *Помни: маленькие шаги каждый день = большие результаты!*"

            return msg

        except Exception as e:
            logger.error(f"Error generating daily motivation: {e}")
            return "❓ Ошибка при генерировании сообщения"

    async def _generate_weekly_motivation(self, user: User) -> str:
        """Generate weekly motivational message."""
        try:
            progress = self.analyze_week_progress(user.id)

            if not progress:
                return "❌ Недостаточно данных"

            nutrition = progress.get("nutrition", {})
            training = progress.get("training", {})
            health = progress.get("health", {})

            # Base message
            msg = f"📈 **Итоги недели** ({progress['dates']['from']} - {progress['dates']['to']})\n\n"

            # Nutrition summary
            adherence = nutrition.get("adherence_percent", 0)
            msg += f"🍽️ **Питание:**\n"
            msg += f"Среднее: {nutrition.get('avg_calories', 0)}/{nutrition.get('target_calories', 0)} ккал/день\n"
            msg += f"Соблюдение плана: {adherence}%\n"

            if adherence >= 90:
                msg += f"🔥 Отличное соблюдение плана!\n\n"
            elif adherence >= 80:
                msg += f"✅ Хорошее соблюдение!\n\n"
            else:
                msg += f"⚠️ Нужно лучше следить за калориями\n\n"

            # Training summary
            workouts = training.get("total_workouts", 0)
            target_freq = training.get("target_frequency", 3)
            msg += f"💪 **Тренировки:**\n"
            msg += f"Выполнено: {workouts}/{target_freq} тренировок\n"

            if workouts >= target_freq:
                msg += f"💯 Все тренировки выполнены!\n\n"
            elif workouts > 0:
                msg += f"⚠️ Осталось: {target_freq - workouts} тренировок\n\n"
            else:
                msg += f"🔴 Тренировок не было\n\n"

            # Weight progress
            weight_change = health.get("weight_change_kg", 0)
            if weight_change < -0.5:
                msg += f"⬇️ **Вес:** {abs(weight_change):.1f} кг снизился! 🎉\n"
            elif weight_change > 0.5:
                msg += f"⬆️ **Вес:** {weight_change:.1f} кг увеличился\n"
            else:
                msg += f"➡️ **Вес:** Изменений нет\n"

            # Use AI for personalized message
            if deepseek_client:
                ai_msg = f"""Дай короткий (2-3 предложения) мотивационный отзыв на неделю пользователя:
                - Питание: {adherence}% соблюдения плана
                - Тренировки: {workouts} из {target_freq}
                - Вес: {weight_change:.1f} кг изменений
                Стиль: мотивирующий, позитивный, реалистичный
                """
                ai_response = await deepseek_client.chat(ai_msg)
                msg += f"\n💬 *{ai_response}*"

            return msg

        except Exception as e:
            logger.error(f"Error generating weekly motivation: {e}")
            return "❓ Ошибка"

    async def _generate_monthly_motivation(self, user: User) -> str:
        """Generate monthly motivational message."""
        try:
            progress = self.analyze_month_progress(user.id)

            if not progress:
                return "❌ Недостаточно данных"

            nutrition = progress.get("nutrition", {})
            training = progress.get("training", {})
            health = progress.get("health", {})

            msg = f"🏆 **Итоги месяца**\n\n"

            # Nutrition
            msg += f"🍽️ **Питание:**\n"
            msg += f"Среднее потребление: {nutrition.get('avg_calories', 0)} ккал/день\n"
            msg += f"Дней залогировано: {nutrition.get('days_logged', 0)}/30\n\n"

            # Training
            msg += f"💪 **Тренировки:**\n"
            msg += f"Всего тренировок: {training.get('total_workouts', 0)}\n"
            msg += f"В среднем в неделю: {training.get('avg_per_week', 0)}\n\n"

            # Weight change
            weight_change = health.get("weight_change_kg", 0)
            weight_percent = health.get("weight_change_percent", 0)

            if abs(weight_change) > 0.3:
                direction = "⬇️ " if weight_change < 0 else "⬆️ "
                msg += f"{direction}**Вес:** {abs(weight_change):.1f} кг ({abs(weight_percent):.1f}%)\n\n"

            # Achievement badges
            if training.get("total_workouts", 0) >= 12:
                msg += f"🏅 **Вы заслужили медаль за консистентность!**\n"
            if abs(weight_change) > 2:
                msg += f"🎯 **Серьезный прогресс в весе!**\n"
            if nutrition.get("days_logged", 0) >= 25:
                msg += f"📊 **Отличное отслеживание питания!**\n"

            msg += f"\n✨ *Продолжай в том же духе! Ты на правильном пути!*"

            return msg

        except Exception as e:
            logger.error(f"Error generating monthly motivation: {e}")
            return "❓ Ошибка"

    # ==================== RESULT PREDICTIONS ====================

    async def predict_results(self, user_id: int, weeks: int = 4) -> Dict[str, Any]:
        """Predict results based on current progress."""
        user = self.db.get_user(user_id)
        if not user:
            return {}

        try:
            # Get current data
            target = self.db.get_daily_calorie_target(user_id)
            target_calories = target.daily_calories if target else 2000

            # Get average adherence
            week_progress = self.analyze_week_progress(user_id)
            adherence = week_progress.get("nutrition", {}).get("adherence_percent", 100)

            # Calculate deficit/surplus
            avg_logged = week_progress.get("nutrition", {}).get("avg_calories", target_calories)
            daily_diff = (avg_logged - target_calories)  # If negative = deficit
            weekly_diff = daily_diff * 7
            monthly_diff = weekly_diff * (weeks / 4)

            # Weight prediction (1kg = 7700 kcal)
            predicted_weight_change = monthly_diff / 7700

            # Build prediction
            prediction = {
                "timeframe_weeks": weeks,
                "adherence_percent": adherence,
                "daily_calorie_diff": daily_diff,
                "predicted_weight_change_kg": round(predicted_weight_change, 1),
                "confidence_percent": min(adherence, 95),  # Based on adherence
            }

            # Add message
            if adherence >= 80:
                if predicted_weight_change < -0.5:
                    prediction["message"] = (
                        f"🎯 При соблюдении плана за {weeks} недель "
                        f"вес может снизиться на {abs(predicted_weight_change):.1f} кг!"
                    )
                elif predicted_weight_change > 0.5:
                    prediction["message"] = (
                        f"💪 При соблюдении плана за {weeks} недель "
                        f"вес может вырасти на {predicted_weight_change:.1f} кг мышц!"
                    )
                else:
                    prediction["message"] = (
                        f"↔️ При текущем плане вес останется примерно же, "
                        f"но улучшится состав тела!"
                    )
            else:
                prediction["message"] = (
                    f"⚠️ Нужно лучше соблюдать план для видимых результатов. "
                    f"Текущее соблюдение: {adherence}%"
                )

            return prediction

        except Exception as e:
            logger.error(f"Error predicting results: {e}")
            return {}

    # ==================== UTILITIES ====================

    def _calculate_avg_calories(self, logs: List) -> float:
        """Calculate average calories from logs."""
        if not logs:
            return 0
        total = sum(log.total_calories for log in logs if log.total_calories)
        return total / len(logs) if logs else 0

    def _calculate_weight_change(self, user_id: int, days: int = 7) -> float:
        """Calculate weight change in past N days."""
        try:
            today = date.today()
            start_date = today - timedelta(days=days)

            metrics = self.db.get_health_metrics(user_id, start_date, today)
            if not metrics or len(metrics) < 2:
                return 0

            first = metrics[0].weight_kg if metrics[0].weight_kg else 0
            last = metrics[-1].weight_kg if metrics[-1].weight_kg else 0

            return first - last  # Negative = weight loss

        except Exception as e:
            logger.error(f"Error calculating weight change: {e}")
            return 0


# Global instance
progress_tracker = ProgressTracker()
