"""
DeepSeek AI integration module for Health Bot.
Provides recommendations, analysis, and insights via DeepSeek API.
"""

from typing import Dict, List, Any, Optional, Tuple
import logging
import json
import aiohttp

from config import config

logger = logging.getLogger(__name__)


class DeepSeekClient:
    """Client for DeepSeek API integration."""
    
    def __init__(self):
        self.api_key = config.deepseek_api_key
        self.base_url = config.deepseek_base_url
        self.chat_model = config.deepseek_chat_model
        self.reasoner_model = config.deepseek_reasoner_model
        self.coder_model = config.deepseek_coder_model
        
        self.is_available = bool(self.api_key)
        
        if self.is_available:
            logger.info("DeepSeek API client initialized")
        else:
            logger.warning("DeepSeek API key not configured")
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> Optional[str]:
        """
        Send chat message to DeepSeek API.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (default: chat model)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
        
        Returns:
            AI response text or None
        """
        if not self.is_available:
            logger.warning("DeepSeek API not available")
            return None
        
        model = model or self.chat_model
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
                
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('choices', [{}])[0].get('message', {}).get('content')
                    else:
                        error_text = await response.text()
                        logger.error(f"DeepSeek API error: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error calling DeepSeek API: {e}")
            return None
    
    async def analyze_nutrition(
        self,
        daily_summary: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze daily nutrition and provide recommendations.
        
        Args:
            daily_summary: Daily nutrition summary
            user_context: User context (goals, conditions, etc.)
        
        Returns:
            Analysis results with recommendations
        """
        prompt = self._build_nutrition_analysis_prompt(daily_summary, user_context)
        
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты - профессиональный нутрициолог и фитнес-тренер. "
                    "Анализируешь питание и даешь персонализированные рекомендации. "
                    "Отвечай на русском языке, конкретно и по делу."
                )
            },
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat(messages, temperature=0.5)
        
        if response:
            return self._parse_nutrition_analysis(response)
        
        return {
            "analysis": "Не удалось получить анализ",
            "recommendations": [],
            "score": 0
        }
    
    def _build_nutrition_analysis_prompt(
        self,
        daily_summary: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> str:
        """Build prompt for nutrition analysis."""
        prompt = f"""Проанализируй питание пользователя за день:

Данные пользователя:
- Возраст: {user_context.get('age', 'Н/Д')}
- Вес: {user_context.get('weight_kg', 'Н/Д')} кг
- Рост: {user_context.get('height_cm', 'Н/Д')} см
- Цель: {user_context.get('goal', 'Н/Д')}
- Особенности здоровья: {', '.join(user_context.get('health_conditions', [])) or 'нет'}

Питание за день:
- Калории: {daily_summary.get('calories', 0):.0f} ккал
- Белки: {daily_summary.get('protein', 0):.1f} г
- Жиры: {daily_summary.get('fat', 0):.1f} г
- Углеводы: {daily_summary.get('carbs', 0):.1f} г
- Прием пищи: {daily_summary.get('meals_count', 0)}

Целевые показатели:
"""
        
        if daily_summary.get('targets'):
            targets = daily_summary['targets']
            prompt += f"""- Калории: {targets.get('calories', 0):.0f} ккал
- Белки: {targets.get('protein', 0):.1f} г
- Жиры: {targets.get('fat', 0):.1f} г
- Углеводы: {targets.get('carbs', 0):.1f} г
"""
        
        prompt += """
Дай краткий анализ и 3-5 конкретных рекомендаций.
Верни ответ в формате JSON:
{
    "analysis": "краткий анализ питания",
    "recommendations": ["рекомендация 1", "рекомендация 2", ...],
    "score": оценка_от_1_до_10
}
"""
        return prompt
    
    def _parse_nutrition_analysis(self, response: str) -> Dict[str, Any]:
        """Parse nutrition analysis response."""
        try:
            # Try to extract JSON from response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
        except:
            pass
        
        # Fallback
        return {
            "analysis": response[:500] if response else "Анализ не удался",
            "recommendations": [],
            "score": 5
        }
    
    async def analyze_training(
        self,
        training_summary: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze training data and provide recommendations.
        
        Args:
            training_summary: Training summary data
            user_context: User context
        
        Returns:
            Analysis results with recommendations
        """
        prompt = self._build_training_analysis_prompt(training_summary, user_context)
        
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты - опытный фитнес-тренер и специалист по спортивной физиологии. "
                    "Анализируешь тренировки и даешь рекомендации по улучшению. "
                    "Отвечай на русском языке."
                )
            },
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat(messages, temperature=0.5)
        
        if response:
            return self._parse_training_analysis(response)
        
        return {
            "analysis": "Не удалось получить анализ",
            "recommendations": [],
            "weekly_plan": []
        }
    
    def _build_training_analysis_prompt(
        self,
        training_summary: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> str:
        """Build prompt for training analysis."""
        prompt = f"""Проанализируй тренировки пользователя:

Данные пользователя:
- Возраст: {user_context.get('age', 'Н/Д')}
- Цель: {user_context.get('goal', 'Н/Д')}
- Особенности здоровья: {', '.join(user_context.get('health_conditions', [])) or 'нет'}

Тренировки за неделю:
- Всего тренировок: {training_summary.get('total_workouts', 0)}
- Общая длительность: {training_summary.get('total_duration_minutes', 0)} мин
- Сожжено калорий: {training_summary.get('total_calories_burned', 0):.0f} ккал

Проработанные группы мышц:
"""
        
        for muscle, count in training_summary.get('muscle_groups_trained', {}).items():
            prompt += f"- {muscle}: {count} раз(а)\n"
        
        prompt += """
Дай анализ и рекомендации по улучшению тренировочного процесса.
Верни ответ в формате JSON:
{
    "analysis": "анализ текущей программы",
    "recommendations": ["рекомендация 1", "рекомендация 2", ...],
    "weekly_plan": ["план на понедельник", "план на среду", ...]
}
"""
        return prompt
    
    def _parse_training_analysis(self, response: str) -> Dict[str, Any]:
        """Parse training analysis response."""
        try:
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
        except:
            pass
        
        return {
            "analysis": response[:500] if response else "Анализ не удался",
            "recommendations": [],
            "weekly_plan": []
        }
    
    async def analyze_blood_test(
        self,
        blood_test_results: List[Dict[str, Any]],
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze blood test results and provide recommendations.
        
        Args:
            blood_test_results: List of blood test results
            user_context: User context including supplements
        
        Returns:
            Analysis with recommendations for supplements and diet
        """
        prompt = self._build_blood_test_prompt(blood_test_results, user_context)
        
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты - врач-диагност с опытом работы 15 лет. "
                    "Анализируешь анализы крови и даешь рекомендации. "
                    "ВАЖНО: Все рекомендации носят информационный характер. "
                    "Всегда указывай на необходимость консультации с врачом. "
                    "Отвечай на русском языке."
                )
            },
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat(messages, temperature=0.3)
        
        if response:
            return self._parse_blood_test_analysis(response)
        
        return {
            "analysis": "Не удалось получить анализ",
            "recommendations": [],
            "supplement_adjustments": [],
            "doctor_consultation_needed": False
        }
    
    def _build_blood_test_prompt(
        self,
        blood_test_results: List[Dict[str, Any]],
        user_context: Dict[str, Any]
    ) -> str:
        """Build prompt for blood test analysis."""
        prompt = """Проанализируй результаты анализов крови:

Результаты:
"""
        
        for result in blood_test_results:
            name = result.get('name', 'Неизвестный')
            value = result.get('value', '')
            unit = result.get('unit', '')
            flag = result.get('flag', 'normal')
            ref_min = result.get('reference_min', '?')
            ref_max = result.get('reference_max', '?')
            
            status = "⬆️" if flag == 'high' else "⬇️" if flag == 'low' else "✅"
            prompt += f"{status} {name}: {value} {unit} (норма: {ref_min}-{ref_max})\n"
        
        prompt += f"""
Текущие добавки пользователя:
{', '.join(user_context.get('supplements', [])) or 'не принимает'}

Особенности здоровья:
{', '.join(user_context.get('health_conditions', [])) or 'нет'}

Дай анализ отклонений и рекомендации:
1. Какие показатели требуют внимания
2. Какие добавки стоит скорректировать
3. Рекомендации по питанию
4. Нужно ли обратиться к врачу

Верни ответ в формате JSON:
{
    "analysis": "общий анализ",
    "recommendations": ["рекомендация 1", ...],
    "supplement_adjustments": [
        {"supplement": "название", "action": "increase/decrease/keep", "reason": "причина"}
    ],
    "doctor_consultation_needed": true/false
}
"""
        return prompt
    
    def _parse_blood_test_analysis(self, response: str) -> Dict[str, Any]:
        """Parse blood test analysis response."""
        try:
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
        except:
            pass
        
        return {
            "analysis": response[:500] if response else "Анализ не удался",
            "recommendations": [],
            "supplement_adjustments": [],
            "doctor_consultation_needed": True
        }
    
    async def generate_health_insights(
        self,
        weekly_data: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> List[str]:
        """
        Generate health insights based on weekly data.
        
        Args:
            weekly_data: Aggregated weekly data
            user_context: User context
        
        Returns:
            List of insight strings
        """
        prompt = f"""На основе данных за неделю сгенерируй 3-5 кратких инсайтов:

Питание (среднее за день):
- Калории: {weekly_data.get('avg_calories', 0):.0f} ккал
- Белки: {weekly_data.get('avg_protein', 0):.1f} г

Тренировки:
- Количество: {weekly_data.get('total_workouts', 0)}
- Длительность: {weekly_data.get('total_training_minutes', 0)} мин

Сон (средний):
- Длительность: {weekly_data.get('avg_sleep_hours', 0):.1f} ч

Вес: {weekly_data.get('current_weight', 'Н/Д')} кг

Дай 3-5 конкретных инсайта о взаимосвязях и прогрессе."""
        
        messages = [
            {"role": "system", "content": "Ты - AI-ассистент по здоровью. Отвечай кратко, по делу, на русском."},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat(messages, temperature=0.7)
        
        if response:
            # Parse bullet points
            insights = []
            for line in response.split('\n'):
                line = line.strip()
                if line and any(line.startswith(p) for p in ['•', '-', '•', '1', '2', '3', '4', '5']):
                    insights.append(line.lstrip('•-12345. '))
            return insights[:5]
        
        return []
    
    async def answer_health_question(
        self,
        question: str,
        user_context: Dict[str, Any]
    ) -> str:
        """
        Answer a health-related question.
        
        Args:
            question: User's question
            user_context: User context for personalization
        
        Returns:
            AI answer
        """
        prompt = f"""Вопрос пользователя: {question}

Контекст пользователя:
- Возраст: {user_context.get('age', 'Н/Д')}
- Вес: {user_context.get('weight_kg', 'Н/Д')} кг
- Цель: {user_context.get('goal', 'Н/Д')}
- Особенности здоровья: {', '.join(user_context.get('health_conditions', [])) or 'нет'}
- Добавки: {', '.join(user_context.get('supplements', [])) or 'нет'}

Дай персонализированный ответ с учетом контекста."""
        
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты - knowledgeable AI-ассистент по здоровью и фитнесу. "
                    "Отвечай на русском языке, дружелюбно и профессионально. "
                    "Всегда указывай, что для медицинских вопросов нужна консультация врача."
                )
            },
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat(messages, temperature=0.7)
        return response or "Извините, не удалось получить ответ. Попробуйте позже."


# Global instance
deepseek_client = DeepSeekClient()
