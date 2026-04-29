"""
Food recognition using Gemini Vision API.
Analyzes food photos and estimates nutrition information.
"""

from typing import Dict, List, Any, Optional, Tuple
import logging
import base64
from pathlib import Path

from config import config

logger = logging.getLogger(__name__)


class FoodRecognizer:
    """Food recognition using Gemini Vision API."""
    
    def __init__(self):
        self.api_key = config.gemini_api_key
        self.model = config.gemini_model
        self.is_available = bool(self.api_key)
        
        if self.is_available:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.model_instance = genai.GenerativeModel(self.model)
                logger.info("Gemini Vision API initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini API: {e}")
                self.is_available = False
                self.model_instance = None
        else:
            self.model_instance = None
            logger.warning("Gemini API key not configured. Food recognition disabled.")
    
    async def recognize_food_from_image(
        self,
        image_path: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Recognize food from image and estimate nutrition.
        
        Args:
            image_path: Path to image file
            user_context: Optional user context (dietary restrictions, preferences)
        
        Returns:
            Tuple of (success, result_dict, message)
            result_dict contains:
                - foods: List of recognized food items
                - total_nutrition: Combined nutrition info
                - confidence: Recognition confidence
                - suggestions: AI suggestions
        """
        if not self.is_available:
            return False, {}, "❌ Сервис распознавания еды временно недоступен"
        
        try:
            # Load and validate image
            image_data = self._load_image(image_path)
            if not image_data:
                return False, {}, "❌ Не удалось загрузить изображение"
            
            # Build prompt
            prompt = self._build_prompt(user_context)
            
            # Call Gemini API
            response = await self._call_gemini_api(image_data, prompt)
            
            if not response:
                return False, {}, "❌ Ошибка при анализе изображения"
            
            # Parse response
            parsed_result = self._parse_gemini_response(response)
            
            if not parsed_result:
                return False, {}, "❌ Не удалось распознать еду на изображении"
            
            return True, parsed_result, "✅ Еда распознана"
            
        except Exception as e:
            logger.error(f"Error recognizing food: {e}")
            return False, {}, f"❌ Ошибка распознавания: {e}"
    
    def _load_image(self, image_path: str) -> Optional[bytes]:
        """Load image from file."""
        try:
            path = Path(image_path)
            if not path.exists():
                logger.error(f"Image not found: {image_path}")
                return None
            
            with open(path, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error loading image: {e}")
            return None
    
    def _build_prompt(self, user_context: Optional[Dict[str, Any]] = None) -> str:
        """Build prompt for Gemini API."""
        base_prompt = """
Ты - профессиональный нутрициолог и эксперт по распознаванию еды. 
Проанализируй изображение и определи все видимые продукты питания.

Верни ответ ТОЛЬКО в формате JSON следующей структуры:
{
    "foods": [
        {
            "name": "название продукта на русском",
            "weight_grams": примерный_вес_в_граммах,
            "calories": калории_на_100г,
            "protein": белки_на_100г,
            "fat": жиры_на_100г,
            "carbs": углеводы_на_100г,
            "confidence": уверенность_от_0_до_1
        }
    ],
    "total_estimated_calories": общая_калорийность_блюда,
    "suggestions": ["советы по улучшению блюда"],
    "notes": "дополнительные заметки"
}

Важно:
- Оценивай вес порции визуально
- Используй средние значения калорийности
- Учитывай способ приготовления (жареное, вареное, и т.д.)
- Если видишь несколько продуктов, перечисли все
- Уверенность от 0.0 до 1.0
- ВСЕГДА возвращай только JSON, без дополнительного текста
"""
        
        if user_context:
            if user_context.get('goal') == 'weight_loss':
                base_prompt += "\n\nПользователь хочет похудеть. Предлагай низкокалорийные альтернативы."
            elif user_context.get('goal') == 'muscle_gain':
                base_prompt += "\n\nПользователь набирает массу. Акцентируй внимание на белке."
        
        return base_prompt
    
    async def _call_gemini_api(
        self,
        image_data: bytes,
        prompt: str
    ) -> Optional[str]:
        """Call Gemini Vision API."""
        try:
            import google.generativeai as genai
            from io import BytesIO
            from PIL import Image
            
            # Create image object
            image = Image.open(BytesIO(image_data))
            
            # Generate content
            response = self.model_instance.generate_content([
                prompt,
                image
            ], generation_config={
                'temperature': 0.2,
                'top_p': 0.8,
                'top_k': 40,
                'max_output_tokens': 2048,
            })
            
            return response.text
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None
    
    def _parse_gemini_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse Gemini API response."""
        import json
        
        try:
            # Clean response - extract JSON from markdown code blocks if present
            cleaned = response_text.strip()
            
            # Remove markdown code blocks
            if cleaned.startswith('```'):
                lines = cleaned.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                cleaned = '\n'.join(lines)
            
            # Find JSON in response
            start_idx = cleaned.find('{')
            end_idx = cleaned.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = cleaned[start_idx:end_idx]
            else:
                json_str = cleaned
            
            data = json.loads(json_str)
            
            # Validate structure
            if 'foods' not in data or not isinstance(data['foods'], list):
                logger.error("Invalid response structure: missing 'foods'")
                return None
            
            # Process foods
            processed_foods = []
            total_calories = 0
            
            for food in data['foods']:
                if not all(k in food for k in ['name', 'weight_grams']):
                    continue
                
                weight = food.get('weight_grams', 100)
                
                # Calculate nutrition for actual portion
                portion_data = {
                    'name': food.get('name', 'Неизвестный продукт'),
                    'weight_g': weight,
                    'calories': round((food.get('calories', 0) * weight) / 100, 1),
                    'protein': round((food.get('protein', 0) * weight) / 100, 1),
                    'fat': round((food.get('fat', 0) * weight) / 100, 1),
                    'carbs': round((food.get('carbs', 0) * weight) / 100, 1),
                    'confidence': food.get('confidence', 0.5),
                    'per_100g': {
                        'calories': food.get('calories', 0),
                        'protein': food.get('protein', 0),
                        'fat': food.get('fat', 0),
                        'carbs': food.get('carbs', 0)
                    }
                }
                
                processed_foods.append(portion_data)
                total_calories += portion_data['calories']
            
            return {
                'foods': processed_foods,
                'total_nutrition': {
                    'calories': round(total_calories, 0),
                    'protein': round(sum(f['protein'] for f in processed_foods), 1),
                    'fat': round(sum(f['fat'] for f in processed_foods), 1),
                    'carbs': round(sum(f['carbs'] for f in processed_foods), 1)
                },
                'confidence': sum(f['confidence'] for f in processed_foods) / len(processed_foods) if processed_foods else 0,
                'suggestions': data.get('suggestions', []),
                'notes': data.get('notes', '')
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            logger.debug(f"Response text: {response_text[:500]}...")
            return None
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return None
    
    def recognize_food_from_text(
        self,
        food_description: str,
        portion_size: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Recognize food from text description.
        
        Args:
            food_description: Text description of food
            portion_size: Optional portion size description
        
        Returns:
            Tuple of (success, result_dict, message)
        """
        if not self.is_available:
            return False, {}, "❌ Сервис распознавания временно недоступен"
        
        try:
            import google.generativeai as genai
            
            prompt = f"""
Ты - нутрициолог. Определи КБЖУ для блюда: "{food_description}"
{f"Размер порции: {portion_size}" if portion_size else ""}

Верни ответ ТОЛЬКО в формате JSON:
{{
    "foods": [
        {{
            "name": "название",
            "weight_grams": вес,
            "calories": калории_на_100г,
            "protein": белки_на_100г,
            "fat": жиры_на_100г,
            "carbs": углеводы_на_100г
        }}
    ],
    "total_estimated_calories": общая_калорийность
}}
"""
            
            response = self.model_instance.generate_content(prompt, generation_config={
                'temperature': 0.2,
                'max_output_tokens': 1024,
            })
            
            parsed = self._parse_gemini_response(response.text)
            
            if parsed:
                return True, parsed, "✅ Данные получены"
            else:
                return False, {}, "❌ Не удалось получить данные о питании"
                
        except Exception as e:
            logger.error(f"Error in text recognition: {e}")
            return False, {}, f"❌ Ошибка: {e}"


# Global instance
food_recognizer = FoodRecognizer()
