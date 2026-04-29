"""Initial database schema

Revision ID: 001_initial
Revises: 
Create Date: 2026-03-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('telegram_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=False),
        sa.Column('gender', sa.Enum('MALE', 'FEMALE', 'OTHER', name='goaltype'), nullable=True),
        sa.Column('weight_kg', sa.Float(), default=0.0),
        sa.Column('target_weight_kg', sa.Float(), nullable=True),
        sa.Column('height_cm', sa.Float(), default=0.0),
        sa.Column('wrist_circumference_cm', sa.Float(), nullable=True),
        sa.Column('body_frame', sa.Enum('SMALL', 'MEDIUM', 'LARGE', name='bodyframetype'), nullable=True),
        sa.Column('goal', sa.Enum('WEIGHT_LOSS', 'MUSCLE_GAIN', 'AESTHETIC_AND_HEALTH', 'ENDURANCE', 'MAINTENANCE', 'STRENGTH', 'RECOMPOSITION', name='goaltype'), default='aesthetic_and_health'),
        sa.Column('activity_level', sa.Enum('SEDENTARY', 'LIGHT', 'MODERATE', 'ACTIVE', 'VERY_ACTIVE', name='activitylevel'), default='moderate'),
        sa.Column('training_level', sa.Enum('BEGINNER', 'INTERMEDIATE', 'ADVANCED', name='traininglevel'), default='beginner'),
        sa.Column('health_conditions', sa.JSON(), default=list),
        sa.Column('surgeries', sa.JSON(), default=list),
        sa.Column('allergies', sa.JSON(), default=list),
        sa.Column('medications', sa.JSON(), default=list),
        sa.Column('occupation_type', sa.String(), default='student'),
        sa.Column('stress_level', sa.Integer(), default=5),
        sa.Column('sleep_quality', sa.Integer(), default=5),
        sa.Column('smoking', sa.Boolean(), default=False),
        sa.Column('alcohol_frequency', sa.String(), default='never'),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('onboarding_completed_at', sa.DateTime(), nullable=True),
        sa.Column('is_default_user', sa.Boolean(), default=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_telegram_id'), 'users', ['telegram_id'], unique=True)
    op.create_index(op.f('ix_users_created_at'), 'users', ['created_at'], unique=False)

    # Supplements table
    op.create_table('supplements',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('dosage', sa.String(), default=''),
        sa.Column('frequency', sa.String(), default='daily'),
        sa.Column('reminder_time', sa.String()),
        sa.Column('time_of_day', sa.String(), default='any'),
        sa.Column('with_food', sa.Boolean(), default=True),
        sa.Column('food_type', sa.String(), default='any'),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_supplements_user_id'), 'supplements', ['user_id'], unique=False)

    # Schedule items table
    op.create_table('schedule_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('item_type', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('days_of_week', sa.JSON(), default=list),
        sa.Column('start_time', sa.String()),
        sa.Column('end_time', sa.String()),
        sa.Column('duration_minutes', sa.Integer(), default=0),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_schedule_items_user_id'), 'schedule_items', ['user_id'], unique=False)
    op.create_index(op.f('ix_schedule_items_item_type'), 'schedule_items', ['item_type'], unique=False)

    # Meal schedules table
    op.create_table('meal_schedules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('meal_type', sa.String(), nullable=False),
        sa.Column('time', sa.String(), nullable=False),
        sa.Column('reminder_offset_minutes', sa.Integer(), default=30),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'meal_type', name='unique_user_meal_type')
    )
    op.create_index(op.f('ix_meal_schedules_user_id'), 'meal_schedules', ['user_id'], unique=False)

    # Nutrition logs table
    op.create_table('nutrition_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('meal_type', sa.String(), nullable=False),
        sa.Column('food_items', sa.JSON(), default=list),
        sa.Column('total_calories', sa.Float(), default=0.0),
        sa.Column('total_protein', sa.Float(), default=0.0),
        sa.Column('total_fat', sa.Float(), default=0.0),
        sa.Column('total_carbs', sa.Float(), default=0.0),
        sa.Column('total_fiber', sa.Float(), default=0.0),
        sa.Column('photo_path', sa.String(), nullable=True),
        sa.Column('is_ai_recognized', sa.Boolean(), default=False),
        sa.Column('is_manually_edited', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'date', 'meal_type', name='unique_user_date_meal')
    )
    op.create_index(op.f('ix_nutrition_logs_user_id'), 'nutrition_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_nutrition_logs_date'), 'nutrition_logs', ['date'], unique=False)
    op.create_index(op.f('ix_nutrition_logs_meal_type'), 'nutrition_logs', ['meal_type'], unique=False)

    # Daily calorie targets table
    op.create_table('daily_calorie_targets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('calorie_target', sa.Float(), default=2500.0),
        sa.Column('protein_target', sa.Float(), default=150.0),
        sa.Column('fat_target', sa.Float(), default=80.0),
        sa.Column('carb_target', sa.Float(), default=300.0),
        sa.Column('fiber_target', sa.Float(), default=30.0),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'date', name='unique_user_date_target')
    )
    op.create_index(op.f('ix_daily_calorie_targets_user_id'), 'daily_calorie_targets', ['user_id'], unique=False)
    op.create_index(op.f('ix_daily_calorie_targets_date'), 'daily_calorie_targets', ['date'], unique=False)

    # Training logs table
    op.create_table('training_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), default=0),
        sa.Column('training_type', sa.String(), default='strength'),
        sa.Column('muscle_groups', sa.JSON(), default=list),
        sa.Column('total_volume', sa.Float(), default=0.0),
        sa.Column('calories_burned', sa.Float(), default=0.0),
        sa.Column('average_rpe', sa.Float(), default=0.0),
        sa.Column('rir', sa.Integer(), default=0),
        sa.Column('volume_change_percent', sa.Float(), default=0.0),
        sa.Column('is_pr_day', sa.Boolean(), default=False),
        sa.Column('notes', sa.Text()),
        sa.Column('is_from_samsung_health', sa.Boolean(), default=False),
        sa.Column('is_from_daily_survey', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_training_logs_user_id'), 'training_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_training_logs_date'), 'training_logs', ['date'], unique=False)

    # Health metrics table
    op.create_table('health_metrics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), default=sa.func.now()),
        sa.Column('weight_kg', sa.Float(), nullable=True),
        sa.Column('body_fat_percent', sa.Float(), nullable=True),
        sa.Column('muscle_mass_kg', sa.Float(), nullable=True),
        sa.Column('water_percent', sa.Float(), nullable=True),
        sa.Column('bmi', sa.Float(), nullable=True),
        sa.Column('waist_circumference_cm', sa.Float(), nullable=True),
        sa.Column('hip_circumference_cm', sa.Float(), nullable=True),
        sa.Column('heart_rate_bpm', sa.Integer(), nullable=True),
        sa.Column('resting_heart_rate', sa.Integer(), nullable=True),
        sa.Column('blood_pressure_systolic', sa.Integer(), nullable=True),
        sa.Column('blood_pressure_diastolic', sa.Integer(), nullable=True),
        sa.Column('spo2_percent', sa.Integer(), nullable=True),
        sa.Column('stress_level', sa.Integer(), nullable=True),
        sa.Column('hrv', sa.Integer(), nullable=True),
        sa.Column('sleep_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('sleep_quality', sa.Integer(), nullable=True),
        sa.Column('sleep_deep_minutes', sa.Integer(), nullable=True),
        sa.Column('sleep_light_minutes', sa.Integer(), nullable=True),
        sa.Column('sleep_rem_minutes', sa.Integer(), nullable=True),
        sa.Column('sleep_awake_minutes', sa.Integer(), nullable=True),
        sa.Column('steps', sa.Integer(), default=0),
        sa.Column('calories_burned', sa.Float(), default=0.0),
        sa.Column('active_minutes', sa.Integer(), default=0),
        sa.Column('floors_climbed', sa.Integer(), default=0),
        sa.Column('source', sa.String(), default='manual'),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_health_metrics_user_id'), 'health_metrics', ['user_id'], unique=False)
    op.create_index(op.f('ix_health_metrics_date'), 'health_metrics', ['date'], unique=False)
    op.create_index(op.f('ix_health_metrics_created_at'), 'health_metrics', ['created_at'], unique=False)

    # Blood tests table
    op.create_table('blood_tests',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('photo_path', sa.String(), nullable=True),
        sa.Column('results', sa.JSON(), default=list),
        sa.Column('analysis', sa.Text()),
        sa.Column('recommendations', sa.JSON(), default=list),
        sa.Column('has_red_flags', sa.Boolean(), default=False),
        sa.Column('red_flag_details', sa.JSON(), default=list),
        sa.Column('requires_doctor_consultation', sa.Boolean(), default=False),
        sa.Column('is_ai_analyzed', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_blood_tests_user_id'), 'blood_tests', ['user_id'], unique=False)
    op.create_index(op.f('ix_blood_tests_date'), 'blood_tests', ['date'], unique=False)

    # Symptom logs table
    op.create_table('symptom_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), default=sa.func.now()),
        sa.Column('pain_level', sa.Integer(), default=0),
        sa.Column('pain_locations', sa.JSON(), default=list),
        sa.Column('fatigue_level', sa.Integer(), default=0),
        sa.Column('mood_level', sa.Integer(), default=5),
        sa.Column('energy_level', sa.Integer(), default=5),
        sa.Column('stress_level', sa.Integer(), default=5),
        sa.Column('symptoms', sa.JSON(), default=list),
        sa.Column('symptom_severity', sa.JSON(), default=dict),
        sa.Column('muscle_soreness', sa.Integer(), default=0),
        sa.Column('joint_pain', sa.Integer(), default=0),
        sa.Column('sleep_quality', sa.Integer(), default=5),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_symptom_logs_user_id'), 'symptom_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_symptom_logs_date'), 'symptom_logs', ['date'], unique=False)

    # Water intakes table
    op.create_table('water_intakes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('amount_ml', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), default=sa.func.now()),
        sa.Column('around_workout', sa.Boolean(), default=False),
        sa.Column('with_supplement', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_water_intakes_user_id'), 'water_intakes', ['user_id'], unique=False)
    op.create_index(op.f('ix_water_intakes_date'), 'water_intakes', ['date'], unique=False)

    # Personal records table
    op.create_table('personal_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('exercise_name', sa.String(), nullable=False),
        sa.Column('muscle_group', sa.String(), nullable=True),
        sa.Column('max_weight', sa.Float(), nullable=False),
        sa.Column('reps', sa.Integer(), default=1),
        sa.Column('date_achieved', sa.Date(), nullable=False),
        sa.Column('estimated_1rm', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'exercise_name', name='unique_user_exercise_pr')
    )
    op.create_index(op.f('ix_personal_records_user_id'), 'personal_records', ['user_id'], unique=False)
    op.create_index(op.f('ix_personal_records_exercise_name'), 'personal_records', ['exercise_name'], unique=False)

    # Achievements table
    op.create_table('achievements',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('achievement_type', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('icon', sa.String(), default='🏆'),
        sa.Column('current_value', sa.Integer(), default=0),
        sa.Column('target_value', sa.Integer(), default=0),
        sa.Column('is_completed', sa.Boolean(), default=False),
        sa.Column('unlocked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_achievements_user_id'), 'achievements', ['user_id'], unique=False)
    op.create_index(op.f('ix_achievements_achievement_type'), 'achievements', ['achievement_type'], unique=False)

    # Deload schedules table
    op.create_table('deload_schedules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('cycle_start_date', sa.Date(), nullable=False),
        sa.Column('cycle_week_number', sa.Integer(), nullable=False),
        sa.Column('is_deload_week', sa.Boolean(), default=False),
        sa.Column('deload_completed', sa.Boolean(), default=False),
        sa.Column('recommended_volume_reduction', sa.Integer(), default=50),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_deload_schedules_user_id'), 'deload_schedules', ['user_id'], unique=False)

    # User settings table
    op.create_table('user_settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('enable_meal_reminders', sa.Boolean(), default=True),
        sa.Column('enable_supplement_reminders', sa.Boolean(), default=True),
        sa.Column('enable_training_reminders', sa.Boolean(), default=True),
        sa.Column('enable_daily_summary', sa.Boolean(), default=True),
        sa.Column('enable_water_reminders', sa.Boolean(), default=True),
        sa.Column('enable_symptom_tracking', sa.Boolean(), default=True),
        sa.Column('daily_summary_time', sa.String(), default='22:00'),
        sa.Column('language', sa.String(), default='ru'),
        sa.Column('timezone', sa.String(), default='Europe/Moscow'),
        sa.Column('measurement_system', sa.String(), default='metric'),
        sa.Column('samsung_health_enabled', sa.Boolean(), default=False),
        sa.Column('samsung_health_sync_interval', sa.Integer(), default=3600),
        sa.Column('deepseek_enabled', sa.Boolean(), default=True),
        sa.Column('gemini_enabled', sa.Boolean(), default=True),
        sa.Column('gamification_enabled', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_user_settings_user_id'), 'user_settings', ['user_id'], unique=True)

    # Reminder logs table
    op.create_table('reminder_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('reminder_type', sa.String(), nullable=False),
        sa.Column('scheduled_time', sa.DateTime(), nullable=False),
        sa.Column('sent_time', sa.DateTime(), nullable=True),
        sa.Column('is_sent', sa.Boolean(), default=False),
        sa.Column('message_text', sa.Text()),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reminder_logs_user_id'), 'reminder_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_reminder_logs_reminder_type'), 'reminder_logs', ['reminder_type'], unique=False)
    op.create_index(op.f('ix_reminder_logs_scheduled_time'), 'reminder_logs', ['scheduled_time'], unique=False)

    # Excel reports table
    op.create_table('excel_reports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('report_type', sa.String(), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('generated_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_excel_reports_user_id'), 'excel_reports', ['user_id'], unique=False)
    op.create_index(op.f('ix_excel_reports_generated_at'), 'excel_reports', ['generated_at'], unique=False)


def downgrade() -> None:
    op.drop_table('excel_reports')
    op.drop_table('reminder_logs')
    op.drop_table('user_settings')
    op.drop_table('deload_schedules')
    op.drop_table('achievements')
    op.drop_table('personal_records')
    op.drop_table('water_intakes')
    op.drop_table('symptom_logs')
    op.drop_table('blood_tests')
    op.drop_table('health_metrics')
    op.drop_table('training_logs')
    op.drop_table('daily_calorie_targets')
    op.drop_table('nutrition_logs')
    op.drop_table('meal_schedules')
    op.drop_table('schedule_items')
    op.drop_table('supplements')
    op.drop_table('users')
