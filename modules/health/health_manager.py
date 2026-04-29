"""
Health monitoring module for Health Bot.
Handles health metrics, blood test analysis, and Samsung Health integration.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import date, datetime, timedelta
import logging
from pathlib import Path

from database.manager import db_manager
from database.models import HealthMetric, BloodTest, User

logger = logging.getLogger(__name__)


class HealthManager:
    """Manager for health metrics and monitoring."""
    
    def __init__(self):
        self.db = db_manager
    
    # Reference ranges for blood tests (adult male)
    BLOOD_TEST_REFERENCES = {
        "hemoglobin": {"min": 130, "max": 170, "unit": "г/л"},
        "erythrocytes": {"min": 4.0, "max": 5.5, "unit": "10^12/л"},
        "leukocytes": {"min": 4.0, "max": 9.0, "unit": "10^9/л"},
        "platelets": {"min": 180, "max": 320, "unit": "10^9/л"},
        "glucose": {"min": 3.9, "max": 5.5, "unit": "ммоль/л"},
        "cholesterol_total": {"min": 3.0, "max": 5.2, "unit": "ммоль/л"},
        "cholesterol_ldl": {"min": 1.8, "max": 3.0, "unit": "ммоль/л"},
        "cholesterol_hdl": {"min": 1.0, "max": 1.7, "unit": "ммоль/л"},
        "triglycerides": {"min": 0.5, "max": 1.7, "unit": "ммоль/л"},
        "creatinine": {"min": 62, "max": 115, "unit": "мкмоль/л"},
        "alt": {"min": 0, "max": 41, "unit": "Ед/л"},
        "ast": {"min": 0, "max": 37, "unit": "Ед/л"},
        "bilirubin_total": {"min": 3.4, "max": 20.5, "unit": "мкмоль/л"},
        "protein_total": {"min": 64, "max": 83, "unit": "г/л"},
        "uric_acid": {"min": 210, "max": 420, "unit": "мкмоль/л"},
        "crp": {"min": 0, "max": 5, "unit": "мг/л"},
        "ferritin": {"min": 20, "max": 250, "unit": "нг/мл"},
        "vitamin_d": {"min": 30, "max": 100, "unit": "нг/мл"},
        "vitamin_b12": {"min": 200, "max": 900, "unit": "пг/мл"},
        "testosterone": {"min": 11, "max": 33, "unit": "нмоль/л"},
        "tsh": {"min": 0.4, "max": 4.0, "unit": "мЕд/л"},
        "cortisol": {"min": 138, "max": 635, "unit": "нмоль/л"},
        "insulin": {"min": 3, "max": 26, "unit": "мкЕд/мл"},
        "homocysteine": {"min": 5, "max": 15, "unit": "мкмоль/л"}
    }
    
    # Reference ranges for health metrics
    HEALTH_METRIC_REFERENCES = {
        "heart_rate_resting": {"min": 60, "max": 100, "unit": "уд/мин"},
        "blood_pressure_systolic": {"min": 90, "max": 120, "unit": "мм рт.ст."},
        "blood_pressure_diastolic": {"min": 60, "max": 80, "unit": "мм рт.ст."},
        "spo2": {"min": 95, "max": 100, "unit": "%"},
        "body_fat_percent": {"min": 8, "max": 20, "unit": "%"},
        "bmi": {"min": 18.5, "max": 25, "unit": "кг/м²"},
        "sleep_hours": {"min": 7, "max": 9, "unit": "часов"},
        "steps_daily": {"min": 8000, "max": 15000, "unit": "шагов"},
        "stress_level": {"min": 0, "max": 30, "unit": "уровень (низкий)"}
    }
    
    def add_health_metric(
        self,
        user_id: int,
        metric_type: str,
        value: float,
        unit: str = "",
        measurement_date: date = None
    ) -> Tuple[bool, Optional[HealthMetric], str]:
        """
        Add a health metric measurement.
        
        Args:
            user_id: User internal ID
            metric_type: Type of metric (weight, heart_rate, etc.)
            value: Measured value
            unit: Unit of measurement
            measurement_date: Date of measurement
        
        Returns:
            Tuple of (success, health_metric, message)
        """
        try:
            if measurement_date is None:
                measurement_date = date.today()
            
            # Map metric type to database field
            field_mapping = {
                "weight": "weight_kg",
                "body_fat": "body_fat_percent",
                "muscle_mass": "muscle_mass_kg",
                "water_percent": "water_percent",
                "bmi": "bmi",
                "heart_rate": "heart_rate_bpm",
                "blood_pressure_systolic": "blood_pressure_systolic",
                "blood_pressure_diastolic": "blood_pressure_diastolic",
                "spo2": "spo2_percent",
                "stress": "stress_level",
                "sleep_duration": "sleep_duration_minutes",
                "sleep_quality": "sleep_quality",
                "steps": "steps",
                "calories_burned": "calories_burned",
                "active_minutes": "active_minutes"
            }
            
            db_field = field_mapping.get(metric_type)
            if not db_field:
                return False, None, f"❌ Неизвестный тип метрики: {metric_type}"
            
            # Create metric data
            metric_data = {db_field: value, "source": "manual"}
            
            # Add special cases
            if metric_type == "blood_pressure":
                # Expect value to be dict with systolic/diastolic
                if isinstance(value, dict):
                    metric_data["blood_pressure_systolic"] = value.get("systolic")
                    metric_data["blood_pressure_diastolic"] = value.get("diastolic")
                else:
                    return False, None, "❌ Для давления укажите систолическое и диастолическое"
            
            metric = self.db.add_health_metric(
                user_id=user_id,
                date=measurement_date,
                **metric_data
            )
            
            # Check if value is in normal range
            reference = self._get_reference_for_metric(metric_type)
            if reference:
                if value < reference["min"] or value > reference["max"]:
                    return True, metric, f"⚠️ Значение вне нормы ({reference['min']}-{reference['max']} {reference.get('unit', '')})"
            
            return True, metric, "✅ Показатель записан"
            
        except Exception as e:
            logger.error(f"Error adding health metric: {e}")
            return False, None, f"❌ Ошибка при записи: {e}"
    
    def _get_reference_for_metric(self, metric_type: str) -> Optional[Dict]:
        """Get reference range for metric type."""
        reference_mapping = {
            "heart_rate": self.HEALTH_METRIC_REFERENCES.get("heart_rate_resting"),
            "body_fat": self.HEALTH_METRIC_REFERENCES.get("body_fat_percent"),
            "bmi": self.HEALTH_METRIC_REFERENCES.get("bmi"),
            "spo2": self.HEALTH_METRIC_REFERENCES.get("spo2"),
            "stress": self.HEALTH_METRIC_REFERENCES.get("stress_level"),
            "sleep_duration": {"min": 420, "max": 540, "unit": "мин"},  # 7-9 hours
            "steps": self.HEALTH_METRIC_REFERENCES.get("steps_daily")
        }
        return reference_mapping.get(metric_type)
    
    def get_latest_metrics(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get latest health metrics for user."""
        metric = self.db.get_latest_health_metrics(user_id)
        if not metric:
            return None
        
        return {
            "date": metric.date.isoformat(),
            "weight_kg": metric.weight_kg,
            "body_fat_percent": metric.body_fat_percent,
            "muscle_mass_kg": metric.muscle_mass_kg,
            "water_percent": metric.water_percent,
            "bmi": metric.bmi,
            "heart_rate_bpm": metric.heart_rate_bpm,
            "blood_pressure": {
                "systolic": metric.blood_pressure_systolic,
                "diastolic": metric.blood_pressure_diastolic
            } if metric.blood_pressure_systolic else None,
            "spo2_percent": metric.spo2_percent,
            "stress_level": metric.stress_level,
            "sleep": {
                "duration_minutes": metric.sleep_duration_minutes,
                "quality": metric.sleep_quality,
                "deep_minutes": metric.sleep_deep_minutes,
                "light_minutes": metric.sleep_light_minutes,
                "rem_minutes": metric.sleep_rem_minutes
            } if metric.sleep_duration_minutes else None,
            "activity": {
                "steps": metric.steps,
                "calories_burned": metric.calories_burned,
                "active_minutes": metric.active_minutes
            }
        }
    
    def get_metrics_history(
        self,
        user_id: int,
        metric_field: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get history of a specific metric.
        
        Args:
            user_id: User internal ID
            metric_field: Database field name (weight_kg, heart_rate_bpm, etc.)
            days: Number of days to retrieve
        
        Returns:
            List of {date, value} dictionaries
        """
        start_date = date.today() - timedelta(days=days)
        
        with self.db.session_scope() as session:
            metrics = session.query(HealthMetric).filter(
                HealthMetric.user_id == user_id,
                HealthMetric.date >= start_date
            ).order_by(HealthMetric.date.asc()).all()
        
        history = []
        for metric in metrics:
            value = getattr(metric, metric_field, None)
            if value is not None:
                history.append({
                    "date": metric.date.isoformat(),
                    "value": value,
                    "timestamp": metric.timestamp.isoformat() if metric.timestamp else None
                })
        
        return history
    
    def add_blood_test(
        self,
        user_id: int,
        test_date: date,
        results: List[Dict[str, Any]],
        photo_path: Optional[str] = None
    ) -> Tuple[bool, Optional[BloodTest], str]:
        """
        Add blood test results.
        
        Args:
            user_id: User internal ID
            test_date: Date of blood test
            results: List of test results with name, value, unit
            photo_path: Path to photo of test results
        
        Returns:
            Tuple of (success, blood_test, message)
        """
        try:
            # Add reference ranges and flags to results
            processed_results = []
            for result in results:
                processed = result.copy()
                
                # Find matching reference
                ref_key = self._match_test_name(result.get('name', ''))
                if ref_key and ref_key in self.BLOOD_TEST_REFERENCES:
                    ref = self.BLOOD_TEST_REFERENCES[ref_key]
                    processed['reference_min'] = ref['min']
                    processed['reference_max'] = ref['max']
                    processed['reference_unit'] = ref['unit']
                    
                    # Determine flag
                    value = result.get('value')
                    if value is not None:
                        if value < ref['min']:
                            processed['flag'] = 'low'
                        elif value > ref['max']:
                            processed['flag'] = 'high'
                        else:
                            processed['flag'] = 'normal'
                
                processed_results.append(processed)
            
            # Create blood test record
            blood_test = self.db.add_blood_test(
                user_id=user_id,
                date=test_date,
                photo_path=photo_path,
                results=processed_results
            )
            
            return True, blood_test, "✅ Анализы загружены"
            
        except Exception as e:
            logger.error(f"Error adding blood test: {e}")
            return False, None, f"❌ Ошибка при загрузке анализов: {e}"
    
    def _match_test_name(self, test_name: str) -> Optional[str]:
        """Match test name to reference key."""
        test_name_lower = test_name.lower()
        
        name_mappings = {
            "hemoglobin": ["гемоглобин", "hb", "hgb"],
            "erythrocytes": ["эритроциты", "rbc"],
            "leukocytes": ["лейкоциты", "wbc"],
            "platelets": ["тромбоциты", "plt"],
            "glucose": ["глюкоза", "сахар", "glucose"],
            "cholesterol_total": ["холестерин общий", "cholesterol total"],
            "cholesterol_ldl": ["лдлп", "ldl", "липопротеины низкой"],
            "cholesterol_hdl": ["лдвп", "hdl", "липопротеины высокой"],
            "triglycerides": ["триглицериды", "tg"],
            "creatinine": ["креатинин", "creatinine"],
            "alt": ["алт", "alt", "аланинаминотрансфераза"],
            "ast": ["аст", "ast", "аспартатаминотрансфераза"],
            "bilirubin_total": ["билирубин общий", "total bilirubin"],
            "protein_total": ["белок общий", "total protein"],
            "uric_acid": ["мочевая кислота", "uric acid"],
            "crp": ["срб", "crp", "c-реактивный белок"],
            "ferritin": ["ферритин", "ferritin"],
            "vitamin_d": ["витамин d", "25-oh-d", "кальциферол"],
            "vitamin_b12": ["витамин b12", "цианокобаламин"],
            "testosterone": ["тестостерон", "testosterone"],
            "tsh": ["ттг", "tsh", "тиреотропный"],
            "cortisol": ["кортизол", "cortisol"],
            "insulin": ["инсулин", "insulin"],
            "homocysteine": ["гомоцистеин", "homocysteine"]
        }
        
        for key, variations in name_mappings.items():
            for variation in variations:
                if variation in test_name_lower:
                    return key
        
        return None
    
    def analyze_blood_test(self, blood_test_id: int) -> Tuple[bool, str, List[str]]:
        """
        Analyze blood test results and generate recommendations.
        
        Args:
            blood_test_id: Blood test internal ID
        
        Returns:
            Tuple of (success, analysis_text, recommendations_list)
        """
        with self.db.session_scope() as session:
            blood_test = session.query(BloodTest).filter(
                BloodTest.id == blood_test_id
            ).first()
        
        if not blood_test:
            return False, "", ["❌ Анализ не найден"]
        
        results = blood_test.results or []
        if not results:
            return False, "", ["❌ Нет результатов для анализа"]
        
        # Analyze results
        abnormal_results = [r for r in results if r.get('flag') in ['low', 'high']]
        normal_results = [r for r in results if r.get('flag') == 'normal']
        
        # Generate analysis
        analysis_parts = []
        recommendations = []
        
        if abnormal_results:
            analysis_parts.append(f"Выявлено {len(abnormal_results)} отклонений от нормы:\n")
            
            for result in abnormal_results:
                name = result.get('name', 'Неизвестный показатель')
                value = result.get('value')
                unit = result.get('unit', '')
                flag = result.get('flag', '')
                ref_min = result.get('reference_min')
                ref_min_str = f"{ref_min}" if ref_min is not None else "?"
                ref_max = result.get('reference_max')
                ref_max_str = f"{ref_max}" if ref_max is not None else "?"
                
                status = "понижен" if flag == 'low' else "повышен"
                analysis_parts.append(
                    f"• {name}: {value} {unit} ({status}, норма: {ref_min_str}-{ref_max_str})"
                )
                
                # Generate specific recommendations
                recs = self._get_recommendations_for_indicator(
                    result.get('name', ''),
                    flag,
                    value
                )
                recommendations.extend(recs)
        else:
            analysis_parts.append("✅ Все показатели в пределах нормы!\n")
            recommendations.append("Продолжайте вести здоровый образ жизни")
        
        if normal_results:
            analysis_parts.append(f"\n{len(normal_results)} показателей в норме.")
        
        analysis_text = "\n".join(analysis_parts)
        
        # Add general recommendation
        recommendations.append("🩺 Для консультации по результатам обратитесь к врачу")
        
        # Update blood test record
        blood_test.analysis = analysis_text
        blood_test.recommendations = recommendations
        blood_test.is_ai_analyzed = True
        
        with self.db.session_scope() as session:
            session.add(blood_test)
        
        return True, analysis_text, recommendations
    
    def _get_recommendations_for_indicator(
        self,
        indicator_name: str,
        flag: str,
        value: Any
    ) -> List[str]:
        """Get recommendations for specific abnormal indicator."""
        recommendations = []
        name_lower = indicator_name.lower()
        
        # Hemoglobin
        if any(x in name_lower for x in ["гемоглобин", "hemoglobin"]):
            if flag == 'low':
                recommendations.extend([
                    "💡 Увеличьте потребление железа: красное мясо, печень, гречка",
                    "💡 Добавьте витамин C для лучшего усвоения железа",
                    "💡 Рассмотрите прием добавок железа после консультации с врачом"
                ])
            else:
                recommendations.append("💡 Пейте больше воды, обсудите с врачом")
        
        # Glucose
        if any(x in name_lower for x in ["глюкоза", "сахар", "glucose"]):
            if flag == 'high':
                recommendations.extend([
                    "💡 Снизьте потребление простых углеводов",
                    "💡 Увеличьте физическую активность",
                    "💡 Проконсультируйтесь с эндокринологом"
                ])
            else:
                recommendations.append("💡 Добавьте сложные углеводы в рацион")
        
        # Cholesterol
        if any(x in name_lower for x in ["холестерин", "cholesterol"]):
            if flag == 'high':
                recommendations.extend([
                    "💡 Снизьте потребление насыщенных жиров",
                    "💡 Добавьте омега-3 (рыба, льняное масло)",
                    "💡 Увеличьте потребление клетчатки"
                ])
        
        # Vitamin D
        if any(x in name_lower for x in ["витамин d", "vitamin d"]):
            if flag == 'low':
                recommendations.extend([
                    "💡 Добавьте витамин D3 в дозировке 2000-5000 МЕ",
                    "💡 Чаще бывайте на солнце",
                    "💡 Употребляйте жирную рыбу, яичные желтки"
                ])
        
        # Testosterone
        if "тестостерон" in name_lower or "testosterone" in name_lower:
            if flag == 'low':
                recommendations.extend([
                    "💡 Оптимизируйте сон (7-9 часов)",
                    "💡 Добавьте силовые тренировки",
                    "💡 Убедитесь в достаточном потреблении цинка и витамина D",
                    "💡 Снизьте уровень стресса"
                ])
        
        # Cortisol
        if "кортизол" in name_lower or "cortisol" in name_lower:
            if flag == 'high':
                recommendations.extend([
                    "💡 Практикуйте техники релаксации (медитация, дыхание)",
                    "💡 Нормализуйте режим сна",
                    "💡 Снизьте потребление кофеина",
                    "💡 Рассмотрите прием магния и адаптогенов"
                ])
        
        return recommendations
    
    def get_blood_test_history(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all blood tests for user with analysis."""
        tests = self.db.get_blood_tests(user_id)
        
        history = []
        for test in tests:
            history.append({
                "id": test.id,
                "date": test.date.isoformat(),
                "results_count": len(test.results or []),
                "abnormal_count": len([
                    r for r in (test.results or []) 
                    if r.get('flag') in ['low', 'high']
                ]),
                "analysis": test.analysis,
                "recommendations": test.recommendations or [],
                "is_analyzed": test.is_ai_analyzed
            })
        
        return history
    
    def get_body_composition_trend(
        self,
        user_id: int,
        days: int = 90
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get body composition trends over time.
        
        Returns:
            Dictionary with trends for weight, body_fat, muscle_mass
        """
        return {
            "weight": self.get_metrics_history(user_id, "weight_kg", days),
            "body_fat": self.get_metrics_history(user_id, "body_fat_percent", days),
            "muscle_mass": self.get_metrics_history(user_id, "muscle_mass_kg", days),
            "bmi": self.get_metrics_history(user_id, "bmi", days)
        }
    
    def calculate_bmi(self, weight_kg: float, height_cm: float) -> Optional[Dict[str, Any]]:
        """Calculate BMI and return category."""
        if not weight_kg or not height_cm or height_cm <= 0:
            return None
        
        height_m = height_cm / 100
        bmi = weight_kg / (height_m ** 2)
        
        if bmi < 18.5:
            category = "Недостаточный вес"
        elif bmi < 25:
            category = "Нормальный вес"
        elif bmi < 30:
            category = "Избыточный вес"
        else:
            category = "Ожирение"
        
        return {
            "bmi": round(bmi, 2),
            "category": category,
            "healthy_range": "18.5 - 25.0"
        }


# Global instance
health_manager = HealthManager()
