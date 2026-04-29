"""
Maximum Personalization Onboarding for Health Bot.
25 steps across 5 phases to collect user data.

Phases:
1. Anthropometry (steps 1-5) - Basic body metrics
2. Health Profile (steps 6-10) - Medical history, conditions
3. Nutrition & Supplements (steps 11-15) - Diet, supplements
4. Lifestyle & Schedule (steps 16-20) - Daily routine, stress, sleep
5. Training & Activity (steps 21-25) - Exercise history, goals
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, date
import logging
import re

logger = logging.getLogger(__name__)


class OnboardingPhase:
    """Onboarding phase with steps."""
    ANTHROPOMETRY = "anthropometry"
    HEALTH = "health"
    NUTRITION = "nutrition"
    LIFESTYLE = "lifestyle"
    TRAINING = "training"


class OnboardingHandler:
    """
    Onboarding handler.
    Collects the information needed for profile setup and personalization.
    """

    # Complete onboarding steps (25 total)
    STEPS = [
        # Phase 1: Anthropometry (1-5)
        "start",
        "name",
        "gender",
        "date_of_birth",
        "weight_current",
        "weight_target",
        "height",
        "wrist_circumference",
        "primary_goal",
        
        # Phase 2: Health Profile (6-10)
        "health_conditions",
        "surgeries",
        "allergies",
        "medications",
        "injuries_limitations",
        
        # Phase 3: Nutrition & Supplements (11-15)
        "supplements_current",
        "supplement_timing",
        "meals_per_day",
        "meal_times",
        "dietary_preferences",
        "food_dislikes",
        
        # Phase 4: Lifestyle & Schedule (16-20)
        "occupation_type",
        "work_schedule",
        "sleep_schedule",
        "stress_level",
        "bad_habits",
        
        # Phase 5: Training & Activity (21-25)
        "training_experience",
        "training_frequency",
        "training_type",
        "equipment_access",
        "personal_records",
        "complete"
    ]

    # Phase boundaries
    PHASES = {
        OnboardingPhase.ANTHROPOMETRY: (1, 8),
        OnboardingPhase.HEALTH: (9, 13),
        OnboardingPhase.NUTRITION: (14, 19),
        OnboardingPhase.LIFESTYLE: (20, 23),
        OnboardingPhase.TRAINING: (24, 28),
    }

    def __init__(self, telegram_id: str):
        self.telegram_id = telegram_id
        self.current_step_index = 0
        self.collected_data: Dict[str, Any] = {}
        self.is_complete = False
        self.temp_data: Dict[str, Any] = {}

    def get_current_step(self) -> str:
        """Get current step name."""
        if self.current_step_index < len(self.STEPS):
            return self.STEPS[self.current_step_index]
        return "complete"

    def get_current_phase(self) -> str:
        """Get current phase name."""
        step_num = self.current_step_index
        
        if step_num <= 8:
            return OnboardingPhase.ANTHROPOMETRY
        elif step_num <= 13:
            return OnboardingPhase.HEALTH
        elif step_num <= 19:
            return OnboardingPhase.NUTRITION
        elif step_num <= 23:
            return OnboardingPhase.LIFESTYLE
        else:
            return OnboardingPhase.TRAINING

    def get_question(self) -> str:
        """Get question for current step."""
        step = self.get_current_step()
        
        questions = {
            # ==================== PHASE 1: ANTHROPOMETRY ====================
            "start": (
                "👋 **Привет! Я помогу тебе создать персональную систему здоровья.**\n\n"
                "Я соберу информацию о тебе, чтобы давать **максимально точные рекомендации**.\n\n"
                "📋 **Что я узнаю:**\n"
                "• Твои параметры и цели\n"
                "• Состояние здоровья\n"
                "• Питание и добавки\n"
                "• Образ жизни\n"
                "• Тренировки\n\n"
                "⏱ Это займет 5-7 минут. Готов начать?"
            ),
            
            "name": (
                "📝 **Шаг 1/25: Имя**\n\n"
                "Как тебя зовут? (Напиши имя и фамилию)"
            ),
            
            "gender": (
                "🚹🚺 **Шаг 2/25: Пол**\n\n"
                "Выбери номер:\n"
                "1️⃣ Мужской\n"
                "2️⃣ Женский\n"
                "3️⃣ Другой"
            ),
            
            "date_of_birth": (
                "📅 **Шаг 3/25: Дата рождения**\n\n"
                "Когда ты родился? (Формат: ДД.ММ.ГГГГ или ГГГГ-ММ-ДД)"
            ),
            
            "weight_current": (
                "⚖️ **Шаг 4/25: Текущий вес**\n\n"
                "Какой у тебя текущий вес в кг? (Например: 83)"
            ),
            
            "weight_target": (
                "🎯 **Шаг 5/25: Целевой вес**\n\n"
                "К какому весу ты стремишься? (Например: 80)\n"
                "Если не знаешь точно, напиши 'рассчитать' — я помогу."
            ),
            
            "height": (
                "📏 **Шаг 6/25: Рост**\n\n"
                "Какой у тебя рост в см? (Например: 176)"
            ),
            
            "wrist_circumference": (
                "🦴 **Шаг 7/25: Тип телосложения**\n\n"
                "Измерь запястье самой узкой части (см) или выбери:\n"
                "• < 16 см — тонкая кость\n"
                "• 16-18 см — средняя кость\n"
                "• > 18 см — широкая кость\n\n"
                "Напиши число (см) или 'средняя' если не знаешь."
            ),
            
            "primary_goal": (
                "🎯 **Шаг 8/25: Главная цель**\n\n"
                "Выбери номер:\n"
                "1️⃣ Похудение (сжигание жира)\n"
                "2️⃣ Набор мышечной массы\n"
                "3️⃣ Эстетика тела и здоровье\n"
                "4️⃣ Сила и мощность\n"
                "5️⃣ Выносливость\n"
                "6️⃣ Рекомпозиция (одновременно жир/мышцы)\n"
                "7️⃣ Поддержание формы"
            ),
            
            # ==================== PHASE 2: HEALTH ====================
            "health_conditions": (
                "🏥 **Шаг 9/25: Хронические заболевания**\n\n"
                "Есть ли у тебя хронические заболевания?\n"
                "(диабет, гипертония, астма, гастрит и т.д.)\n\n"
                "Напиши список через запятую или 'нет'."
            ),
            
            "surgeries": (
                "🔪 **Шаг 10/25: Перенесенные операции**\n\n"
                "Были ли у тебя операции? Напиши:\n"
                "• Название операции\n"
                "• Когда была (год)\n\n"
                "Пример: 'Аппендэктомия 2020' или 'нет'"
            ),
            
            "allergies": (
                "⚠️ **Шаг 11/25: Аллергии**\n\n"
                "Есть ли у тебя аллергии?\n"
                "(пищевые, на лекарства, контакты)\n\n"
                "Напиши список или 'нет'."
            ),
            
            "medications": (
                "💊 **Шаг 12/25: Лекарства**\n\n"
                "Принимаешь ли ты лекарства постоянно?\n"
                "(не путать со спортивными добавками)\n\n"
                "Напиши список или 'нет'."
            ),
            
            "injuries_limitations": (
                "🩹 **Шаг 13/25: Травмы и ограничения**\n\n"
                "Есть ли у тебя травмы, боли, ограничения по движениям?\n"
                "(спина, колени, плечи и т.д.)\n\n"
                "Напиши список или 'нет'."
            ),
            
            # ==================== PHASE 3: NUTRITION ====================
            "supplements_current": (
                "💪 **Шаг 14/25: Спортивные добавки**\n\n"
                "Какие добавки ты принимаешь?\n"
                "(креатин, протеин, витамины, минералы)\n\n"
                "Напиши список с дозировками или 'нет'."
            ),
            
            "supplement_timing": (
                "⏰ **Шаг 15/25: Когда принимать добавки**\n\n"
                "Укажи время для каждой добавки:\n"
                "Пример: 'Креатин 8:00, Протеин 17:00'\n\n"
                "Или напиши 'стандартно' для авто-настройки."
            ),
            
            "meals_per_day": (
                "🍽️ **Шаг 16/25: Режим питания**\n\n"
                "Сколько раз в день ты обычно ешь?\n"
                "(Например: 3, 4, 5)"
            ),
            
            "meal_times": (
                "🕐 **Шаг 17/25: Время приемов пищи**\n\n"
                "Напиши время каждого приема:\n"
                "Пример: 'Завтрак 8:00, Обед 13:00, Ужин 19:00'"
            ),
            
            "dietary_preferences": (
                "🥗 **Шаг 18/25: Пищевые предпочтения**\n\n"
                "Есть ли особые предпочтения?\n"
                "(вегетарианец, веган, без глютена, без лактозы)\n\n"
                "Напиши или 'нет'."
            ),
            
            "food_dislikes": (
                "🤢 **Шаг 19/25: Нелюбимые продукты**\n\n"
                "Что ты точно не хочешь есть?\n"
                "(Например: брокколи, печень, рыба)\n\n"
                "Напиши список или 'нет'."
            ),
            
            # ==================== PHASE 4: LIFESTYLE ====================
            "occupation_type": (
                "💼 **Шаг 20/25: Род занятий**\n\n"
                "Кем ты работаешь/учишься?\n"
                "1️⃣ Школа/ВУЗ\n"
                "2️⃣ Офисная работа\n"
                "3️⃣ Физическая работа\n"
                "4️⃣ Фриланс/удаленка\n"
                "5️⃣ Домохозяйка/хозяйство\n"
                "6️⃣ Другое"
            ),
            
            "work_schedule": (
                "📅 **Шаг 21/25: График работы/учебы**\n\n"
                "Напиши дни и время:\n"
                "Пример: 'Пн-Пт 9:00-18:00' или 'Сб-Вс выходные'"
            ),
            
            "sleep_schedule": (
                "😴 **Шаг 22/25: Режим сна**\n\n"
                "Во сколько ты обычно:\n"
                "• Ложишься спать\n"
                "• Просыпаешься\n\n"
                "Пример: '23:00-7:00'"
            ),
            
            "stress_level": (
                "📊 **Шаг 23/25: Уровень стресса**\n\n"
                "Оцени свой средний стресс 1-10:\n"
                "1 = совсем нет стресса\n"
                "10 = максимальный стресс\n\n"
                "Напиши число."
            ),
            
            "bad_habits": (
                "🚬 **Шаг 24/25: Вредные привычки**\n\n"
                "Курение: да/нет\n"
                "Алкоголь: никогда/редко/еженедельно/часто\n\n"
                "Пример: 'Курение нет, Алкоголь редко'"
            ),
            
            # ==================== PHASE 5: TRAINING ====================
            "training_experience": (
                "🏋️ **Шаг 25/25: Опыт тренировок**\n\n"
                "Как давно ты тренируешься?\n"
                "1️⃣ Новичок (0-6 месяцев)\n"
                "2️⃣ Средний (6-18 месяцев)\n"
                "3️⃣ Продвинутый (18+ месяцев)"
            ),
            
            "training_frequency": (
                "📆 **Частота тренировок**\n\n"
                "Сколько дней в неделю ты тренируешься?\n"
                "(Например: 3, 4, 5)"
            ),
            
            "training_type": (
                "🏃 **Тип тренировок**\n\n"
                "Что ты предпочитаешь?\n"
                "1️⃣ Силовые (штанга, гантели)\n"
                "2️⃣ Кардио (бег, велосипед)\n"
                "3️⃣ Кроссфит/HIIT\n"
                "4️⃣ Смешанные\n"
                "5️⃣ Дом без оборудования"
            ),
            
            "equipment_access": (
                "🏠 **Доступное оборудование**\n\n"
                "Где и с чем ты тренируешься?\n"
                "1️⃣ Тренажерный зал (полный доступ)\n"
                "2️⃣ Дом (гантели, турник)\n"
                "3️⃣ Улица (турники, брусья)\n"
                "4️⃣ Без оборудования"
            ),
            
            "personal_records": (
                "🏆 **Личные рекорды**\n\n"
                "Твои текущие максимумы (кг):\n"
                "Жим лежа / Присед / Становая\n\n"
                "Пример: '60/80/100' или '0/0/0' если новичок"
            ),
            
            "complete": "✅ Настройка завершена!"
        }
        
        return questions.get(step, "❓ Вопрос не найден")

    def process_answer(self, answer: str) -> Tuple[bool, Optional[str]]:
        """
        Process user answer and move to next step.
        
        Returns:
            Tuple of (success, error_message)
        """
        step = self.get_current_step()
        
        try:
            # ==================== PHASE 1: ANTHROPOMETRY ====================
            
            if step == "start":
                self.current_step_index += 1
                return True, None
            
            elif step == "name":
                if len(answer.strip()) < 2:
                    return False, "Пожалуйста, введи корректное имя"
                self.collected_data["name"] = answer.strip()
                self.current_step_index += 1
                return True, None
            
            elif step == "gender":
                gender_map = {"1": "male", "2": "female", "3": "other"}
                gender = gender_map.get(answer.strip())
                if not gender:
                    return False, "Выбери номер от 1 до 3"
                self.collected_data["gender"] = gender
                self.current_step_index += 1
                return True, None
            
            elif step == "date_of_birth":
                dob = self._parse_date(answer)
                if not dob:
                    return False, "Неверный формат даты. Используй ДД.ММ.ГГГГ"
                
                age = (datetime.now() - datetime.combine(dob, datetime.min.time())).days / 365.25
                if age < 13:
                    return False, "Извини, ботом могут пользоваться лица старше 13 лет"
                if age > 100:
                    return False, "Проверь дату рождения"
                
                self.collected_data["date_of_birth"] = dob
                self.current_step_index += 1
                return True, None
            
            elif step == "weight_current":
                try:
                    weight = float(answer.replace(',', '.'))
                    if weight < 30 or weight > 300:
                        return False, "Введи корректный вес (30-300 кг)"
                    self.collected_data["weight_kg"] = weight
                    self.current_step_index += 1
                    return True, None
                except ValueError:
                    return False, "Введи числовое значение"
            
            elif step == "weight_target":
                if answer.strip().lower() == "рассчитать":
                    self.collected_data["calculate_target_weight"] = True
                else:
                    try:
                        target = float(answer.replace(',', '.'))
                        if target < 30 or target > 300:
                            return False, "Введи корректный вес"
                        self.collected_data["target_weight_kg"] = target
                    except ValueError:
                        return False, "Введи число или 'рассчитать'"
                self.current_step_index += 1
                return True, None
            
            elif step == "height":
                try:
                    height = float(answer.replace(',', '.'))
                    if height < 100 or height > 250:
                        return False, "Введи корректный рост (100-250 см)"
                    self.collected_data["height_cm"] = height
                    self.current_step_index += 1
                    return True, None
                except ValueError:
                    return False, "Введи числовое значение"
            
            elif step == "wrist_circumference":
                if answer.strip().lower() == "средняя":
                    self.collected_data["body_frame"] = "medium"
                else:
                    try:
                        wrist = float(answer.replace(',', '.'))
                        if wrist < 12 or wrist > 25:
                            return False, "Проверь значение (12-25 см)"
                        
                        # Calculate body frame
                        if wrist < 16:
                            frame = "small"
                        elif wrist <= 18:
                            frame = "medium"
                        else:
                            frame = "large"
                        
                        self.collected_data["wrist_circumference_cm"] = wrist
                        self.collected_data["body_frame"] = frame
                    except ValueError:
                        return False, "Введи число или 'средняя'"
                self.current_step_index += 1
                return True, None
            
            elif step == "primary_goal":
                goal_map = {
                    "1": "weight_loss",
                    "2": "muscle_gain",
                    "3": "aesthetic_and_health",
                    "4": "strength",
                    "5": "endurance",
                    "6": "recomposition",
                    "7": "maintenance"
                }
                goal = goal_map.get(answer.strip())
                if not goal:
                    return False, "Выбери номер от 1 до 7"
                self.collected_data["goal"] = goal
                self.current_step_index += 1
                return True, None
            
            # ==================== PHASE 2: HEALTH ====================
            
            elif step == "health_conditions":
                conditions = []
                if answer.strip().lower() not in ["нет", "no", "none", "-"]:
                    conditions = [c.strip() for c in answer.split(",")]
                self.collected_data["health_conditions"] = conditions
                self.current_step_index += 1
                return True, None
            
            elif step == "surgeries":
                surgeries = []
                if answer.strip().lower() not in ["нет", "no", "none", "-"]:
                    # Parse "Operation Year" format
                    surgeries = self._parse_surgeries(answer)
                self.collected_data["surgeries"] = surgeries
                self.current_step_index += 1
                return True, None
            
            elif step == "allergies":
                allergies = []
                if answer.strip().lower() not in ["нет", "no", "none", "-"]:
                    allergies = [a.strip() for a in answer.split(",")]
                self.collected_data["allergies"] = allergies
                self.current_step_index += 1
                return True, None
            
            elif step == "medications":
                medications = []
                if answer.strip().lower() not in ["нет", "no", "none", "-"]:
                    medications = [m.strip() for m in answer.split(",")]
                self.collected_data["medications"] = medications
                self.current_step_index += 1
                return True, None
            
            elif step == "injuries_limitations":
                injuries = []
                if answer.strip().lower() not in ["нет", "no", "none", "-"]:
                    injuries = [i.strip() for i in answer.split(",")]
                self.collected_data["injuries"] = injuries
                self.current_step_index += 1
                return True, None
            
            # ==================== PHASE 3: NUTRITION ====================
            
            elif step == "supplements_current":
                supplements = []
                if answer.strip().lower() not in ["нет", "no", "none", "-"]:
                    supplements = self._parse_supplements(answer)
                self.collected_data["supplements"] = supplements
                self.current_step_index += 1
                return True, None
            
            elif step == "supplement_timing":
                if answer.strip().lower() == "стандартно":
                    self.collected_data["use_standard_supplement_schedule"] = True
                else:
                    self.collected_data["supplement_schedule"] = self._parse_supplement_schedule(answer)
                self.current_step_index += 1
                return True, None
            
            elif step == "meals_per_day":
                try:
                    meals = int(answer.strip())
                    if meals < 1 or meals > 10:
                        return False, "Введи число от 1 до 10"
                    self.collected_data["meals_per_day"] = meals
                    self.current_step_index += 1
                    return True, None
                except ValueError:
                    return False, "Введи число"
            
            elif step == "meal_times":
                meals = self._parse_meal_schedule(answer)
                self.collected_data["meal_schedule"] = meals
                self.current_step_index += 1
                return True, None
            
            elif step == "dietary_preferences":
                preferences = []
                if answer.strip().lower() not in ["нет", "no", "none", "-"]:
                    preferences = [p.strip() for p in answer.split(",")]
                self.collected_data["dietary_preferences"] = preferences
                self.current_step_index += 1
                return True, None
            
            elif step == "food_dislikes":
                dislikes = []
                if answer.strip().lower() not in ["нет", "no", "none", "-"]:
                    dislikes = [d.strip() for d in answer.split(",")]
                self.collected_data["food_dislikes"] = dislikes
                self.current_step_index += 1
                return True, None
            
            # ==================== PHASE 4: LIFESTYLE ====================
            
            elif step == "occupation_type":
                occ_map = {
                    "1": "student",
                    "2": "office",
                    "3": "manual",
                    "4": "freelance",
                    "5": "homemaker",
                    "6": "other"
                }
                occ = occ_map.get(answer.strip())
                if not occ:
                    return False, "Выбери номер от 1 до 6"
                self.collected_data["occupation_type"] = occ
                self.current_step_index += 1
                return True, None
            
            elif step == "work_schedule":
                schedule = self._parse_schedule(answer)
                self.collected_data["work_schedule"] = schedule
                self.current_step_index += 1
                return True, None
            
            elif step == "sleep_schedule":
                sleep = self._parse_sleep_schedule(answer)
                self.collected_data["sleep_schedule"] = sleep
                self.current_step_index += 1
                return True, None
            
            elif step == "stress_level":
                try:
                    stress = int(answer.strip())
                    if stress < 1 or stress > 10:
                        return False, "Введи число от 1 до 10"
                    self.collected_data["stress_level"] = stress
                    self.current_step_index += 1
                    return True, None
                except ValueError:
                    return False, "Введи число от 1 до 10"
            
            elif step == "bad_habits":
                habits = self._parse_bad_habits(answer)
                self.collected_data["bad_habits"] = habits
                self.current_step_index += 1
                return True, None
            
            # ==================== PHASE 5: TRAINING ====================
            
            elif step == "training_experience":
                exp_map = {
                    "1": "beginner",
                    "2": "intermediate",
                    "3": "advanced"
                }
                exp = exp_map.get(answer.strip())
                if not exp:
                    return False, "Выбери номер от 1 до 3"
                self.collected_data["training_level"] = exp
                self.current_step_index += 1
                return True, None
            
            elif step == "training_frequency":
                try:
                    freq = int(answer.strip())
                    if freq < 0 or freq > 7:
                        return False, "Введи число от 0 до 7"
                    self.collected_data["training_days_per_week"] = freq
                    
                    # Set activity level based on frequency
                    if freq == 0:
                        self.collected_data["activity_level"] = "sedentary"
                    elif freq <= 2:
                        self.collected_data["activity_level"] = "light"
                    elif freq <= 4:
                        self.collected_data["activity_level"] = "moderate"
                    elif freq <= 6:
                        self.collected_data["activity_level"] = "active"
                    else:
                        self.collected_data["activity_level"] = "very_active"
                    
                    self.current_step_index += 1
                    return True, None
                except ValueError:
                    return False, "Введи число"
            
            elif step == "training_type":
                type_map = {
                    "1": "strength",
                    "2": "cardio",
                    "3": "hiit",
                    "4": "mixed",
                    "5": "home"
                }
                ttype = type_map.get(answer.strip())
                if not ttype:
                    return False, "Выбери номер от 1 до 5"
                self.collected_data["training_type"] = ttype
                self.current_step_index += 1
                return True, None
            
            elif step == "equipment_access":
                equip_map = {
                    "1": "gym",
                    "2": "home",
                    "3": "outdoor",
                    "4": "none"
                }
                equip = equip_map.get(answer.strip())
                if not equip:
                    return False, "Выбери номер от 1 до 4"
                self.collected_data["equipment_access"] = equip
                self.current_step_index += 1
                return True, None
            
            elif step == "personal_records":
                prs = self._parse_personal_records(answer)
                self.collected_data["personal_records"] = prs
                self.current_step_index += 1
                self.is_complete = True
                return True, None
            
            return False, "Неизвестный шаг"
        
        except Exception as e:
            logger.error(f"Error processing onboarding step {step}: {e}")
            return False, f"Произошла ошибка: {e}"

    # ==================== PARSING HELPERS ====================
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string to date object."""
        formats = ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        return None
    
    def _parse_surgeries(self, answer: str) -> List[Dict]:
        """Parse surgeries string."""
        surgeries = []
        parts = answer.split(",")
        for part in parts:
            part = part.strip()
            # Try to extract year
            match = re.search(r'(\d{4})', part)
            if match:
                year = int(match.group(1))
                name = part.replace(str(year), "").strip()
                surgeries.append({"name": name, "year": year})
            else:
                surgeries.append({"name": part, "year": None})
        return surgeries
    
    def _parse_supplements(self, answer: str) -> List[Dict]:
        """Parse supplements with dosages."""
        supplements = []
        parts = answer.split(",")
        for part in parts:
            part = part.strip()
            # Try to extract dosage (e.g., "5g", "1 capsule")
            dosage_match = re.search(r'(\d+\s*\w+)', part)
            if dosage_match:
                dosage = dosage_match.group(1)
                name = part.replace(dosage, "").strip()
                supplements.append({"name": name, "dosage": dosage})
            else:
                supplements.append({"name": part, "dosage": ""})
        return supplements
    
    def _parse_supplement_schedule(self, answer: str) -> Dict[str, str]:
        """Parse supplement schedule."""
        schedule = {}
        parts = answer.replace(",", " ").split()
        current_supplement = None
        
        for part in parts:
            if ":" in part:
                if current_supplement:
                    schedule[current_supplement] = part
            else:
                current_supplement = part
        
        return schedule
    
    def _parse_meal_schedule(self, answer: str) -> List[Dict]:
        """Parse meal schedule."""
        meals = []
        meal_types = {
            "завтрак": "breakfast", "breakfast": "breakfast",
            "обед": "lunch", "lunch": "lunch",
            "ужин": "dinner", "dinner": "dinner",
            "перекус": "snack", "snack": "snack",
            "второй завтрак": "second_breakfast",
            "второй обед": "second_lunch"
        }
        
        parts = answer.replace(",", " ").split()
        current_meal = None
        
        for part in parts:
            part_lower = part.lower()
            if part_lower in meal_types:
                current_meal = meal_types[part_lower]
            elif current_meal and ":" in part:
                meals.append({"meal_type": current_meal, "time": part})
                current_meal = None
        
        return meals
    
    def _parse_schedule(self, answer: str) -> List[Dict]:
        """Parse work/training schedule."""
        result = []
        day_map = {
            "пн": "mon", "пон": "mon", "понедельник": "mon",
            "вт": "tue", "вторник": "tue",
            "ср": "wed", "среда": "wed",
            "чт": "thu", "четверг": "thu",
            "пт": "fri", "пятница": "fri",
            "сб": "sat", "суббота": "sat",
            "вс": "sun", "воскресенье": "sun"
        }
        
        # Simple parser for "Пн-Пт 9:00-18:00"
        days = []
        time_str = ""
        
        for day_key, day_val in day_map.items():
            if day_key in answer.lower():
                days.append(day_val)
        
        time_match = re.search(r'(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})', answer)
        if time_match:
            time_str = f"{time_match.group(1)}-{time_match.group(2)}"
        
        if days:
            result.append({
                "days_of_week": days,
                "time_range": time_str
            })
        
        return result
    
    def _parse_sleep_schedule(self, answer: str) -> Dict[str, str]:
        """Parse sleep schedule."""
        times = re.findall(r'(\d{1,2}:\d{2})', answer)
        if len(times) >= 2:
            return {"bedtime": times[0], "wake_time": times[1]}
        return {"bedtime": "23:00", "wake_time": "07:00"}
    
    def _parse_bad_habits(self, answer: str) -> Dict[str, str]:
        """Parse bad habits."""
        habits = {"smoking": False, "alcohol": "never"}
        
        answer_lower = answer.lower()
        
        if "курени" in answer_lower:
            if "да" in answer_lower.split("курени")[1][:10]:
                habits["smoking"] = True
        else:
            habits["smoking"] = False
        
        if "алкого" in answer_lower:
            if "часто" in answer_lower:
                habits["alcohol"] = "daily"
            elif "еженедельн" in answer_lower or "недельн" in answer_lower:
                habits["alcohol"] = "weekly"
            elif "редк" in answer_lower:
                habits["alcohol"] = "rarely"
            else:
                habits["alcohol"] = "never"
        
        return habits
    
    def _parse_personal_records(self, answer: str) -> Dict[str, float]:
        """Parse personal records (bench/squat/deadlift)."""
        parts = answer.replace("/", " ").split()
        prs = {}
        
        exercises = ["bench_press", "squat", "deadlift"]
        for i, val in enumerate(parts[:3]):
            try:
                weight = float(val.replace(',', '.'))
                prs[exercises[i]] = weight
            except ValueError:
                prs[exercises[i]] = 0.0
        
        return prs
    
    def get_collected_data(self) -> Dict[str, Any]:
        """Get all collected onboarding data."""
        return self.collected_data.copy()
    
    def is_onboarding_complete(self) -> bool:
        """Check if onboarding is complete."""
        return self.is_complete
    
    def get_progress(self) -> Tuple[int, int, str]:
        """Get onboarding progress (current, total, phase)."""
        return self.current_step_index, len(self.STEPS) - 1, self.get_current_phase()


# Onboarding sessions storage
onboarding_sessions: Dict[str, OnboardingHandler] = {}


def get_or_create_onboarding_session(telegram_id: str) -> OnboardingHandler:
    """Get or create onboarding session for user."""
    if telegram_id not in onboarding_sessions:
        onboarding_sessions[telegram_id] = OnboardingHandler(telegram_id)
    return onboarding_sessions[telegram_id]


def remove_onboarding_session(telegram_id: str):
    """Remove onboarding session after completion."""
    if telegram_id in onboarding_sessions:
        del onboarding_sessions[telegram_id]
