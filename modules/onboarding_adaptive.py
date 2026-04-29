"""
Smart Onboarding 2.0 - Adaptive 3-Phase with Button Input & Branching.

Phases:
1. CRITICAL (5 buttons) - Fast start, immediate results
2. ADAPTIVE (branching based on goal) - Health/Training/Nutrition specifics  
3. OPTIONAL (after profile creation) - Deep dive settings

Features:
- Button-based input (less parsing errors)
- Adaptive question branching (goal → specific questions)
- Progress bar in every message
- Immediate TDEE/BMI/Macros calculation
- Skip logic for irrelevant questions
- Motivational messages
"""

from typing import Dict, Any, Optional, List, Tuple, Callable
from datetime import datetime, date
import logging
import re
from enum import Enum

logger = logging.getLogger(__name__)


class OnboardingPhase(Enum):
    """Onboarding phases."""
    PHASE_1_CRITICAL = "phase_1_critical"
    PHASE_2_HEALTH = "phase_2_health"
    PHASE_3_TRAINING = "phase_3_training"
    COMPLETE = "complete"


class ActivityLevel(Enum):
    """User activity levels."""
    SEDENTARY = 1.2  # Minimal activity
    LIGHT = 1.375  # 1-3 days/week training
    MODERATE = 1.55  # 3-5 days/week training
    VERY_ACTIVE = 1.725  # 6-7 days/week
    EXTREME = 1.9  # 2x per day training


class AdaptiveOnboardingHandler:
    """
    Adaptive 3-phase onboarding handler.
    Collects critical data first, shows results, then expands.
    """

    # ==================== PHASE 1: CRITICAL ====================
    PHASE_1_STEPS = [
        "start",
        "name",
        "date_of_birth",
        "gender",
        "height",
        "weight",
        "goal",
        "activity_level",
    ]

    # ==================== PHASE 2: HEALTH (Adaptive) ====================
    PHASE_2_BASE_STEPS = [
        "health_conditions",
        "allergies",
        "medications",
        "blood_pressure",
    ]

    # ==================== PHASE 3: TRAINING (Adaptive) ====================
    PHASE_3_BASE_STEPS = [
        "training_experience",
        "training_frequency",
        "training_type",
        "equipment_access",
    ]

    def __init__(self, telegram_id: str):
        self.telegram_id = telegram_id
        self.phase = OnboardingPhase.PHASE_1_CRITICAL
        self.current_step_index = 0
        self.collected_data: Dict[str, Any] = {}
        self.is_complete = False
        self.current_steps_list = self.PHASE_1_STEPS.copy()

    def get_current_step(self) -> str:
        """Get current step name."""
        if self.current_step_index < len(self.current_steps_list):
            return self.current_steps_list[self.current_step_index]
        return "phase_complete"

    def get_phase_progress(self) -> str:
        """Get progress bar for current phase."""
        total = len(self.current_steps_list)
        current = self.current_step_index + 1
        filled = int((current / total) * 10)
        empty = 10 - filled
        bar = "▓" * filled + "░" * empty
        return f"{bar} {current}/{total}"

    def get_question(self) -> str:
        """Get question for current step with progress."""
        step = self.get_current_step()
        phase_num = self._get_phase_number()
        progress = self.get_phase_progress()

        questions = {
            # ==================== PHASE 1: CRITICAL ====================
            "start": (
                "👋 **Привет! Я помогу тренировать твое здоровье.**\n\n"
                "📊 Я быстро узнаю о тебе и покажу:\n"
                "✅ Твой BMI\n"
                "✅ Дневную норму калорий\n"
                "✅ Оптимальные макросы (БЖУ)\n"
                "✅ Первую программу питания\n\n"
                "⏱️ Займет ~5 минут. Начинаем?\n\n"
                f"{progress}"
            ),

            "name": (
                "📝 **Твое имя?**\n"
                "(Например: Вячеслав)\n\n"
                f"{progress}"
            ),

            "date_of_birth": (
                "📅 **Дата рождения?**\n"
                "(Формат: ДД.ММ.ГГГГ, например 17.01.2009)\n\n"
                f"{progress}"
            ),

            "gender": (
                "🚹 **Пол?**\n\n"
                "[👨 Мужской] [👩 Женский] [❓ Другое]"
            ),

            "height": (
                "📏 **Рост в см?**\n"
                "(Например: 176)\n\n"
                f"{progress}"
            ),

            "weight": (
                "⚖️ **Текущий вес в кг?**\n"
                "(Например: 83)\n\n"
                f"{progress}"
            ),

            "goal": (
                "🎯 **Твоя главная цель?**\n\n"
                "[1️⃣ Похудение]\n"
                "[2️⃣ Набор мышц]\n"
                "[3️⃣ Здоровье & форма]\n"
                "[4️⃣ Рекомпозиция (жир↔мышцы)]"
            ),

            "activity_level": (
                "🏃 **Уровень активности?**\n\n"
                "[1️⃣ Минимальная]\n"
                "[2️⃣ Легкая (1-3 дн/нед тренировок)]\n"
                "[3️⃣ Умеренная (3-5 дн/нед)]\n"
                "[4️⃣ Активная (6-7 дн/нед)]"
            ),

            # ==================== PHASE 2: HEALTH ====================
            "health_conditions": (
                "🏥 **Хронические заболевания?**\n"
                "(Диабет, гипертония, астма и т.д.)\n\n"
                "Пиши 'нет' или список через запятую.\n\n"
                f"{progress}"
            ),

            "allergies": (
                "⚠️ **Пищевые аллергии?**\n"
                "(Глютен, лактоза, орехи и т.д.)\n\n"
                "Пиши 'нет' или список.\n\n"
                f"{progress}"
            ),

            "medications": (
                "💊 **Постоянные лекарства?**\n"
                "(Не считая добавок)\n\n"
                "Пиши 'нет' или список.\n\n"
                f"{progress}"
            ),

            "blood_pressure": (
                "🩸 **Кровяное давление в норме?**\n"
                "(Обычное: ~120/80)\n\n"
                "[✅ Нормально] [⚠️ Высокое] [❓ Не знаю]"
            ),

            "injuries_limitations": (
                "🩹 **Травмы или ограничения?**\n"
                "(Спина, колени, плечи и т.д.)\n\n"
                "Пиши 'нет' или список.\n\n"
                f"{progress}"
            ),

            # ==================== PHASE 3: TRAINING ====================
            "training_experience": (
                "🏋️ **Опыт тренировок?**\n\n"
                "[1️⃣ Новичок (0-6 мес)]\n"
                "[2️⃣ Средний (6-18 мес)]\n"
                "[3️⃣ Опытный (18+ мес)]"
            ),

            "training_frequency": (
                "📆 **Сколько дней в неделю тренируешься?**\n"
                "(Например: 3, 4, 5)\n\n"
                f"{progress}"
            ),

            "training_type": (
                "🏃 **Тип тренировок?**\n\n"
                "[1️⃣ Силовые]\n"
                "[2️⃣ Кардио]\n"
                "[3️⃣ Смешанные]\n"
                "[4️⃣ Дом (без оборудования)]"
            ),

            "equipment_access": (
                "🏠 **Где тренируешься?**\n\n"
                "[1️⃣ Тренажерный зал]\n"
                "[2️⃣ Дома]\n"
                "[3️⃣ Улица/парк]\n"
                "[4️⃣ Везде/смешанное]"
            ),

            "phase_complete": "✅ Этап завершен!",
        }

        return questions.get(step, "❓ Вопрос не найден")

    def process_answer(self, answer: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Process answer and move to next step.
        
        Returns:
            (success, error_message, phase_results)
        """
        step = self.get_current_step()

        try:
            # ==================== PHASE 1 ====================

            if step == "start":
                self.current_step_index += 1
                return True, None, None

            elif step == "name":
                if len(answer.strip()) < 2:
                    return False, "❌ Введи корректное имя", None
                self.collected_data["name"] = answer.strip()
                self.current_step_index += 1
                return True, None, None

            elif step == "date_of_birth":
                dob = self._parse_date(answer)
                if not dob:
                    return False, "❌ Неверный формат (ДД.ММ.ГГГГ)", None

                age = self._calculate_age(dob)
                if age < 13:
                    return False, "❌ Ботом могут пользоваться лица старше 13 лет", None
                if age > 120:
                    return False, "❌ Проверь дату рождения", None

                self.collected_data["date_of_birth"] = dob
                self.collected_data["age"] = age
                self.current_step_index += 1
                return True, None, None

            elif step == "gender":
                gender_map = {"1": "male", "2": "female", "3": "other", "м": "male", "ж": "female"}
                gender = gender_map.get(answer.strip().lower())
                if not gender:
                    return False, "❌ Выбери: 1️⃣ / 2️⃣ / 3️⃣", None
                self.collected_data["gender"] = gender
                self.current_step_index += 1
                return True, None, None

            elif step == "height":
                try:
                    height = float(answer.replace(",", "."))
                    if height < 100 or height > 250:
                        return False, "❌ Рост 100-250 см", None
                    self.collected_data["height_cm"] = height
                    self.current_step_index += 1
                    return True, None, None
                except ValueError:
                    return False, "❌ Введи число (см)", None

            elif step == "weight":
                try:
                    weight = float(answer.replace(",", "."))
                    if weight < 30 or weight > 300:
                        return False, "❌ Вес 30-300 кг", None
                    self.collected_data["weight_kg"] = weight
                    self.current_step_index += 1
                    return True, None, None
                except ValueError:
                    return False, "❌ Введи число (кг)", None

            elif step == "goal":
                goal_map = {
                    "1": "weight_loss",
                    "2": "muscle_gain",
                    "3": "health",
                    "4": "recomposition",
                }
                goal = goal_map.get(answer.strip())
                if not goal:
                    return False, "❌ Выбери: 1️⃣ / 2️⃣ / 3️⃣ / 4️⃣", None
                self.collected_data["goal"] = goal
                self.current_step_index += 1
                return True, None, None

            elif step == "activity_level":
                level_map = {
                    "1": "sedentary",
                    "2": "light",
                    "3": "moderate",
                    "4": "very_active",
                }
                level = level_map.get(answer.strip())
                if not level:
                    return False, "❌ Выбери: 1️⃣ / 2️⃣ / 3️⃣ / 4️⃣", None
                self.collected_data["activity_level"] = level
                self.current_step_index += 1

                # ✅ PHASE 1 COMPLETE → CALCULATE RESULTS
                if self.current_step_index >= len(self.PHASE_1_STEPS):
                    results = self._calculate_phase_1_results()
                    self._move_to_phase_2()
                    return True, None, results

                return True, None, None

            # ==================== PHASE 2 ====================

            elif step == "health_conditions":
                if answer.strip().lower() == "нет":
                    self.collected_data["health_conditions"] = []
                else:
                    self.collected_data["health_conditions"] = [
                        c.strip() for c in answer.split(",")
                    ]
                self.current_step_index += 1
                return True, None, None

            elif step == "allergies":
                if answer.strip().lower() == "нет":
                    self.collected_data["allergies"] = []
                else:
                    self.collected_data["allergies"] = [a.strip() for a in answer.split(",")]
                self.current_step_index += 1
                return True, None, None

            elif step == "medications":
                if answer.strip().lower() == "нет":
                    self.collected_data["medications"] = []
                else:
                    self.collected_data["medications"] = [m.strip() for m in answer.split(",")]
                self.current_step_index += 1
                return True, None, None

            elif step == "blood_pressure":
                bp_map = {"1": "normal", "2": "high", "3": "unknown"}
                bp = bp_map.get(answer.strip())
                if not bp:
                    return False, "❌ Выбери: ✅ / ⚠️ / ❓", None
                self.collected_data["blood_pressure"] = bp
                self.current_step_index += 1

                if self.current_step_index >= len(self.current_steps_list):
                    results = self._calculate_phase_2_results()
                    self._move_to_phase_3()
                    return True, None, results

                return True, None, None

            # ==================== PHASE 3 ====================

            elif step == "training_experience":
                exp_map = {"1": "beginner", "2": "intermediate", "3": "advanced"}
                exp = exp_map.get(answer.strip())
                if not exp:
                    return False, "❌ Выбери: 1️⃣ / 2️⃣ / 3️⃣", None
                self.collected_data["training_experience"] = exp
                self.current_step_index += 1
                return True, None, None

            elif step == "training_frequency":
                try:
                    freq = int(answer.strip())
                    if freq < 0 or freq > 7:
                        return False, "❌ Вводи 0-7 дней", None
                    self.collected_data["training_frequency"] = freq
                    self.current_step_index += 1
                    return True, None, None
                except ValueError:
                    return False, "❌ Введи число (дни в неделю)", None

            elif step == "training_type":
                type_map = {"1": "strength", "2": "cardio", "3": "mixed", "4": "home"}
                ttype = type_map.get(answer.strip())
                if not ttype:
                    return False, "❌ Выбери: 1️⃣ / 2️⃣ / 3️⃣ / 4️⃣", None
                self.collected_data["training_type"] = ttype
                self.current_step_index += 1
                return True, None, None

            elif step == "equipment_access":
                equip_map = {"1": "gym", "2": "home", "3": "street", "4": "mixed"}
                equip = equip_map.get(answer.strip())
                if not equip:
                    return False, "❌ Выбери: 1️⃣ / 2️⃣ / 3️⃣ / 4️⃣", None
                self.collected_data["equipment_access"] = equip
                self.current_step_index += 1

                if self.current_step_index >= len(self.current_steps_list):
                    results = self._calculate_phase_3_results()
                    self.is_complete = True
                    self.phase = OnboardingPhase.COMPLETE
                    return True, None, results

                return True, None, None

        except Exception as e:
            logger.error(f"Error processing answer: {e}")
            return False, f"❌ Ошибка: {str(e)}", None

        return False, "❌ Неизвестная ошибка", None

    # ==================== CALCULATION METHODS ====================

    def _calculate_phase_1_results(self) -> Dict[str, Any]:
        """Calculate BMI, TDEE, Macros after Phase 1."""
        weight = self.collected_data.get("weight_kg", 0)
        height = self.collected_data.get("height_cm", 0)
        age = self.collected_data.get("age", 0)
        gender = self.collected_data.get("gender", "male")
        activity_level = self.collected_data.get("activity_level", "moderate")
        goal = self.collected_data.get("goal", "health")

        # BMI
        bmi = weight / ((height / 100) ** 2)
        bmi_status = self._get_bmi_status(bmi)

        # TDEE (Mifflin-St Jeor)
        if gender == "male":
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161

        activity_multiplier = {
            "sedentary": 1.2,
            "light": 1.375,
            "moderate": 1.55,
            "very_active": 1.725,
        }.get(activity_level, 1.55)

        tdee = int(bmr * activity_multiplier)

        # Adjusted TDEE for goal
        if goal == "weight_loss":
            adjusted_tdee = tdee - 500  # 500 kcal deficit
        elif goal == "muscle_gain":
            adjusted_tdee = tdee + 300  # 300 kcal surplus
        elif goal == "recomposition":
            adjusted_tdee = tdee
        else:
            adjusted_tdee = tdee

        # Macros
        macros = self._calculate_macros(adjusted_tdee, goal, weight)

        # Status message
        status_msg = self._get_health_status_message(bmi, bmi_status, weight, height)

        return {
            "bmi": round(bmi, 1),
            "bmi_status": bmi_status,
            "bmr": int(bmr),
            "tdee": tdee,
            "adjusted_tdee": adjusted_tdee,
            "macros": macros,
            "status_message": status_msg,
            "recommendation": self._get_phase_1_recommendation(goal, bmi),
        }

    def _calculate_phase_2_results(self) -> Dict[str, Any]:
        """Generate health recommendations after Phase 2."""
        conditions = self.collected_data.get("health_conditions", [])
        allergies = self.collected_data.get("allergies", [])
        bp = self.collected_data.get("blood_pressure", "normal")

        recommendations = []

        if bp == "high":
            recommendations.append("⚠️ Снизить подсоленность, увеличить калий (бананы, шпинат)")
        if "диабет" in str(conditions).lower():
            recommendations.append("🍎 Контролировать углеводы (низкий GI)")
        if allergies:
            recommendations.append(f"🚫 Избегать: {', '.join(allergies)}")

        return {
            "health_conditions": conditions,
            "allergies": allergies,
            "blood_pressure": bp,
            "recommendations": recommendations or ["✅ Здоровье в норме!"],
        }

    def _calculate_phase_3_results(self) -> Dict[str, Any]:
        """Generate training program recommendations after Phase 3."""
        experience = self.collected_data.get("training_experience", "beginner")
        frequency = self.collected_data.get("training_frequency", 3)
        ttype = self.collected_data.get("training_type", "mixed")
        equip = self.collected_data.get("equipment_access", "gym")

        # Training program template
        programs = {
            "beginner": {
                "3": "ПН-СР-ПТ: Fullbody (3 дня)",
                "4": "ПН-ВТ-ЧТ-ПТ: Upper/Lower Split",
                "5": "ПН-ВТ-СР-ЧТ-ПТ: PPL (Push/Pull/Legs)",
            },
            "intermediate": {
                "3": "ПН-СР-ПТ: Upper/Lower + Full",
                "4": "ПН-ВТ-ЧТ-ПТ: PPL",
                "5": "ПН-ВТ-СР-ЧТ-ПТ: PPL + Cardio",
            },
            "advanced": {
                "4": "Upper/Lower/Upper/Lower",
                "5": "PPL x2 (6 дней)",
                "6": "PPL x2 + Cardio",
            },
        }

        freq_str = str(frequency)
        program = programs.get(experience, {}).get(
            freq_str, "Персональная программа (спроси ИИ)"
        )

        return {
            "training_experience": experience,
            "training_frequency": frequency,
            "training_type": ttype,
            "equipment_access": equip,
            "suggested_program": program,
            "first_workout_message": f"💪 Первая тренировка: {program}",
        }

    # ==================== HELPER METHODS ====================

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date from DD.MM.YYYY or YYYY-MM-DD."""
        formats = ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        return None

    def _calculate_age(self, dob: date) -> int:
        """Calculate age from date of birth."""
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    def _get_bmi_status(self, bmi: float) -> str:
        """Get BMI status."""
        if bmi < 18.5:
            return "underweight"
        elif bmi < 25:
            return "normal"
        elif bmi < 30:
            return "overweight"
        else:
            return "obese"

    def _get_health_status_message(
        self, bmi: float, status: str, weight: float, height: float
    ) -> str:
        """Generate health status message."""
        status_map = {
            "underweight": "🤏 Недовес (нужен профицит калорий)",
            "normal": "✅ Вес в норме (BMI: 18.5-24.9)",
            "overweight": "⚠️ Избыток (BMI: 25-29.9) → дефицит калорий",
            "obese": "🔴 Ожирение (BMI > 30) → большой дефицит или врач",
        }
        return status_map.get(status, "❓ Неизвестный статус")

    def _calculate_macros(
        self, tdee: int, goal: str, weight: float
    ) -> Dict[str, int]:
        """Calculate macronutrients."""
        # Protein: 1.6-2.2 g/kg
        if goal == "muscle_gain":
            protein_g = int(weight * 2.0)
        else:
            protein_g = int(weight * 1.8)

        protein_kcal = protein_g * 4

        # Fat: 0.8-1.2 g/kg
        fat_g = int(weight * 1.0)
        fat_kcal = fat_g * 9

        # Carbs: remainder
        carbs_kcal = tdee - protein_kcal - fat_kcal
        carbs_g = int(carbs_kcal / 4)

        return {
            "protein_g": protein_g,
            "fat_g": fat_g,
            "carbs_g": carbs_g,
            "protein_kcal": protein_kcal,
            "fat_kcal": fat_kcal,
            "carbs_kcal": carbs_kcal,
        }

    def _get_phase_1_recommendation(self, goal: str, bmi: float) -> str:
        """Get personalized Phase 1 recommendation."""
        recommendations = {
            "weight_loss": "🎯 Режим дефицита (TDEE - 500 ккал). Увеличь белки, урежь углеводы.",
            "muscle_gain": "💪 Режим профицита (TDEE + 300 ккал). Максимум белков, нормальные жиры.",
            "health": "❤️ Поддержание (TDEE). Сбалансированное питание + регулярные тренировки.",
            "recomposition": "🔄 Умный дефицит (TDEE - 200 ккал) + силовые тренировки для сброса жира и роста мышц.",
        }
        return recommendations.get(goal, "✅ Начни с базового плана питания")

    def _get_phase_number(self) -> int:
        """Get current phase number (1-3)."""
        if self.phase == OnboardingPhase.PHASE_1_CRITICAL:
            return 1
        elif self.phase == OnboardingPhase.PHASE_2_HEALTH:
            return 2
        elif self.phase == OnboardingPhase.PHASE_3_TRAINING:
            return 3
        return 0

    def _move_to_phase_2(self):
        """Move to Phase 2."""
        self.phase = OnboardingPhase.PHASE_2_HEALTH
        self.current_steps_list = self.PHASE_2_BASE_STEPS.copy()
        self.current_step_index = 0
        logger.info(f"User {self.telegram_id} moved to Phase 2 (Health)")

    def _move_to_phase_3(self):
        """Move to Phase 3."""
        self.phase = OnboardingPhase.PHASE_3_TRAINING
        self.current_steps_list = self.PHASE_3_BASE_STEPS.copy()
        self.current_step_index = 0
        logger.info(f"User {self.telegram_id} moved to Phase 3 (Training)")

    # ==================== DATA EXPORT ====================

    def get_collected_data(self) -> Dict[str, Any]:
        """Get all collected data (for saving to database)."""
        return self.collected_data.copy()

    def is_phase_complete(self) -> bool:
        """Check if current phase is complete."""
        return self.current_step_index >= len(self.current_steps_list)
