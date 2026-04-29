"""
Onboarding Integration Module
- Полная интеграция SmartOnboarding
- Генерация первого плана питания
- Генерация первой программы тренировок
- DeepSeek персонализированные рекомендации
- Отслеживание результатов
- Мотивация пользователя
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta
import logging
import json

from database.manager import db_manager
from database.models import User, MealSchedule, TrainingLog, DailyCalorieTarget
from modules.smart_onboarding import SmartOnboardingHandler, Goal
from modules.nutrition.nutrition_manager import nutrition_manager
from modules.training.training_manager import training_manager
from modules.integrations.deepseek_api import deepseek_client
from modules.profile import profile_manager

logger = logging.getLogger(__name__)


class OnboardingIntegrationManager:
    """
    Полная интеграция онбординга с генерацией планов и рекомендаций.
    
    Этапы:
    1. Сбор данных (Phase 1-3 SmartOnboarding)
    2. Создание профиля пользователя в БД
    3. Генерация плана питания
    4. Генерация программы тренировок
    5. Получение AI рекомендаций
    6. Запуск напоминаний
    """

    def __init__(self):
        self.sessions: Dict[int, SmartOnboardingHandler] = {}

    # ==================== PHASE TRANSITIONS ====================

    async def get_next_question(self, user_id: int) -> tuple[str, Optional[List[List[str]]]]:
        """Get next onboarding question."""
        handler = self.sessions.get(user_id)
        if not handler:
            handler = SmartOnboardingHandler(str(user_id))
            self.sessions[user_id] = handler

        return handler.get_question_with_buttons()

    async def process_button_answer(
        self, user_id: int, button_text: str
    ) -> tuple[bool, Optional[str], Optional[Dict]]:
        """
        Process button answer.
        Returns: (success, message, phase_results)
        """
        handler = self.sessions.get(user_id)
        if not handler:
            return False, "❌ Сессия не найдена", None

        success, msg = handler.process_button_answer(button_text)

        if not success:
            return False, msg, None

        # Check phase transitions
        if msg == "PHASE_1_COMPLETE":
            results = handler.get_phase_1_results()
            return True, "PHASE_1_COMPLETE", results

        elif msg == "PHASE_2_COMPLETE":
            results = handler.phase_2_results
            return True, "PHASE_2_COMPLETE", results

        return True, msg, None

    async def process_text_answer(
        self, user_id: int, text: str
    ) -> tuple[bool, Optional[str]]:
        """Process text answer."""
        handler = self.sessions.get(user_id)
        if not handler:
            return False, "❌ Сессия не найдена"

        success, msg = handler.process_text_answer(text)
        return success, msg

    async def on_phase_1_complete(
        self, user_id: int, results: Dict[str, Any]
    ) -> str:
        """
        After Phase 1 complete - show results and ask to continue.
        Returns: motivational message with results
        """
        handler = self.sessions.get(user_id)
        if not handler:
            return "❌ Ошибка"

        data = handler.collected_data

        # Create motivational message
        msg = (
            f"🎉 **Фаза 1 завершена! Твои метрики:**\n\n"
            f"📊 **BMI:** {results['bmi']}\n"
            f"🎯 **Статус:** {self._get_bmi_description(results['bmi_status'])}\n\n"
            f"**Энергия (TDEE = BMR × коэффициент активности):**\n"
            f"💪 BMR (базовый метаболизм): {results['bmr']} ккал\n"
            f"🔥 TDEE (сжигаемо в день): {results['tdee']} ккал\n"
            f"✅ **Для твоей цели:** {results['adjusted_tdee']} ккал/день\n\n"
            f"**Макронутриенты (идеально для {data.get('goal').value}):**\n"
            f"🍗 Белки: {results['macros']['protein_g']}г ({results['macros']['protein_g']*4} ккал)\n"
            f"🧈 Жиры: {results['macros']['fat_g']}г ({results['macros']['fat_g']*9} ккал)\n"
            f"🍞 Углеводы: {results['macros']['carbs_g']}г ({results['macros']['carbs_g']*4} ккал)\n\n"
            f"💬 **Совет:** Это твой персональный план! Считая калории первые 2 недели, "
            f"ты научишься интуитивно чувствовать нужное количество еды.\n\n"
            f"🚀 **Далее:** Ответь на вопросы о здоровье для детализирован рекомендаций"
        )

        return msg

    async def on_phase_2_complete(self, user_id: int) -> str:
        """After Phase 2 complete."""
        handler = self.sessions.get(user_id)
        if not handler:
            return "❌ Ошибка"

        data = handler.collected_data
        health_conditions = data.get("health_conditions", "Нет")

        msg = (
            f"✅ **Этап здоровья пройден!**\n\n"
            f"Хронические заболевания: {health_conditions}\n"
            f"Лекарства: {data.get('medications', 'Нет')}\n\n"
            f"Это поможет мне давать безопасные рекомендации.\n\n"
            f"🏋️ **Переходим к тренировкам!**"
        )

        return msg

    async def on_onboarding_complete(
        self, user_id: int, telegram_user_id: int
    ) -> Dict[str, Any]:
        """
        Complete onboarding and create user profile.
        Returns: completion data with next steps
        """
        handler = self.sessions.get(user_id)
        if not handler:
            return {"error": "Session not found"}

        data = handler.get_collected_data()
        results = handler.get_phase_1_results()

        try:
            # 1️⃣ Create user in database
            user = await self._create_user_profile(telegram_user_id, data, results)

            if not user:
                return {"error": "Failed to create user"}

            # 2️⃣ Generate nutrition plan
            nutrition_plan = await self._generate_nutrition_plan(user, data, results)

            # 3️⃣ Generate training program
            training_program = await self._generate_training_program(user, data, results)

            # 4️⃣ Get AI recommendations
            ai_recommendations = await self._generate_ai_recommendations(user, data, results)

            # 5️⃣ Setup reminders
            await self._setup_reminders(user)

            # Clean up session
            if user_id in self.sessions:
                del self.sessions[user_id]

            return {
                "success": True,
                "user_id": user.id,
                "telegram_id": telegram_user_id,
                "profile": {
                    "name": user.name,
                    "bmi": results["bmi"],
                    "tdee": results["adjusted_tdee"],
                },
                "nutrition_plan": nutrition_plan,
                "training_program": training_program,
                "ai_recommendations": ai_recommendations,
            }

        except Exception as e:
            logger.error(f"Error completing onboarding: {e}")
            return {"error": str(e)}

    # ==================== USER PROFILE CREATION ====================

    async def _create_user_profile(
        self, telegram_user_id: int, data: Dict, results: Dict
    ) -> Optional[User]:
        """Create user profile in database."""
        try:
            # Map goal
            goal_map = {
                "weight_loss": "weight_loss",
                "muscle_gain": "muscle_gain",
                "health": "aesthetic_and_health",
                "maintenance": "maintenance",
                "recomposition": "recomposition",
            }

            goal = data.get("goal")
            goal_str = goal.value if hasattr(goal, "value") else goal

            # Create user
            user = db_manager.create_user(
                telegram_id=str(telegram_user_id),
                name=data.get("name", "User"),
                date_of_birth=data.get("date_of_birth"),
                weight_kg=data.get("weight_kg"),
                height_cm=data.get("height_cm"),
                goal=goal_str,
                is_default_user=False,
            )

            # Add health conditions
            conditions = data.get("health_conditions", [])
            if conditions and conditions != "✅ Нет":
                db_manager.update_user(user.id, health_conditions=conditions)

            # Set calorie target
            db_manager.set_daily_calorie_target(
                user_id=user.id,
                calories=results["adjusted_tdee"],
                protein_g=results["macros"]["protein_g"],
                fat_g=results["macros"]["fat_g"],
                carbs_g=results["macros"]["carbs_g"],
            )

            logger.info(f"Created user profile: {user.name} (ID: {user.id})")
            return user

        except Exception as e:
            logger.error(f"Error creating user profile: {e}")
            return None

    # ==================== NUTRITION PLAN GENERATION ====================

    async def _generate_nutrition_plan(
        self, user: User, data: Dict, results: Dict
    ) -> Dict[str, Any]:
        """Generate first week nutrition plan."""
        try:
            goal = data.get("goal")
            tdee = results["adjusted_tdee"]
            macros = results["macros"]

            # Get meals per day (default 4)
            meals_per_day = 4

            # Calculate calories per meal
            meal_calories = [
                {"type": "Завтрак", "percentage": 0.25, "time": "08:00"},
                {"type": "Полдник", "percentage": 0.15, "time": "11:30"},
                {"type": "Обед", "percentage": 0.35, "time": "14:00"},
                {"type": "Ужин", "percentage": 0.25, "time": "19:00"},
            ]

            plan = {
                "week_1": [],
                "tdee": tdee,
                "macros": macros,
                "meals": [],
            }

            # Generate sample meals
            for meal in meal_calories:
                meal_kcal = int(tdee * meal["percentage"])
                meal_data = {
                    "type": meal["type"],
                    "time": meal["time"],
                    "target_kcal": meal_kcal,
                    "suggestions": await self._get_meal_suggestions(
                        meal_type=meal["type"],
                        kcal=meal_kcal,
                        goal=goal,
                        macros=macros,
                    ),
                }
                plan["meals"].append(meal_data)

            logger.info(f"Generated nutrition plan for user {user.id}")
            return plan

        except Exception as e:
            logger.error(f"Error generating nutrition plan: {e}")
            return {}

    async def _get_meal_suggestions(
        self, meal_type: str, kcal: int, goal: Goal, macros: Dict
    ) -> List[str]:
        """Get meal suggestions from AI."""
        try:
            if not deepseek_client:
                # Fallback suggestions
                suggestions = {
                    "Завтрак": [
                        "Яйца (3 шт) + гарнир из овсянки с черникой",
                        "Творог 150г + мед + миндаль",
                        "Омлет 3 яйца + бутерброд с омлетом",
                    ],
                    "Обед": [
                        "Куриная грудка 200г + рис 150г + салат",
                        "Говядина 150g + сладкий картофель + брокколи",
                        "Рыба 200g + макаронные изделия + овощи",
                    ],
                    "Ужин": [
                        "Индейка 150g + батат + зелень",
                        "Лосось 180g + бурый рис + салат",
                        "Куриная грудка 150g + овощи на гриле",
                    ],
                }
                return suggestions.get(meal_type, ["Здоровая еда"])

            # Use AI for better suggestions
            prompt = (
                f"Дай 3 идеи для {meal_type} ({kcal} ккал) для цели {goal.value}.\n"
                f"Макросы: {macros['protein_g']}g белка, {macros['fat_g']}g жира, {macros['carbs_g']}g углеводов.\n"
                f"Формат: 'Блюдо | количество | калории'"
            )

            response = await deepseek_client.chat(prompt)
            suggestions = response.split("\n")[:3]
            return suggestions

        except Exception as e:
            logger.error(f"Error getting meal suggestions: {e}")
            return []

    # ==================== TRAINING PROGRAM GENERATION ====================

    async def _generate_training_program(
        self, user: User, data: Dict, results: Dict
    ) -> Dict[str, Any]:
        """Generate first training program."""
        try:
            experience = data.get("training_experience", "beginner")
            frequency = data.get("training_frequency", 3)
            training_type = data.get("training_type", "mixed")
            equipment = data.get("equipment_access", "gym")

            # Select program based on experience and frequency
            program = self._select_training_program(
                experience, frequency, training_type, equipment
            )

            return {
                "program_name": program["name"],
                "duration_weeks": 4,
                "frequency": frequency,
                "experience": experience,
                "type": training_type,
                "equipment": equipment,
                "weekly_schedule": program["schedule"],
                "exercises_per_workout": program["exercises_per_workout"],
                "notes": program["notes"],
            }

        except Exception as e:
            logger.error(f"Error generating training program: {e}")
            return {}

    def _select_training_program(
        self, experience: str, frequency: int, training_type: str, equipment: str
    ) -> Dict:
        """Select appropriate training program."""
        # Beginner programs
        if experience == "beginner":
            if frequency <= 3:
                return {
                    "name": "Full Body 3x/week (Новичок)",
                    "schedule": {
                        "Пн": "Full Body A",
                        "Ср": "Full Body B",
                        "Пт": "Full Body A",
                    },
                    "exercises_per_workout": 6,
                    "notes": "Базовые упражнения, 3 подхода x 8-12 рeps",
                }
            elif frequency <= 4:
                return {
                    "name": "Upper/Lower Split (Новичок)",
                    "schedule": {
                        "Пн": "Upper Body",
                        "Ср": "Lower Body",
                        "Пт": "Upper Body",
                        "Вс": "Lower Body",
                    },
                    "exercises_per_workout": 6,
                    "notes": "Разделение по группам мышц",
                }
            else:
                return {
                    "name": "PPL Split (Новичок)",
                    "schedule": {
                        "Пн": "Push",
                        "Ср": "Pull",
                        "Пт": "Legs",
                    },
                    "exercises_per_workout": 7,
                    "notes": "Push/Pull/Legs программа",
                }

        # Intermediate programs
        elif experience == "intermediate":
            if frequency <= 3:
                return {
                    "name": "Upper/Lower/Full (Средний)",
                    "schedule": {
                        "Пн": "Upper Power",
                        "Ср": "Lower Volume",
                        "Пт": "Full Body",
                    },
                    "exercises_per_workout": 7,
                    "notes": "Микс мощности и объема",
                }
            elif frequency == 4:
                return {
                    "name": "Upper/Lower x2 (Средний)",
                    "schedule": {
                        "Пн": "Upper A",
                        "Ср": "Lower A",
                        "Пт": "Upper B",
                        "Вс": "Lower B",
                    },
                    "exercises_per_workout": 8,
                    "notes": "Две тренировки для каждой группы",
                }
            else:
                return {
                    "name": "PPL x2 (Средний)",
                    "schedule": {
                        "Пн": "Push",
                        "Ср": "Pull",
                        "Пт": "Legs",
                    },
                    "exercises_per_workout": 9,
                    "notes": "Интенсивная PPL программа",
                }

        # Advanced programs
        else:
            return {
                "name": "Customized (Продвинутый)",
                "schedule": {
                    "Пн": "Day 1",
                    "Ср": "Day 2",
                    "Пт": "Day 3",
                },
                "exercises_per_workout": 10,
                "notes": "Персональная программа на основе целей",
            }

    # ==================== AI RECOMMENDATIONS ====================

    async def _generate_ai_recommendations(
        self, user: User, data: Dict, results: Dict
    ) -> Dict[str, Any]:
        """Generate personalized AI recommendations."""
        try:
            goal = data.get("goal")
            bmi = results["bmi"]
            tdee = results["adjusted_tdee"]

            if not deepseek_client:
                return self._get_default_recommendations(goal, bmi)

            # Build prompt for DeepSeek
            prompt = f"""
            Дай персональные рекомендации для достижения цели "{goal.value}" пользователю:
            
            Данные:
            - Возраст: {data.get('age')} лет
            - BMI: {bmi}
            - TDEE: {tdee} ккал/день
            - Опыт тренировок: {data.get('training_experience')}
            - Здоровье: {data.get('health_conditions')}
            
            Дай конкретные советы (3-5 пунктов):
            1. Питание
            2. Тренировки
            3. Восстановление
            4. Отслеживание прогресса
            5. Первые шаги на эту неделю
            """

            response = await deepseek_client.chat(prompt)

            return {
                "source": "DeepSeek AI",
                "recommendations": response,
                "created_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error generating AI recommendations: {e}")
            return self._get_default_recommendations(data.get("goal"), results.get("bmi"))

    def _get_default_recommendations(self, goal: Goal, bmi: float) -> Dict:
        """Get default recommendations if AI fails."""
        recommendations = {
            "source": "Default",
            "recommendations": f"""
            📋 **Твой план на неделю:**
            
            1️⃣ **Питание:**
            - Считай калории первые 2 недели (учись визуально оценивать)
            - Ешь постные белки каждый прием пищи
            - Уменьши обработанные углеводы
            
            2️⃣ **Тренировки:**
            - Начни с 3 тренировок в неделю
            - Прогрессируй в весах/подходах каждую неделю
            - Делай все упражнения правильно (видео важнее веса)
            
            3️⃣ **Восстановление:**
            - Спи 7-9 часов в день
            - Пей 2-3 литра воды в день
            - Отдыхай минимум день между пеиками
            
            4️⃣ **Отслеживание:**
            - Взвешивайся 1-2 раза в неделю
            - Делай фото прогресса каждые 2 недели
            - Веди дневник тренировок
            """,
            "created_at": datetime.now().isoformat(),
        }
        return recommendations

    # ==================== REMINDERS SETUP ====================

    async def _setup_reminders(self, user: User):
        """Setup reminders for user."""
        try:
            from modules.reminders import reminder_manager, ReminderType

            # Meal reminders
            reminder_manager.add_recurring_reminder(
                user_id=user.id,
                reminder_type=ReminderType.MEAL,
                times=["08:00", "11:30", "14:00", "19:00"],
                days_of_week=[0, 1, 2, 3, 4, 5, 6],  # Every day
            )

            # Training reminder
            reminder_manager.add_recurring_reminder(
                user_id=user.id,
                reminder_type=ReminderType.TRAINING,
                times=["17:00"],
                days_of_week=[0, 2, 4],  # Mon, Wed, Fri
            )

            # Daily summary
            reminder_manager.add_recurring_reminder(
                user_id=user.id,
                reminder_type=ReminderType.DAILY_SUMMARY,
                times=["21:00"],
                days_of_week=[0, 1, 2, 3, 4, 5, 6],
            )

            logger.info(f"Setup reminders for user {user.id}")

        except Exception as e:
            logger.error(f"Error setting up reminders: {e}")

    # ==================== UTILITIES ====================

    def _get_bmi_description(self, status: str) -> str:
        """Get BMI status description."""
        descriptions = {
            "underweight": "🤏 Недовес (нужен профицит калорий)",
            "normal": "✅ Здоровый вес (BMI 18.5-24.9)",
            "overweight": "📈 Избыток веса (BMI 25-29.9)",
            "obese": "🔴 Ожирение (BMI > 30)",
        }
        return descriptions.get(status, "❓ Неизвестный статус")

    def get_session(self, user_id: int) -> Optional[SmartOnboardingHandler]:
        """Get onboarding session."""
        return self.sessions.get(user_id)

    def clear_session(self, user_id: int):
        """Clear onboarding session."""
        if user_id in self.sessions:
            del self.sessions[user_id]


# Global instance
onboarding_integration = OnboardingIntegrationManager()
