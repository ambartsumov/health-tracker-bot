"""
Database models for Health Bot.
Complete SQLAlchemy ORM models with full personalization support.
"""

from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, Date,
    ForeignKey, Text, Boolean, JSON, Enum, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import enum

Base = declarative_base()


class GoalType(enum.Enum):
    """User goal types."""
    WEIGHT_LOSS = "weight_loss"
    MUSCLE_GAIN = "muscle_gain"
    AESTHETIC_AND_HEALTH = "aesthetic_and_health"
    ENDURANCE = "endurance"
    MAINTENANCE = "maintenance"
    STRENGTH = "strength"
    RECOMPOSITION = "recomposition"


class GenderType(enum.Enum):
    """User gender."""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class BodyFrameType(enum.Enum):
    """Body frame size based on wrist circumference."""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class ActivityLevel(enum.Enum):
    """Physical activity levels."""
    SEDENTARY = "sedentary"  # 1.2
    LIGHT = "light"  # 1.375
    MODERATE = "moderate"  # 1.55
    ACTIVE = "active"  # 1.725
    VERY_ACTIVE = "very_active"  # 1.9


class TrainingLevel(enum.Enum):
    """Training experience level."""
    BEGINNER = "beginner"  # 0-6 months
    INTERMEDIATE = "intermediate"  # 6-18 months
    ADVANCED = "advanced"  # 18+ months


class User(Base):
    """User profile model with extended personalization fields."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(String, unique=True, nullable=False, index=True)
    
    # Basic info
    name = Column(String, nullable=False)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(Enum(GenderType), default=GenderType.MALE)
    
    # Anthropometry
    weight_kg = Column(Float, default=0.0)
    target_weight_kg = Column(Float, nullable=True)  # Goal weight
    height_cm = Column(Float, default=0.0)
    wrist_circumference_cm = Column(Float, nullable=True)  # For frame calculation
    body_frame = Column(Enum(BodyFrameType), nullable=True)  # Calculated from wrist
    
    # Goals
    goal = Column(Enum(GoalType), default=GoalType.AESTHETIC_AND_HEALTH)
    activity_level = Column(Enum(ActivityLevel), default=ActivityLevel.MODERATE)
    training_level = Column(Enum(TrainingLevel), default=TrainingLevel.BEGINNER)
    
    # Health
    health_conditions = Column(JSON, default=list)  # Chronic conditions, injuries
    surgeries = Column(JSON, default=list)  # Past surgeries with dates
    allergies = Column(JSON, default=list)  # Food, drug allergies
    medications = Column(JSON, default=list)  # Current medications
    
    # Lifestyle
    occupation_type = Column(String, default="student")  # student, office, manual, freelance, homemaker
    stress_level = Column(Integer, default=5)  # 1-10 average stress
    sleep_quality = Column(Integer, default=5)  # 1-10 average quality
    
    # Bad habits
    smoking = Column(Boolean, default=False)
    alcohol_frequency = Column(String, default="never")  # never, rarely, weekly, daily
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    onboarding_completed_at = Column(DateTime, nullable=True)
    is_default_user = Column(Boolean, default=False)  # For default user creation

    # Relationships
    supplements = relationship("Supplement", back_populates="user", cascade="all, delete-orphan")
    schedule_items = relationship("ScheduleItem", back_populates="user", cascade="all, delete-orphan")
    meal_schedules = relationship("MealSchedule", back_populates="user", cascade="all, delete-orphan")
    nutrition_logs = relationship("NutritionLog", back_populates="user", cascade="all, delete-orphan")
    training_logs = relationship("TrainingLog", back_populates="user", cascade="all, delete-orphan")
    health_metrics = relationship("HealthMetric", back_populates="user", cascade="all, delete-orphan")
    blood_tests = relationship("BloodTest", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", cascade="all, delete-orphan", uselist=False)
    symptom_logs = relationship("SymptomLog", back_populates="user", cascade="all, delete-orphan")
    water_intakes = relationship("WaterIntake", back_populates="user", cascade="all, delete-orphan")
    personal_records = relationship("PersonalRecord", back_populates="user", cascade="all, delete-orphan")
    achievements = relationship("Achievement", back_populates="user", cascade="all, delete-orphan")
    deload_schedules = relationship("DeloadSchedule", back_populates="user", cascade="all, delete-orphan")
    reminder_logs = relationship("ReminderLog", back_populates="user", cascade="all, delete-orphan")
    excel_reports = relationship("ExcelReport", back_populates="user", cascade="all, delete-orphan")

    def get_age(self) -> int:
        """Calculate user age."""
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    def calculate_bmi(self) -> Optional[float]:
        """Calculate Body Mass Index."""
        if not self.weight_kg or not self.height_cm or self.height_cm <= 0:
            return None
        height_m = self.height_cm / 100
        return round(self.weight_kg / (height_m ** 2), 2)

    def calculate_bmr(self) -> float:
        """Calculate Basal Metabolic Rate (Mifflin-St Jeor)."""
        weight = self.weight_kg
        height = self.height_cm
        age = self.get_age()
        
        if self.gender == GenderType.FEMALE:
            bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
        else:  # MALE or OTHER
            bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
        
        return round(bmr, 0)

    def calculate_tdee(self) -> float:
        """Calculate Total Daily Energy Expenditure."""
        bmr = self.calculate_bmr()
        
        activity_multipliers = {
            ActivityLevel.SEDENTARY: 1.2,
            ActivityLevel.LIGHT: 1.375,
            ActivityLevel.MODERATE: 1.55,
            ActivityLevel.ACTIVE: 1.725,
            ActivityLevel.VERY_ACTIVE: 1.9
        }
        
        multiplier = activity_multipliers.get(self.activity_level, 1.55)
        return round(bmr * multiplier, 0)

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', telegram_id='{self.telegram_id}')>"


class Supplement(Base):
    """User supplements with food timing."""
    __tablename__ = "supplements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String, nullable=False)
    dosage = Column(String, default="")  # e.g., "5g", "1 capsule"
    frequency = Column(String, default="daily")  # daily, weekly, as_needed
    
    # Timing
    reminder_time = Column(String)  # HH:MM format
    time_of_day = Column(String, default="any")  # morning, afternoon, evening, night
    
    # Food relation
    with_food = Column(Boolean, default=True)  # Take with food?
    food_type = Column(String, default="any")  # fatty, carb, protein, any
    
    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="supplements")

    def __repr__(self):
        return f"<Supplement(id={self.id}, name='{self.name}', user_id={self.user_id})>"


class ScheduleItem(Base):
    """User schedule items (work, training, etc.)."""
    __tablename__ = "schedule_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    item_type = Column(String, nullable=False, index=True)  # work, training, school, etc.
    name = Column(String, nullable=False)
    days_of_week = Column(JSON, default=[])  # [mon, tue, wed, thu, fri, sat, sun]
    start_time = Column(String)  # HH:MM format
    end_time = Column(String)  # HH:MM format
    duration_minutes = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="schedule_items")

    def __repr__(self):
        return f"<ScheduleItem(id={self.id}, type='{self.item_type}', user_id={self.user_id})>"


class MealSchedule(Base):
    """User meal schedule."""
    __tablename__ = "meal_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    meal_type = Column(String, nullable=False)  # breakfast, lunch, dinner, snack
    time = Column(String, nullable=False)  # HH:MM format
    reminder_offset_minutes = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="meal_schedules")

    __table_args__ = (
        UniqueConstraint('user_id', 'meal_type', name='unique_user_meal_type'),
    )

    def __repr__(self):
        return f"<MealSchedule(id={self.id}, type='{self.meal_type}', user_id={self.user_id})>"


class NutritionLog(Base):
    """Daily nutrition log."""
    __tablename__ = "nutrition_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    meal_type = Column(String, nullable=False, index=True)
    
    food_items = Column(JSON, default=list)  # [{name, weight_g, calories, protein, fat, carbs}]
    total_calories = Column(Float, default=0.0)
    total_protein = Column(Float, default=0.0)
    total_fat = Column(Float, default=0.0)
    total_carbs = Column(Float, default=0.0)
    total_fiber = Column(Float, default=0.0)  # NEW: fiber tracking
    
    photo_path = Column(String, nullable=True)
    is_ai_recognized = Column(Boolean, default=False)
    is_manually_edited = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="nutrition_logs")

    __table_args__ = (
        UniqueConstraint('user_id', 'date', 'meal_type', name='unique_user_date_meal'),
        Index('idx_nutrition_user_date', 'user_id', 'date'),
    )

    def __repr__(self):
        return f"<NutritionLog(id={self.id}, user_id={self.user_id}, date={self.date})>"


class DailyCalorieTarget(Base):
    """User daily calorie and macro targets."""
    __tablename__ = "daily_calorie_targets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    calorie_target = Column(Float, default=2500.0)
    protein_target = Column(Float, default=150.0)
    fat_target = Column(Float, default=80.0)
    carb_target = Column(Float, default=300.0)
    fiber_target = Column(Float, default=30.0)  # NEW
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='unique_user_date_target'),
    )

    def __repr__(self):
        return f"<DailyCalorieTarget(id={self.id}, user_id={self.user_id}, date={self.date})>"


class TrainingLog(Base):
    """Training session log with RPE and progressive overload."""
    __tablename__ = "training_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    # Basic info
    duration_minutes = Column(Integer, default=0)
    training_type = Column(String, default="strength")  # strength, cardio, hiit, mobility
    
    # Exercises with RPE
    muscle_groups = Column(JSON, default=list)  # [{group, exercises: [{name, sets, reps, weight, rpe}]}]
    total_volume = Column(Float, default=0.0)  # Total weight lifted (tons)
    calories_burned = Column(Float, default=0.0)
    
    # Intensity
    average_rpe = Column(Float, default=0.0)  # Rate of Perceived Exertion 1-10
    rir = Column(Integer, default=0)  # Reps In Reserve
    
    # Comparison with previous
    volume_change_percent = Column(Float, default=0.0)  # vs last workout
    is_pr_day = Column(Boolean, default=False)  # Personal record achieved
    
    notes = Column(Text, default="")
    
    # Source
    is_from_samsung_health = Column(Boolean, default=False)
    is_from_daily_survey = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="training_logs")

    __table_args__ = (
        Index('idx_training_user_date', 'user_id', 'date'),
        Index('idx_training_user_type', 'user_id', 'training_type'),
    )

    def __repr__(self):
        return f"<TrainingLog(id={self.id}, user_id={self.user_id}, date={self.date})>"


class HealthMetric(Base):
    """Health metrics from Samsung Health or manual input."""
    __tablename__ = "health_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Body composition
    weight_kg = Column(Float, nullable=True)
    body_fat_percent = Column(Float, nullable=True)
    muscle_mass_kg = Column(Float, nullable=True)
    water_percent = Column(Float, nullable=True)
    bmi = Column(Float, nullable=True)
    waist_circumference_cm = Column(Float, nullable=True)  # NEW
    hip_circumference_cm = Column(Float, nullable=True)  # NEW

    # Vitals
    heart_rate_bpm = Column(Integer, nullable=True)
    resting_heart_rate = Column(Integer, nullable=True)  # NEW
    blood_pressure_systolic = Column(Integer, nullable=True)
    blood_pressure_diastolic = Column(Integer, nullable=True)
    spo2_percent = Column(Integer, nullable=True)
    stress_level = Column(Integer, nullable=True)  # 1-100
    hrv = Column(Integer, nullable=True)  # Heart Rate Variability (NEW)

    # Sleep
    sleep_duration_minutes = Column(Integer, nullable=True)
    sleep_quality = Column(Integer, nullable=True)  # 1-100
    sleep_deep_minutes = Column(Integer, nullable=True)
    sleep_light_minutes = Column(Integer, nullable=True)
    sleep_rem_minutes = Column(Integer, nullable=True)
    sleep_awake_minutes = Column(Integer, nullable=True)  # NEW

    # Activity
    steps = Column(Integer, default=0)
    calories_burned = Column(Float, default=0.0)
    active_minutes = Column(Integer, default=0)
    floors_climbed = Column(Integer, default=0)  # NEW

    # Source
    source = Column(String, default="manual")  # manual, samsung_health, screenshot

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="health_metrics")

    __table_args__ = (
        Index('idx_health_user_date', 'user_id', 'date'),
    )

    def __repr__(self):
        return f"<HealthMetric(id={self.id}, user_id={self.user_id}, date={self.date})>"


class BloodTest(Base):
    """Blood test results with red flag alerts."""
    __tablename__ = "blood_tests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    photo_path = Column(String, nullable=True)
    results = Column(JSON, default=list)  # [{name, value, unit, reference_min, reference_max, flag}]
    
    # AI analysis
    analysis = Column(Text, default="")  # AI-generated analysis
    recommendations = Column(JSON, default=list)  # AI-generated recommendations
    
    # Alerts
    has_red_flags = Column(Boolean, default=False)  # Critical values detected
    red_flag_details = Column(JSON, default=list)  # [{marker, value, urgency}]
    requires_doctor_consultation = Column(Boolean, default=False)
    
    is_ai_analyzed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="blood_tests")

    __table_args__ = (
        Index('idx_blood_user_date', 'user_id', 'date'),
    )

    def __repr__(self):
        return f"<BloodTest(id={self.id}, user_id={self.user_id}, date={self.date})>"


class SymptomLog(Base):
    """Daily symptom tracking for health monitoring."""
    __tablename__ = "symptom_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Pain tracking
    pain_level = Column(Integer, default=0)  # 0-10 scale
    pain_locations = Column(JSON, default=list)  # ["head", "chest", "back", "joints"]
    
    # General symptoms
    fatigue_level = Column(Integer, default=0)  # 0-10
    mood_level = Column(Integer, default=5)  # 1-10
    energy_level = Column(Integer, default=5)  # 1-10
    stress_level = Column(Integer, default=5)  # 1-10
    
    # Specific symptoms
    symptoms = Column(JSON, default=list)  # ["headache", "nausea", "dizziness", "shortness_of_breath"]
    symptom_severity = Column(JSON, default=dict)  # {symptom_name: severity_1_10}
    
    # Recovery indicators
    muscle_soreness = Column(Integer, default=0)  # 0-10 (DOMS)
    joint_pain = Column(Integer, default=0)  # 0-10
    sleep_quality = Column(Integer, default=5)  # 1-10
    
    # Notes
    notes = Column(Text, default="")
    
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="symptom_logs")

    __table_args__ = (
        Index('idx_symptom_user_date', 'user_id', 'date'),
    )

    def __repr__(self):
        return f"<SymptomLog(id={self.id}, user_id={self.user_id}, date={self.date})>"


class WaterIntake(Base):
    """Daily water intake tracking."""
    __tablename__ = "water_intakes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    amount_ml = Column(Integer, nullable=False)  # Amount in ml (typically 250ml per entry)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Context
    around_workout = Column(Boolean, default=False)  # Drank around workout?
    with_supplement = Column(String, nullable=True)  # Which supplement taken with water
    
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="water_intakes")

    __table_args__ = (
        Index('idx_water_user_date', 'user_id', 'date'),
    )

    def __repr__(self):
        return f"<WaterIntake(id={self.id}, user_id={self.user_id}, amount={self.amount_ml}ml)>"


class PersonalRecord(Base):
    """Personal records for exercises."""
    __tablename__ = "personal_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    exercise_name = Column(String, nullable=False, index=True)  # "bench_press", "squat", "deadlift"
    muscle_group = Column(String, nullable=True)  # "chest", "legs", "back"
    
    # Record details
    max_weight = Column(Float, nullable=False)  # kg
    reps = Column(Integer, default=1)  # Reps at max weight
    date_achieved = Column(Date, nullable=False)
    
    # 1RM calculation
    estimated_1rm = Column(Float, nullable=True)  # Calculated 1 rep max
    
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="personal_records")

    __table_args__ = (
        UniqueConstraint('user_id', 'exercise_name', name='unique_user_exercise_pr'),
    )

    def __repr__(self):
        return f"<PersonalRecord(id={self.id}, exercise='{self.exercise_name}', weight={self.max_weight}kg)>"


class Achievement(Base):
    """User achievements and milestones."""
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Achievement type
    achievement_type = Column(String, nullable=False, index=True)  # streak, milestone, first_time
    
    # Details
    name = Column(String, nullable=False)  # "7-Day Streak", "First PR"
    description = Column(Text, default="")
    icon = Column(String, default="🏆")  # Emoji icon
    
    # Progress
    current_value = Column(Integer, default=0)  # Current streak count, etc.
    target_value = Column(Integer, default=0)  # Target for completion
    is_completed = Column(Boolean, default=False)
    
    # Timestamps
    unlocked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="achievements")

    __table_args__ = (
        Index('idx_achievement_user_type', 'user_id', 'achievement_type'),
    )

    def __repr__(self):
        return f"<Achievement(id={self.id}, name='{self.name}', user_id={self.user_id})>"


class DeloadSchedule(Base):
    """Deload week tracking for periodization."""
    __tablename__ = "deload_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Cycle tracking
    cycle_start_date = Column(Date, nullable=False)
    cycle_week_number = Column(Integer, nullable=False)  # Which week of training cycle (1-8)
    
    # Status
    is_deload_week = Column(Boolean, default=False)  # Should reduce volume
    deload_completed = Column(Boolean, default=False)
    
    # Recommendations
    recommended_volume_reduction = Column(Integer, default=50)  # Reduce by 50%
    notes = Column(Text, default="")
    
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="deload_schedules")

    __table_args__ = (
        Index('idx_deload_user_cycle', 'user_id', 'cycle_start_date'),
    )

    def __repr__(self):
        return f"<DeloadSchedule(id={self.id}, user_id={self.user_id}, week={self.cycle_week_number})>"


class UserSettings(Base):
    """User settings and preferences."""
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Notifications
    enable_meal_reminders = Column(Boolean, default=True)
    enable_supplement_reminders = Column(Boolean, default=True)
    enable_training_reminders = Column(Boolean, default=True)
    enable_daily_summary = Column(Boolean, default=True)
    enable_water_reminders = Column(Boolean, default=True)  # NEW
    enable_symptom_tracking = Column(Boolean, default=True)  # NEW
    daily_summary_time = Column(String, default="22:00")

    # Preferences
    language = Column(String, default="ru")
    timezone = Column(String, default="Europe/Moscow")
    measurement_system = Column(String, default="metric")  # metric, imperial

    # Samsung Health integration
    samsung_health_enabled = Column(Boolean, default=False)
    samsung_health_sync_interval = Column(Integer, default=3600)  # seconds

    # AI preferences
    deepseek_enabled = Column(Boolean, default=True)
    gemini_enabled = Column(Boolean, default=True)

    # Gamification
    gamification_enabled = Column(Boolean, default=True)  # Enable achievements/XP

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="settings")

    def __repr__(self):
        return f"<UserSettings(id={self.id}, user_id={self.user_id})>"


class ReminderLog(Base):
    """Log of sent reminders."""
    __tablename__ = "reminder_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    reminder_type = Column(String, nullable=False, index=True)  # meal, supplement, training, water, symptom
    scheduled_time = Column(DateTime, nullable=False, index=True)
    sent_time = Column(DateTime, nullable=True)
    is_sent = Column(Boolean, default=False)
    message_text = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="reminder_logs")

    __table_args__ = (
        Index('idx_reminder_user_time', 'user_id', 'scheduled_time'),
    )

    def __repr__(self):
        return f"<ReminderLog(id={self.id}, user_id={self.user_id}, type={self.reminder_type})>"


class ExcelReport(Base):
    """Generated Excel reports."""
    __tablename__ = "excel_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    report_type = Column(String, nullable=False)  # weekly, monthly
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)
    file_path = Column(String, nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="excel_reports")

    def __repr__(self):
        return f"<ExcelReport(id={self.id}, user_id={self.user_id}, type={self.report_type})>"


# ==================== DATABASE ENGINE ====================

def get_engine(database_url: str, echo: bool = False):
    """Create database engine."""
    return create_engine(database_url, echo=echo, pool_pre_ping=True)


def get_session_factory(engine):
    """Create session factory."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db(engine):
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def drop_db(engine):
    """Drop all tables (for development)."""
    Base.metadata.drop_all(bind=engine)
