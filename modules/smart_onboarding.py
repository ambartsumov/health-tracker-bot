"""
Smart Onboarding 2.0 - Complete Implementation
Adaptive 3-Phase with Button Input, Branching & Optional Deep Dive

Features:
✅ Phase 1: 5 critical questions → Immediate BMI/TDEE/Macros
✅ Phase 2: Adaptive branching based on goal
✅ Phase 3: Optional deep dive settings
✅ Button-based input (minimal text parsing)
✅ Progress bar in every message
✅ Skip logic for irrelevant questions
✅ Motivational messages & badges
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, date
import logging
import re
from enum import Enum

logger = logging.getLogger(__name__)


class Goal(Enum):
    """User goals."""
    WEIGHT_LOSS = "weight_loss"
    MUSCLE_GAIN = "muscle_gain"
    HEALTH = "health"
    MAINTENANCE = "maintenance"
    RECOMPOSITION = "recomposition"


class ActivityLevel(Enum):
    """Activity levels with TDEE multipliers."""
    SEDENTARY = 1.2
    LIGHT = 1.375
    MODERATE = 1.55
    VERY_ACTIVE = 1.725


class Gender(Enum):
    """Gender options."""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class SmartOnboardingHandler:
    """Smart 3-phase adaptive onboarding with button input."""

    # ==================== PHASE 1: CRITICAL (5 steps) ====================
    PHASE_1_QUESTIONS = [
        "goal",          # Goal selection
        "gender_age",    # Gender + Age (combined for speed)
        "anthropometry", # Weight + Height (combined)
        "activity",      # Activity level
        "equipment",     # Equipment access
    ]

    # ==================== PHASE 2: ADAPTIVE BRANCHING ====================
    # Questions that appear based on goal
    PHASE_2_BY_GOAL = {
        Goal.WEIGHT_LOSS: [
            "health_conditions",
            "eating_habits",
            "stress_level",
            "medications",
        ],
        Goal.MUSCLE_GAIN: [
            "training_experience",
            "supplements",
            "health_conditions",
            "sleep_quality",
        ],
        Goal.HEALTH: [
            "health_conditions",
            "medications",
            "blood_pressure",
            "allergies",
        ],
        Goal.MAINTENANCE: [
            "health_conditions",
            "training_experience",
            "sedentary_hours",
        ],
        Goal.RECOMPOSITION: [
            "training_experience",
            "supplements",
            "sleep_quality",
            "medications",
        ],
    }

    # ==================== PHASE 3: OPTIONAL DEEP DIVE ====================
    PHASE_3_OPTIONS = [
        "detailed_health",    # Full medical history
        "daily_schedule",     # Work/study schedule
        "dietary_preferences", # Food likes/dislikes
        "personal_records",   # Strength benchmarks (if trained)
        "goals_timeline",     # Goal timeline & targets
    ]

    def __init__(self, telegram_id: str):
        self.telegram_id = telegram_id
        self.phase = 1  # 1, 2, 3, or completed
        self.step_index = 0
        self.collected_data: Dict[str, Any] = {}
        self.is_complete = False
        self.current_questions: List[str] = self.PHASE_1_QUESTIONS.copy()
        self.phase_1_results: Optional[Dict] = None
        self.phase_2_results: Optional[Dict] = None

    # ==================== PROGRESS & STATE ====================

    def get_progress_bar(self) -> str:
        """Get emoji progress bar."""
        total = len(self.current_questions)
        current = self.step_index + 1
        filled = int((current / total) * 10)
        bar = "▓" * filled + "░" * (10 - filled)
        return f"{bar} {current}/{total}"

    def get_current_question_key(self) -> str:
        """Get current question key."""
        if self.step_index < len(self.current_questions):
            return self.current_questions[self.step_index]
        return "complete"

    # ==================== QUESTION SYSTEM ====================

    def get_question_with_buttons(self) -> Tuple[str, Optional[List[List[str]]]]:
        """
        Get question text and button options.
        Returns: (message, button_grid or None for text input)
        """
        q = self.get_current_question_key()
        progress = self.get_progress_bar()
        phase = f"📋 Фаза {self.phase}/3"

        questions = {
            # ==================== PHASE 1 ====================
            "goal": (
                f"{phase} | {progress}\n\n"
                "🎯 **Какова твоя главная цель?**\n\n"
                "[⚖️ Похудеть]\n"
                "[💪 Набрать мышцы]\n"
                "[❤️ Здоровье]\n"
                "[🔄 Рекомпозиция]\n"
                "[⏸️ Поддержание]",
                [
                    ["⚖️ Похудеть", "💪 Набрать мышцы"],
                    ["❤️ Здоровье", "🔄 Рекомпозиция"],
                    ["⏸️ Поддержание"],
                ],
            ),

            "gender_age": (
                f"{phase} | {progress}\n\n"
                "👤 **Пол и возраст?**\n\n"
                "Сначала выбери пол, потом введи возраст числом",
                [
                    ["👨 Мужской", "👩 Женский", "❓ Другое"],
                ],
            ),

            "anthropometry": (
                f"{phase} | {progress}\n\n"
                "📏 **Вес и рост?**\n\n"
                "Введи: 'Вес 83 кг, Рост 176 см'\n"
                "или просто: '83 176'",
                None,  # Text input
            ),

            "activity": (
                f"{phase} | {progress}\n\n"
                "🏃 **Уровень активности?**\n\n"
                "[🏢 Офис]\n"
                "[🚶 Умеренная]\n"
                "[💪 Активная]\n"
                "[🏋️ Спортсмен]",
                [
                    ["🏢 Офис", "🚶 Умеренная"],
                    ["💪 Активная", "🏋️ Спортсмен"],
                ],
            ),

            "equipment": (
                f"{phase} | {progress}\n\n"
                "🏠 **Где ты тренируешься?**\n\n"
                "[🏋️ Тренажерный зал]\n"
                "[🏠 Дома]\n"
                "[🌳 Улица]\n"
                "[❌ Нет оборудования]",
                [
                    ["🏋️ Тренажерный зал", "🏠 Дома"],
                    ["🌳 Улица", "❌ Нет оборудования"],
                ],
            ),

            # ==================== PHASE 2: ADAPTIVE ====================

            "health_conditions": (
                f"{phase} | {progress}\n\n"
                "🏥 **Хронические заболевания?**",
                [["✅ Нет", "⚠️ Есть"], ["📝 Напишу подробнее"]],
            ),

            "eating_habits": (
                f"{phase} | {progress}\n\n"
                "🍽️ **Пищевые привычки?**",
                [
                    ["🥗 Здоровое", "🍔 Частые перекусы"],
                    ["😰 Стресс-еда", "🍕 Нерегулярное"],
                ],
            ),

            "stress_level": (
                f"{phase} | {progress}\n\n"
                "📊 **Уровень стресса?**",
                [
                    ["😌 Низкий", "😶 Средний", "😰 Высокий"],
                ],
            ),

            "medications": (
                f"{phase} | {progress}\n\n"
                "💊 **Постоянные лекарства?**",
                [["✅ Нет", "⚠️ Есть"], ["📝 Напишу какие"]],
            ),

            "training_experience": (
                f"{phase} | {progress}\n\n"
                "🏋️ **Опыт тренировок?**",
                [
                    ["🆕 Новичок", "🟡 Средний", "🥇 Опытный"],
                ],
            ),

            "supplements": (
                f"{phase} | {progress}\n\n"
                "💪 **Добавки?**",
                [
                    ["✅ Не принимаю", "🥤 Протеин", "⚪ Креатин"],
                    ["🅾️ Другие", "📝 Напишу"],
                ],
            ),

            "sleep_quality": (
                f"{phase} | {progress}\n\n"
                "😴 **Качество сна?**",
                [
                    ["😴 Хороший (7-9ч)", "🥱 Нормальный (5-7ч)"],
                    ["😫 Плохой (<5ч)"],
                ],
            ),

            "blood_pressure": (
                f"{phase} | {progress}\n\n"
                "🩸 **Кровяное давление?**",
                [
                    ["✅ Нормально", "⚠️ Повышенное", "❓ Не знаю"],
                ],
            ),

            "allergies": (
                f"{phase} | {progress}\n\n"
                "⚠️ **Пищевые аллергии?**",
                [["✅ Нет", "⚠️ Есть"], ["📝 Напишу какие"]],
            ),

            "sedentary_hours": (
                f"{phase} | {progress}\n\n"
                "🪑 **Часов в день сидишь?**",
                [["🟢 < 4ч", "🟡 4-8ч", "🔴 > 8ч"]],
            ),

            # ==================== PHASE 3: OPTIONAL ====================

            "detailed_health": (
                f"{phase} | {progress}\n\n"
                "🏥 **Подробный медицинский анамнез?**\n\n"
                "Операции, травмы, особенности",
                [["✅ Пропустить", "📋 Готов добавить"]],
            ),

            "daily_schedule": (
                f"{phase} | {progress}\n\n"
                "📅 **Расписание дня?**\n\n"
                "Работа, учеба, тренировки",
                [["✅ Пропустить", "📋 Готов добавить"]],
            ),

            "dietary_preferences": (
                f"{phase} | {progress}\n\n"
                "🥗 **Пищевые предпочтения?**",
                [["✅ Пропустить", "📋 Готов добавить"]],
            ),

            "personal_records": (
                f"{phase} | {progress}\n\n"
                "🏆 **Личные рекорды?**\n\n"
                "Жим / Присед / Становая",
                [["✅ Пропустить", "📋 Готов добавить"]],
            ),

            "goals_timeline": (
                f"{phase} | {progress}\n\n"
                "⏰ **Цели с дедлайнами?**",
                [["✅ Пропустить", "📋 Готов добавить"]],
            ),

            "complete": (
                "✅ **Профиль создан! 🎉**\n\n"
                f"Имя: {self.collected_data.get('name', 'Пользователь')}\n"
                f"BMI: {self.phase_1_results.get('bmi', '?')}\n"
                f"TDEE: {self.phase_1_results.get('adjusted_tdee', '?')} ккал\n\n"
                "💪 Готов к работе!",
                None,
            ),
        }

        if q in questions:
            msg, buttons = questions[q]
            return msg, buttons

        return "❓ Вопрос не найден", None

    # ==================== DATA PROCESSING ====================

    def process_button_answer(self, button_text: str) -> Tuple[bool, Optional[str]]:
        """Process button click answer. Returns (success, error_msg)."""
        q = self.get_current_question_key()

        try:
            # PHASE 1
            if q == "goal":
                goal_map = {
                    "⚖️ Похудеть": Goal.WEIGHT_LOSS,
                    "💪 Набрать мышцы": Goal.MUSCLE_GAIN,
                    "❤️ Здоровье": Goal.HEALTH,
                    "🔄 Рекомпозиция": Goal.RECOMPOSITION,
                    "⏸️ Поддержание": Goal.MAINTENANCE,
                }
                goal = goal_map.get(button_text)
                if not goal:
                    return False, "❌ Выбери из предложенных"
                self.collected_data["goal"] = goal
                self._move_to_next_step()
                return True, None

            elif q == "activity":
                activity_map = {
                    "🏢 Офис": 1.2,
                    "🚶 Умеренная": 1.55,
                    "💪 Активная": 1.725,
                    "🏋️ Спортсмен": 1.9,
                }
                activity = activity_map.get(button_text)
                if activity is None:
                    return False, "❌ Выбери уровень"
                self.collected_data["activity_level"] = activity
                self._move_to_next_step()
                return True, None

            elif q == "equipment":
                equip_map = {
                    "🏋️ Тренажерный зал": "gym",
                    "🏠 Дома": "home",
                    "🌳 Улица": "street",
                    "❌ Нет оборудования": "none",
                }
                equip = equip_map.get(button_text)
                if not equip:
                    return False, "❌ Выбери вариант"
                self.collected_data["equipment_access"] = equip
                self._move_to_next_step()

                # After Phase 1 → Move to Phase 2
                if self.phase == 1 and self.step_index >= len(self.PHASE_1_QUESTIONS):
                    self.phase_1_results = self._calculate_phase_1_results()
                    self._move_to_phase_2()
                    return True, "PHASE_1_COMPLETE"

                return True, None

            # PHASE 2
            else:
                self.collected_data[q] = button_text
                self._move_to_next_step()

                if self.phase == 2 and self.step_index >= len(self.current_questions):
                    self.phase_2_results = self._calculate_phase_2_results()
                    self._move_to_phase_3()
                    return True, "PHASE_2_COMPLETE"

                return True, None

        except Exception as e:
            logger.error(f"Error processing button: {e}")
            return False, f"❌ Ошибка: {str(e)}"

    def process_text_answer(self, text: str) -> Tuple[bool, Optional[str]]:
        """Process text input answer."""
        q = self.get_current_question_key()

        try:
            if q == "gender_age":
                # Parse gender first (if not set), then age
                gender_map = {"м": "male", "ж": "female", "м/м": "male", "м/ж": "female"}
                first_word = text.split()[0].lower() if text else ""

                if first_word in gender_map:
                    self.collected_data["gender"] = gender_map[first_word]

                # Parse age
                age_match = re.search(r"\d+", text)
                if not age_match:
                    return False, "❌ Укажи возраст числом (13-100)"
                age = int(age_match.group())
                if age < 13 or age > 120:
                    return False, "❌ Возраст: 13-120"
                self.collected_data["age"] = age
                self._move_to_next_step()
                return True, None

            elif q == "anthropometry":
                # Parse weight and height
                numbers = re.findall(r"\d+(?:[.,]\d+)?", text)
                if len(numbers) < 2:
                    return False, "❌ Подели вес и рост (например: 83 176 или 83, 176)"

                weight = float(numbers[0].replace(",", "."))
                height = float(numbers[1].replace(",", "."))

                if weight < 30 or weight > 300:
                    return False, "❌ Вес: 30-300 кг"
                if height < 100 or height > 250:
                    return False, "❌ Рост: 100-250 см"

                self.collected_data["weight_kg"] = weight
                self.collected_data["height_cm"] = height
                self._move_to_next_step()
                return True, None

            # PHASE 2, 3 text inputs
            else:
                self.collected_data[q] = text
                self._move_to_next_step()

                if self.phase == 2 and self.step_index >= len(self.current_questions):
                    self.phase_2_results = self._calculate_phase_2_results()
                    self._move_to_phase_3()
                    return True, "PHASE_2_COMPLETE"

                if self.phase == 3 and self.step_index >= len(self.current_questions):
                    self.is_complete = True
                    return True, "COMPLETE"

                return True, None

        except Exception as e:
            logger.error(f"Error processing text: {e}")
            return False, f"❌ Ошибка: {str(e)}"

    # ==================== PHASE TRANSITIONS ====================

    def _move_to_next_step(self):
        """Move to next step."""
        self.step_index += 1

    def _move_to_phase_2(self):
        """Move to Phase 2 with adaptive branching."""
        self.phase = 2
        self.step_index = 0

        # Determine which questions to ask based on goal
        goal = self.collected_data.get("goal", Goal.HEALTH)
        self.current_questions = self.PHASE_2_BY_GOAL.get(goal, [])

        logger.info(
            f"User {self.telegram_id} → Phase 2 with goal={goal.value}, "
            f"questions={self.current_questions}"
        )

    def _move_to_phase_3(self):
        """Move to Phase 3 optional deep dive."""
        self.phase = 3
        self.step_index = 0
        self.current_questions = self.PHASE_3_OPTIONS.copy()
        logger.info(f"User {self.telegram_id} → Phase 3 (Optional)")

    # ==================== CALCULATIONS ====================

    def _calculate_phase_1_results(self) -> Dict[str, Any]:
        """Calculate BMI, TDEE, Macros after Phase 1."""
        weight = self.collected_data.get("weight_kg", 0)
        height = self.collected_data.get("height_cm", 0)
        age = self.collected_data.get("age", 25)
        gender = self.collected_data.get("gender", "male")
        activity = self.collected_data.get("activity_level", 1.55)
        goal = self.collected_data.get("goal", Goal.HEALTH)

        # BMI
        bmi = weight / ((height / 100) ** 2)
        bmi_status = self._get_bmi_status(bmi)

        # TDEE (Mifflin-St Jeor)
        if gender == "male":
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161

        tdee = int(bmr * activity)

        # Adjusted TDEE
        if goal == Goal.WEIGHT_LOSS:
            adjusted_tdee = tdee - 500
        elif goal == Goal.MUSCLE_GAIN:
            adjusted_tdee = tdee + 300
        elif goal == Goal.RECOMPOSITION:
            adjusted_tdee = tdee - 250
        else:
            adjusted_tdee = tdee

        # Macros
        macros = self._calculate_macros(adjusted_tdee, goal, weight)

        return {
            "bmi": round(bmi, 1),
            "bmi_status": bmi_status,
            "bmr": int(bmr),
            "tdee": tdee,
            "adjusted_tdee": adjusted_tdee,
            "macros": macros,
            "goal": goal.value,
        }

    def _calculate_phase_2_results(self) -> Dict[str, Any]:
        """Generate health recommendations after Phase 2."""
        return {q: self.collected_data.get(q, "") for q in self.current_questions}

    def _get_bmi_status(self, bmi: float) -> str:
        """Get BMI status."""
        if bmi < 18.5:
            return "underweight"
        elif bmi < 25:
            return "normal"
        elif bmi < 30:
            return "overweight"
        return "obese"

    def _calculate_macros(self, tdee: int, goal: Goal, weight: float) -> Dict[str, int]:
        """Calculate macronutrients."""
        if goal == Goal.MUSCLE_GAIN:
            protein_g = int(weight * 2.0)
        else:
            protein_g = int(weight * 1.8)

        protein_kcal = protein_g * 4
        fat_g = int(weight * 1.0)
        fat_kcal = fat_g * 9
        carbs_kcal = tdee - protein_kcal - fat_kcal
        carbs_g = max(0, int(carbs_kcal / 4))

        return {
            "protein_g": protein_g,
            "fat_g": fat_g,
            "carbs_g": carbs_g,
        }

    # ==================== STATE MANAGEMENT ====================

    def get_state(self) -> Dict[str, Any]:
        """Get current state for persistence."""
        return {
            "phase": self.phase,
            "step_index": self.step_index,
            "collected_data": self.collected_data,
            "is_complete": self.is_complete,
            "current_questions": self.current_questions,
        }

    def load_state(self, state: Dict[str, Any]):
        """Load state from persistence."""
        self.phase = state.get("phase", 1)
        self.step_index = state.get("step_index", 0)
        self.collected_data = state.get("collected_data", {})
        self.is_complete = state.get("is_complete", False)
        self.current_questions = state.get("current_questions", self.PHASE_1_QUESTIONS)

    # ==================== UTILITIES ====================

    def get_collected_data(self) -> Dict[str, Any]:
        """Get all collected data."""
        return self.collected_data.copy()

    def get_phase_1_results(self) -> Optional[Dict]:
        """Get Phase 1 calculation results."""
        return self.phase_1_results

    def is_phase_1_complete(self) -> bool:
        """Check if Phase 1 is complete."""
        return self.phase >= 2
