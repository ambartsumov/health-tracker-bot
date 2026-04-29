"""
Test suite for Health Telegram Bot.
Tests for all bot modules.
"""

import pytest
import asyncio
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ==================== FIXTURES ====================

@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "telegram_id": "123456789",
        "name": "Test User",
        "date_of_birth": date(2009, 1, 17),
        "weight_kg": 83.0,
        "height_cm": 175.5,
        "goal": "aesthetic_and_health"
    }


@pytest.fixture
def sample_nutrition_data():
    """Sample nutrition data."""
    return {
        "foods": [
            {
                "name": "Chicken breast",
                "weight_g": 200,
                "calories": 330,
                "protein": 62,
                "fat": 7.2,
                "carbs": 0
            },
            {
                "name": "Rice",
                "weight_g": 150,
                "calories": 195,
                "protein": 4,
                "fat": 0.5,
                "carbs": 42
            }
        ],
        "total_nutrition": {
            "calories": 525,
            "protein": 66,
            "fat": 7.7,
            "carbs": 42
        }
    }


@pytest.fixture
def sample_training_data():
    """Sample training data."""
    return {
        "duration_minutes": 60,
        "muscle_groups": [
            {"group": "chest", "exercises": [
                {"name": "Bench press", "sets": 4, "reps": 10, "weight": 80}
            ]},
            {"group": "triceps", "exercises": [
                {"name": "Tricep dips", "sets": 3, "reps": 12, "weight": 0}
            ]}
        ],
        "calories_burned": 350
    }


@pytest.fixture
def sample_blood_test_results():
    """Sample blood test results."""
    return [
        {"name": "Hemoglobin", "value": 145, "unit": "г/л", "flag": "normal"},
        {"name": "Glucose", "value": 6.5, "unit": "ммоль/л", "flag": "high"},
        {"name": "Vitamin D", "value": 25, "unit": "нг/мл", "flag": "low"}
    ]


# ==================== CONFIG TESTS ====================

class TestConfig:
    """Tests for configuration module."""
    
    def test_config_exists(self):
        """Test that config module exists and is importable."""
        from config import config, Config
        assert config is not None
    
    def test_config_validation(self):
        """Test config validation."""
        from config import config
        is_valid, errors = config.validate()
        # Should have warnings about missing API keys in test environment
        assert isinstance(is_valid, bool)
        assert isinstance(errors, list)
    
    def test_default_user_profile(self):
        """Test default user profile configuration."""
        from config import config
        default_user = config.default_user
        assert default_user is not None
        assert "name" in default_user
        assert "date_of_birth" in default_user
        assert "weight_kg" in default_user


# ==================== DATABASE TESTS ====================

class TestDatabase:
    """Tests for database module."""
    
    @pytest.fixture
    def test_db(self):
        """Create test database."""
        from database.manager import DatabaseManager
        db = DatabaseManager("sqlite:///:memory:")
        db.initialize()
        yield db
    
    def test_create_user(self, test_db, sample_user_data):
        """Test user creation."""
        user = test_db.create_user(
            telegram_id=sample_user_data["telegram_id"],
            name=sample_user_data["name"],
            date_of_birth=sample_user_data["date_of_birth"],
            weight_kg=sample_user_data["weight_kg"],
            height_cm=sample_user_data["height_cm"]
        )
        
        assert user is not None
        assert user.id is not None
        assert user.name == sample_user_data["name"]
        assert user.telegram_id == sample_user_data["telegram_id"]
    
    def test_get_user_by_telegram_id(self, test_db, sample_user_data):
        """Test getting user by Telegram ID."""
        # Create user
        test_db.create_user(
            telegram_id=sample_user_data["telegram_id"],
            name=sample_user_data["name"],
            date_of_birth=sample_user_data["date_of_birth"]
        )
        
        # Get user
        user = test_db.get_user_by_telegram_id(sample_user_data["telegram_id"])
        
        assert user is not None
        assert user.name == sample_user_data["name"]
    
    def test_add_nutrition_log(self, test_db, sample_user_data):
        """Test nutrition log creation."""
        # Create user first
        user = test_db.create_user(
            telegram_id=sample_user_data["telegram_id"],
            name=sample_user_data["name"],
            date_of_birth=sample_user_data["date_of_birth"]
        )
        
        # Add nutrition log
        food_items = [
            {"name": "Apple", "weight_g": 100, "calories": 52, "protein": 0.3, "fat": 0.2, "carbs": 14}
        ]
        
        log = test_db.add_nutrition_log(
            user_id=user.id,
            date=date.today(),
            meal_type="snack",
            food_items=food_items,
            total_calories=52,
            total_protein=0.3,
            total_fat=0.2,
            total_carbs=14
        )
        
        assert log is not None
        assert log.id is not None
        assert log.total_calories == 52
    
    def test_add_training_log(self, test_db, sample_user_data, sample_training_data):
        """Test training log creation."""
        user = test_db.create_user(
            telegram_id=sample_user_data["telegram_id"],
            name=sample_user_data["name"],
            date_of_birth=sample_user_data["date_of_birth"]
        )
        
        log = test_db.add_training_log(
            user_id=user.id,
            date=date.today(),
            duration_minutes=sample_training_data["duration_minutes"],
            muscle_groups=sample_training_data["muscle_groups"],
            calories_burned=sample_training_data["calories_burned"]
        )
        
        assert log is not None
        assert log.duration_minutes == 60


# ==================== PROFILE MODULE TESTS ====================

class TestProfile:
    """Tests for profile module."""
    
    def test_profile_manager_exists(self):
        """Test profile manager import."""
        from modules.profile import profile_manager, UserProfileManager
        assert profile_manager is not None
    
    def test_calculate_bmi(self):
        """Test BMI calculation."""
        from modules.profile import profile_manager
        
        bmi = profile_manager.calculate_bmi(83.0, 175.5)
        assert bmi is not None
        assert 26.0 < bmi < 28.0  # Expected BMI for 83kg/175.5cm
    
    def test_calculate_daily_calories(self, sample_user_data):
        """Test daily calorie calculation."""
        from modules.profile import profile_manager
        from database.manager import DatabaseManager
        
        # Create in-memory database
        db = DatabaseManager("sqlite:///:memory:")
        db.initialize()
        
        user = db.create_user(
            telegram_id=sample_user_data["telegram_id"],
            name=sample_user_data["name"],
            date_of_birth=sample_user_data["date_of_birth"],
            weight_kg=sample_user_data["weight_kg"],
            height_cm=sample_user_data["height_cm"]
        )
        
        calories = profile_manager.calculate_daily_calories(user)
        
        assert calories is not None
        assert "calories" in calories
        assert "protein_g" in calories
        assert calories["calories"] > 0
        assert calories["protein_g"] > 0


# ==================== NUTRITION MODULE TESTS ====================

class TestNutrition:
    """Tests for nutrition module."""
    
    def test_nutrition_manager_exists(self):
        """Test nutrition manager import."""
        from modules.nutrition import nutrition_manager, NutritionManager
        assert nutrition_manager is not None
    
    def test_get_food_database(self):
        """Test food database retrieval."""
        from modules.nutrition import nutrition_manager
        
        db = nutrition_manager.get_food_database()
        assert isinstance(db, dict)
        assert "chicken_breast" in db
        assert "rice" in db
    
    @pytest.mark.asyncio
    async def test_food_recognizer_exists(self):
        """Test food recognizer import."""
        from modules.nutrition import food_recognizer, FoodRecognizer
        assert food_recognizer is not None


# ==================== TRAINING MODULE TESTS ====================

class TestTraining:
    """Tests for training module."""
    
    def test_training_manager_exists(self):
        """Test training manager import."""
        from modules.training import training_manager, TrainingManager
        assert training_manager is not None
    
    def test_muscle_groups_defined(self):
        """Test muscle groups are defined."""
        from modules.training import training_manager
        
        assert len(training_manager.MUSCLE_GROUPS) > 0
        assert "chest" in training_manager.MUSCLE_GROUPS
        assert "back" in training_manager.MUSCLE_GROUPS
    
    def test_get_daily_survey_questions(self):
        """Test survey question generation."""
        from modules.training import training_manager
        
        questions = training_manager.get_daily_survey_questions(1)
        
        assert isinstance(questions, list)
        assert len(questions) > 0
        assert questions[0]["id"] == "trained_today"


# ==================== HEALTH MODULE TESTS ====================

class TestHealth:
    """Tests for health module."""
    
    def test_health_manager_exists(self):
        """Test health manager import."""
        from modules.health import health_manager, HealthManager
        assert health_manager is not None
    
    def test_blood_test_references_defined(self):
        """Test blood test references are defined."""
        from modules.health import health_manager
        
        assert len(health_manager.BLOOD_TEST_REFERENCES) > 0
        assert "hemoglobin" in health_manager.BLOOD_TEST_REFERENCES
        assert "glucose" in health_manager.BLOOD_TEST_REFERENCES
    
    def test_calculate_bmi(self):
        """Test BMI calculation in health module."""
        from modules.health import health_manager
        
        result = health_manager.calculate_bmi(83.0, 175.5)
        
        assert result is not None
        assert "bmi" in result
        assert "category" in result
        assert result["bmi"] > 0


# ==================== REMINDER MODULE TESTS ====================

class TestReminders:
    """Tests for reminder module."""
    
    def test_reminder_manager_exists(self):
        """Test reminder manager import."""
        from modules.reminders import reminder_manager, ReminderManager
        assert reminder_manager is not None
    
    def test_reminder_types_defined(self):
        """Test reminder types are defined."""
        from modules.reminders import ReminderType
        
        assert hasattr(ReminderType, 'MEAL')
        assert hasattr(ReminderType, 'SUPPLEMENT')
        assert hasattr(ReminderType, 'TRAINING')


# ==================== ANALYTICS MODULE TESTS ====================

class TestAnalytics:
    """Tests for analytics module."""
    
    def test_report_generator_exists(self):
        """Test report generator import."""
        from modules.analytics import report_generator, ExcelReportGenerator
        assert report_generator is not None


# ==================== INTEGRATION TESTS ====================

class TestIntegrations:
    """Tests for API integrations."""
    
    def test_deepseek_client_exists(self):
        """Test DeepSeek client import."""
        from modules.integrations import deepseek_client, DeepSeekClient
        assert deepseek_client is not None
    
    def test_deepseek_client_initialization(self):
        """Test DeepSeek client initialization."""
        from modules.integrations import deepseek_client
        
        # Should have is_available attribute
        assert hasattr(deepseek_client, 'is_available')


# ==================== UTILS TESTS ====================

class TestUtils:
    """Tests for utility modules."""
    
    def test_image_processor_exists(self):
        """Test image processor import."""
        from utils import image_processor, ImageProcessor
        assert image_processor is not None
    
    def test_security_manager_exists(self):
        """Test security manager import."""
        from utils import security_manager, SecurityManager
        assert security_manager is not None
    
    def test_privacy_manager_exists(self):
        """Test privacy manager import."""
        from utils import privacy_manager, PrivacyManager
        assert privacy_manager is not None
    
    def test_security_manager_encrypt_decrypt(self):
        """Test encryption/decryption."""
        from utils import security_manager
        
        test_data = {"sensitive": "data", "number": 123}
        encrypted = security_manager.encrypt_sensitive_data(test_data)
        
        assert encrypted is not None
        assert encrypted != test_data
        
        decrypted = security_manager.decrypt_sensitive_data(encrypted)
        assert decrypted == test_data


# ==================== ONBOARDING TESTS ====================

class TestOnboarding:
    """Tests for onboarding module."""
    
    def test_onboarding_handler_exists(self):
        """Test onboarding handler import."""
        from modules.onboarding import OnboardingHandler
        assert OnboardingHandler is not None
    
    def test_onboarding_steps_defined(self):
        """Test onboarding steps are defined."""
        from modules.onboarding import OnboardingHandler
        
        handler = OnboardingHandler("test_id")
        assert len(handler.STEPS) > 0
        assert "start" in handler.STEPS
        assert "complete" in handler.STEPS
    
    def test_onboarding_process(self):
        """Test onboarding process."""
        from modules.onboarding import OnboardingHandler
        
        handler = OnboardingHandler("test_id")
        
        # Start onboarding
        assert handler.get_current_step() == "start"
        
        # Process first answer
        success, error = handler.process_answer("yes")
        assert success is True
        assert handler.get_current_step() == "name"
        
        # Process name
        success, error = handler.process_answer("Test User")
        assert success is True


# ==================== MAIN BOT TESTS ====================

class TestBot:
    """Tests for main bot."""
    
    def test_bot_module_exists(self):
        """Test bot module import."""
        import bot
        assert bot is not None
    
    def test_bot_class_exists(self):
        """Test HealthBot class exists."""
        from bot import HealthBot
        assert HealthBot is not None


# ==================== PERFORMANCE TESTS ====================

class TestPerformance:
    """Performance tests."""
    
    def test_database_query_performance(self):
        """Test database query performance."""
        from database.manager import DatabaseManager
        import time
        
        db = DatabaseManager("sqlite:///:memory:")
        db.initialize()
        
        # Create multiple users
        start = time.time()
        for i in range(100):
            db.create_user(
                telegram_id=f"user_{i}",
                name=f"User {i}",
                date_of_birth=date(2000, 1, 1)
            )
        create_time = time.time() - start
        
        # Query users
        start = time.time()
        users = db.get_all_users()
        query_time = time.time() - start
        
        assert create_time < 5.0  # Should create 100 users in under 5 seconds
        assert query_time < 1.0  # Should query in under 1 second
        assert len(users) == 100


# ==================== RUN TESTS ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
