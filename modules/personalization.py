"""
Personalization module for Health Bot.
Handles symptom tracking, hydration, blood test analysis with red flags.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import date, datetime
import logging

from database.manager import db_manager
from database.models import SymptomLog, WaterIntake, BloodTest, User

logger = logging.getLogger(__name__)


# ==================== BLOOD TEST RED FLAGS ====================

# Critical values that require immediate medical attention
BLOOD_TEST_RED_FLAGS = {
    # Hematology
    "hemoglobin": {"min": 100, "critical_min": 80, "max": 200, "unit": "г/л"},
    "hematocrit": {"min": 35, "max": 55, "unit": "%"},
    "rbc": {"min": 3.5, "max": 6.0, "unit": "10^12/L"},  # Red blood cells
    "wbc": {"min": 3.5, "max": 11.0, "unit": "10^9/L"},  # White blood cells
    "platelets": {"min": 100, "max": 450, "unit": "10^9/L"},
    
    # Biochemistry
    "glucose": {"min": 3.3, "critical_max": 11.0, "max": 7.0, "unit": "ммоль/л"},
    "cholesterol_total": {"min": 3.0, "max": 6.2, "unit": "ммоль/л"},
    "ldl": {"min": 1.0, "max": 4.1, "unit": "ммоль/л"},  # Bad cholesterol
    "hdl": {"min": 1.0, "max": 2.5, "unit": "ммоль/л"},  # Good cholesterol
    "triglycerides": {"min": 0.4, "max": 2.3, "unit": "ммоль/л"},
    
    # Liver function
    "alt": {"min": 7, "max": 56, "unit": "Ед/л"},  # Alanine aminotransferase
    "ast": {"min": 10, "max": 40, "unit": "Ед/л"},  # Aspartate aminotransferase
    "bilirubin_total": {"min": 3.4, "max": 20.5, "unit": "мкмоль/л"},
    
    # Kidney function
    "creatinine": {"min": 60, "max": 115, "unit": "мкмоль/л"},
    "urea": {"min": 2.5, "max": 8.3, "unit": "ммоль/л"},
    "uric_acid": {"min": 200, "max": 420, "unit": "мкмоль/л"},
    
    # Electrolytes
    "potassium": {"min": 3.5, "critical_min": 3.0, "max": 5.5, "unit": "ммоль/л"},
    "sodium": {"min": 135, "max": 145, "unit": "ммоль/л"},
    "calcium": {"min": 2.1, "max": 2.6, "unit": "ммоль/л"},
    
    # Iron status
    "iron": {"min": 9, "max": 32, "unit": "мкмоль/л"},
    "ferritin": {"min": 20, "max": 400, "unit": "нг/мл"},
    
    # Thyroid
    "tsh": {"min": 0.4, "max": 4.0, "unit": "мЕд/л"},  # Thyroid stimulating hormone
    "t4_free": {"min": 9, "max": 22, "unit": "пмоль/л"},  # Free thyroxine
    
    # Vitamins
    "vitamin_d": {"min": 30, "max": 100, "unit": "нг/мл"},
    "vitamin_b12": {"min": 180, "max": 900, "unit": "пг/мл"},
    
    # Inflammation
    "crp": {"min": 0, "max": 5, "unit": "мг/л"},  # C-reactive protein
    "esr": {"min": 1, "max": 20, "unit": "мм/ч"},  # Erythrocyte sedimentation rate
}


class PersonalizationManager:
    """Manager for personalization features."""

    def __init__(self):
        self.db = db_manager

    # ==================== SYMPTOM TRACKING ====================

    def log_symptoms(
        self,
        user_id: int,
        pain_level: int = 0,
        fatigue_level: int = 0,
        mood_level: int = 5,
        energy_level: int = 5,
        stress_level: int = 5,
        muscle_soreness: int = 0,
        joint_pain: int = 0,
        pain_locations: List[str] = None,
        symptoms: List[str] = None,
        notes: str = ""
    ) -> Tuple[bool, SymptomLog, str]:
        """
        Log daily symptoms.

        Returns:
            Tuple of (success, symptom_log, message)
        """
        try:
            symptom_log = self.db.add_symptom_log(
                user_id=user_id,
                date=date.today(),
                pain_level=pain_level,
                fatigue_level=fatigue_level,
                mood_level=mood_level,
                energy_level=energy_level,
                stress_level=stress_level,
                muscle_soreness=muscle_soreness,
                joint_pain=joint_pain,
                pain_locations=pain_locations or [],
                symptoms=symptoms or [],
                symptom_severity={s: 5 for s in (symptoms or [])},  # Default severity
                notes=notes
            )
            return True, symptom_log, "✅ Симптомы записаны"
        except Exception as e:
            logger.error(f"Error logging symptoms: {e}")
            return False, None, f"❌ Ошибка: {e}"

    def get_symptom_trend(self, user_id: int, days: int = 7) -> Dict[str, float]:
        """
        Get symptom trends over last N days.

        Returns:
            Dictionary with average values for each symptom
        """
        end_date = date.today()
        start_date = date.today() - timedelta(days=days)

        logs = self.db.get_symptom_logs(user_id, start_date, end_date)

        if not logs:
            return {}

        # Calculate averages
        total = len(logs)
        return {
            "avg_pain": sum(l.pain_level for l in logs) / total,
            "avg_fatigue": sum(l.fatigue_level for l in logs) / total,
            "avg_mood": sum(l.mood_level for l in logs) / total,
            "avg_energy": sum(l.energy_level for l in logs) / total,
            "avg_stress": sum(l.stress_level for l in logs) / total,
            "avg_muscle_soreness": sum(l.muscle_soreness for l in logs) / total,
            "days_logged": total
        }

    def get_recovery_score(self, user_id: int) -> int:
        """
        Calculate recovery score (0-100) based on symptoms and sleep.

        Returns:
            Recovery score (higher is better)
        """
        latest = self.db.get_latest_symptom_log(user_id)
        if not latest:
            return 50  # Default

        # Get latest health metrics for sleep
        metrics = self.db.get_latest_health_metrics(user_id)

        score = 100

        # Deduct for negative symptoms
        score -= latest.pain_level * 3  # Max -30
        score -= latest.fatigue_level * 2  # Max -20
        score -= latest.muscle_soreness * 2  # Max -20
        score -= latest.joint_pain * 2  # Max -20

        # Add for good mood and energy
        score += (latest.mood_level - 5)  # -10 to +10
        score += (latest.energy_level - 5)  # -10 to +10

        # Sleep factor
        if metrics and metrics.sleep_duration_minutes:
            sleep_hours = metrics.sleep_duration_minutes / 60
            if 7 <= sleep_hours <= 9:
                score += 10
            elif sleep_hours < 6 or sleep_hours > 10:
                score -= 10

        return max(0, min(100, score))

    # ==================== HYDRATION TRACKING ====================

    def log_water_intake(
        self,
        user_id: int,
        amount_ml: int = 250,
        around_workout: bool = False,
        with_supplement: str = None
    ) -> Tuple[bool, WaterIntake, str]:
        """
        Log water intake.

        Args:
            user_id: User internal ID
            amount_ml: Amount in ml (default 250ml = 1 glass)
            around_workout: Was this around a workout?
            with_supplement: Which supplement was taken with this water

        Returns:
            Tuple of (success, water_intake, message)
        """
        try:
            intake = self.db.add_water_intake(
                user_id=user_id,
                date=date.today(),
                amount_ml=amount_ml,
                around_workout=around_workout,
                with_supplement=with_supplement
            )
            return True, intake, f"✅ Записано {amount_ml}мл воды"
        except Exception as e:
            logger.error(f"Error logging water intake: {e}")
            return False, None, f"❌ Ошибка: {e}"

    def get_daily_hydration_status(self, user_id: int, target_ml: int = 2500) -> Dict[str, Any]:
        """
        Get daily hydration status.

        Args:
            user_id: User internal ID
            target_ml: Daily target (default 2500ml for active males)

        Returns:
            Dictionary with hydration data
        """
        total = self.db.get_daily_water_intake(user_id, date.today())

        return {
            "total_ml": total,
            "target_ml": target_ml,
            "percent": round((total / target_ml) * 100, 1) if target_ml > 0 else 0,
            "remaining_ml": max(0, target_ml - total),
            "glasses": total // 250,  # Approximate glasses
            "status": "on_track" if total >= target_ml * 0.8 else "behind"
        }

    def calculate_water_target(self, user: User) -> int:
        """
        Calculate personalized water target.

        Based on:
        - Weight (35ml per kg)
        - Activity level (+500ml for active)
        - Creatine supplementation (+500ml)

        Returns:
            Target in ml
        """
        weight = user.weight_kg
        base_target = weight * 35  # 35ml per kg

        # Activity adjustment
        activity_bonus = {
            "sedentary": 0,
            "light": 250,
            "moderate": 500,
            "active": 750,
            "very_active": 1000
        }
        base_target += activity_bonus.get(user.activity_level, 500)

        # Check for creatine
        supplements = self.db.get_user_supplements(user.id)
        for supp in supplements:
            if "креатин" in supp.name.lower() or "creatine" in supp.name.lower():
                if supp.is_active:
                    base_target += 500
                    break

        return int(base_target)

    # ==================== BLOOD TEST RED FLAGS ====================

    def analyze_blood_test(self, user_id: int, blood_test_id: int) -> Tuple[bool, Dict[str, Any]]:
        """
        Analyze blood test results for red flags.

        Args:
            user_id: User internal ID
            blood_test_id: Blood test internal ID

        Returns:
            Tuple of (success, analysis_result)
        """
        with self.db.session_scope() as session:
            blood_test = session.query(BloodTest).filter(
                BloodTest.id == blood_test_id,
                BloodTest.user_id == user_id
            ).first()

            if not blood_test:
                return False, {"error": "Blood test not found"}

            results = blood_test.results or []
            red_flags = []
            warnings = []
            recommendations = []

            for result in results:
                marker_name = result.get("name", "").lower().replace(" ", "_")
                value = result.get("value")

                if value is None:
                    continue

                # Find matching reference
                for ref_name, ref_range in BLOOD_TEST_RED_FLAGS.items():
                    if ref_name in marker_name or marker_name in ref_name:
                        # Check for critical values
                        if "critical_min" in ref_range and value < ref_range["critical_min"]:
                            red_flags.append({
                                "marker": result.get("name", marker_name),
                                "value": value,
                                "unit": result.get("unit", ""),
                                "issue": "critically_low",
                                "message": f"⚠️ {result.get('name')}: {value} {result.get('unit')} - КРИТИЧЕСКИ НИЗКО!"
                            })
                            recommendations.append(f"СРОЧНО обратитесь к врачу по поводу {result.get('name')}")

                        elif "critical_max" in ref_range and value > ref_range["critical_max"]:
                            red_flags.append({
                                "marker": result.get("name", marker_name),
                                "value": value,
                                "unit": result.get("unit", ""),
                                "issue": "critically_high",
                                "message": f"⚠️ {result.get('name')}: {value} {result.get('unit')} - КРИТИЧЕСКИ ВЫСОКО!"
                            })
                            recommendations.append(f"СРОЧНО обратитесь к врачу по поводу {result.get('name')}")

                        # Check for normal out-of-range
                        elif value < ref_range.get("min", 0):
                            warnings.append({
                                "marker": result.get("name", marker_name),
                                "value": value,
                                "unit": result.get("unit", ""),
                                "issue": "low",
                                "message": f"📉 {result.get('name')}: {value} {result.get('unit')} - Ниже нормы"
                            })

                        elif value > ref_range.get("max", 1000):
                            warnings.append({
                                "marker": result.get("name", marker_name),
                                "value": value,
                                "unit": result.get("unit", ""),
                                "issue": "high",
                                "message": f"📈 {result.get('name')}: {value} {result.get('unit')} - Выше нормы"
                            })

                        break

            # Update blood test record
            blood_test.has_red_flags = len(red_flags) > 0
            blood_test.red_flag_details = red_flags
            blood_test.requires_doctor_consultation = len(red_flags) > 0

            # Generate summary
            summary = self._generate_blood_test_summary(red_flags, warnings, recommendations)
            blood_test.analysis = summary

            return True, {
                "has_red_flags": len(red_flags) > 0,
                "red_flags_count": len(red_flags),
                "warnings_count": len(warnings),
                "red_flags": red_flags,
                "warnings": warnings,
                "recommendations": recommendations,
                "summary": summary,
                "requires_doctor": len(red_flags) > 0
            }

    def _generate_blood_test_summary(
        self,
        red_flags: List[Dict],
        warnings: List[Dict],
        recommendations: List[str]
    ) -> str:
        """Generate human-readable summary."""
        summary = "📊 **Анализ показателей крови**\n\n"

        if red_flags:
            summary += "🚨 **КРИТИЧЕСКИЕ ОТКЛОНЕНИЯ**\n"
            for flag in red_flags:
                summary += f"• {flag['message']}\n"
            summary += "\n"

        if warnings:
            summary += "⚠️ **ОТКЛОНЕНИЯ ОТ НОРМЫ**\n"
            for warn in warnings:
                summary += f"• {warn['message']}\n"
            summary += "\n"

        if recommendations:
            summary += "💡 **РЕКОМЕНДАЦИИ**\n"
            for rec in recommendations[:5]:  # Top 5
                summary += f"• {rec}\n"

        if not red_flags and not warnings:
            summary += "✅ Все показатели в пределах нормы!\n"

        summary += "\n⚠️ _Этот анализ носит информационный характер. Проконсультируйтесь с врачом._"

        return summary

    def get_blood_test_history(self, user_id: int, marker_name: str = None) -> List[Dict]:
        """
        Get blood test history for specific marker or all markers.

        Returns:
            List of historical values with dates
        """
        blood_tests = self.db.get_blood_tests(user_id)
        history = []

        for test in blood_tests:
            for result in (test.results or []):
                if marker_name is None or marker_name.lower() in result.get("name", "").lower():
                    history.append({
                        "date": test.date.isoformat(),
                        "marker": result.get("name"),
                        "value": result.get("value"),
                        "unit": result.get("unit"),
                        "flag": result.get("flag")
                    })

        return sorted(history, key=lambda x: x["date"], reverse=True)


# Import timedelta for symptom trend
from datetime import timedelta

# Global instance
personalization_manager = PersonalizationManager()
