"""
Image processing module for Health Bot.
Handles image uploads, Gemini Vision analysis, and FoodScanner integration.
Includes caching, retries, and error handling.
"""

from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from datetime import date, datetime, timedelta
import logging
import base64
import aiohttp
import asyncio
import json as json_lib
from functools import wraps
import hashlib

from config import config

logger = logging.getLogger(__name__)


# ==================== CACHE DECORATOR ====================

def async_cache(ttl_seconds: int = 3600):
    """Async caching decorator with TTL."""
    cache_data = {}
    cache_times = {}

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from arguments
            key_parts = [str(arg) for arg in args]
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = hashlib.md5('|'.join(key_parts).encode()).hexdigest()

            # Check cache
            now = datetime.now()
            if cache_key in cache_data:
                if now < cache_times[cache_key]:
                    logger.debug(f"Cache hit for {func.__name__}")
                    return cache_data[cache_key]
                else:
                    # Expired
                    del cache_data[cache_key]
                    del cache_times[cache_key]

            # Call function
            result = await func(*args, **kwargs)

            # Store in cache
            cache_data[cache_key] = result
            cache_times[cache_key] = now + timedelta(seconds=ttl_seconds)

            return result
        return wrapper
    return decorator


# ==================== RETRY DECORATOR ====================

def retry_on_exception(max_attempts: int = 3, delay: float = 1.0, exceptions=(Exception,)):
    """Retry decorator with exponential backoff."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed: {e}")
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(current_delay)
                        current_delay *= 2  # Exponential backoff

            logger.error(f"All {max_attempts} attempts failed")
            raise last_exception
        return wrapper
    return decorator


class ImageProcessor:
    """Processor for image uploads and analysis."""

    def __init__(self):
        self.upload_dir = config.DATA_DIR / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        # Rate limiting
        self.api_call_count = 0
        self.api_call_reset_time = datetime.now()
        self.max_calls_per_minute = 10  # Stay well within Gemini free tier limit

        # Initialize Gemini
        self.gemini_available = bool(config.gemini_api_key)
        if self.gemini_available:
            try:
                import google.generativeai as genai
                genai.configure(api_key=config.gemini_api_key)
                self.gemini_model = genai.GenerativeModel(config.gemini_model)
                logger.info("Gemini Vision initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
                self.gemini_available = False
                self.gemini_model = None
        else:
            self.gemini_model = None

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        now = datetime.now()

        # Reset counter every minute
        if now >= self.api_call_reset_time:
            self.api_call_count = 0
            self.api_call_reset_time = now + timedelta(minutes=1)

        if self.api_call_count >= self.max_calls_per_minute:
            logger.warning(f"Rate limit reached ({self.api_call_count}/{self.max_calls_per_minute})")
            return False

        self.api_call_count += 1
        return True

    async def _wait_for_rate_limit(self, timeout: float = 30.0):
        """Wait until rate limit allows."""
        start = datetime.now()
        while not self._check_rate_limit():
            await asyncio.sleep(1.0)
            if (datetime.now() - start).total_seconds() > timeout:
                return False
        return True
    
    def save_uploaded_image(
        self,
        image_data: bytes,
        telegram_id: str,
        file_type: str = "food"
    ) -> Tuple[bool, str, str]:
        """
        Save uploaded image to disk.
        
        Args:
            image_data: Raw image bytes
            telegram_id: User's Telegram ID
            file_type: Type of image (food, blood_test, body, etc.)
        
        Returns:
            Tuple of (success, file_path, message)
        """
        try:
            # Create user-specific directory
            user_dir = self.upload_dir / telegram_id / file_type
            user_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{file_type}_{timestamp}.jpg"
            filepath = user_dir / filename
            
            # Save file
            with open(filepath, 'wb') as f:
                f.write(image_data)
            
            return True, str(filepath), f"✅ Изображение сохранено: {filename}"
            
        except Exception as e:
            logger.error(f"Error saving image: {e}")
            return False, "", f"❌ Ошибка сохранения: {e}"
    
    @retry_on_exception(max_attempts=3, delay=1.0, exceptions=(Exception,))
    async def analyze_food_image(
        self,
        image_path: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Analyze food image using Gemini Vision.
        With caching, retries, and rate limiting.

        Args:
            image_path: Path to image file
            user_context: Optional user context for personalization

        Returns:
            Tuple of (success, result_dict, message)
            result_dict contains:
                - foods: List of recognized food items
                - total_nutrition: Combined nutrition info
                - confidence: Recognition confidence
                - suggestions: AI suggestions
        """
        if not self.gemini_available:
            return False, {}, "❌ Сервис распознавания еды недоступен"

        # Wait for rate limit
        if not await self._wait_for_rate_limit(timeout=60.0):
            return False, {}, "⏳ Превышен лимит запросов. Попробуйте через минуту"

        try:
            # Load image and create hash for caching
            from PIL import Image
            image = Image.open(image_path)

            # Create cache key from image hash
            image_hash = hashlib.md5(open(image_path, 'rb').read()).hexdigest()
            cache_key = f"food_{image_hash}_{user_context.get('goal', '') if user_context else ''}"

            # Check cache (24 hour TTL for food images)
            cached_result = self._get_cached_result(cache_key, ttl_hours=24)
            if cached_result:
                logger.info(f"Using cached result for food image")
                return True, cached_result, "✅ Еда распознана (из кэша)"

            # Build prompt
            prompt = self._build_food_analysis_prompt(user_context)

            # Call Gemini with timeout
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.gemini_model.generate_content([
                    prompt,
                    image
                ], generation_config={
                    'temperature': 0.2,
                    'top_p': 0.8,
                    'max_output_tokens': 2048,
                }, request_options={'timeout': 30000})
            )

            # Parse response
            result = self._parse_food_response(response.text)

            if result:
                # Cache the result
                self._cache_result(cache_key, result)
                return True, result, "✅ Еда распознана"
            else:
                return False, {}, "❌ Не удалось распознать еду"

        except asyncio.TimeoutError:
            logger.error("Gemini API timeout")
            return False, {}, "⏱️ Превышено время ожидания ответа"
        except Exception as e:
            logger.error(f"Error analyzing food image: {e}")
            return False, {}, f"❌ Ошибка анализа: {str(e)}"

    def _get_cached_result(self, cache_key: str, ttl_hours: int = 24) -> Optional[Dict]:
        """Get cached result if available and not expired."""
        cache_file = config.DATA_DIR / "cache" / f"{cache_key}.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        if not cache_file.exists():
            return None

        try:
            # Check file age
            file_mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if datetime.now() - file_mtime > timedelta(hours=ttl_hours):
                cache_file.unlink()  # Delete expired cache
                return None

            # Read cached data
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json_lib.load(f)
        except Exception as e:
            logger.debug(f"Cache read error: {e}")
            return None

    def _cache_result(self, cache_key: str, result: Dict):
        """Save result to cache."""
        cache_file = config.DATA_DIR / "cache" / f"{cache_key}.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json_lib.dump(result, f, ensure_ascii=False, indent=2)
            logger.debug(f"Cached result for {cache_key}")
        except Exception as e:
            logger.debug(f"Cache write error: {e}")
    
    def _build_food_analysis_prompt(
        self,
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build prompt for food analysis."""
        prompt = """
Ты - профессиональный нутрициолог с экспертизой в распознавании еды.
Проанализируй изображение и определи все видимые продукты питания.

Верни ответ ТОЛЬКО в формате JSON:
{
    "foods": [
        {
            "name": "название продукта на русском",
            "weight_grams": примерный_вес_в_граммах,
            "calories_per_100g": калории_на_100г,
            "protein_per_100g": белки_на_100г,
            "fat_per_100g": жиры_на_100г,
            "carbs_per_100g": углеводы_на_100г,
            "confidence": уверенность_от_0.0_до_1.0
        }
    ],
    "total_estimated_calories": общая_калорийность_блюда,
    "suggestions": ["советы по улучшению блюда"],
    "notes": "дополнительные заметки"
}

Важно:
- Оценивай вес порции визуально на основе стандартных размеров посуды
- Учитывай способ приготовления (жареное, вареное, на пару)
- Используй средние значения калорийности для продуктов
- Если видишь несколько продуктов, перечисли все
- Уверенность от 0.0 (не уверен) до 1.0 (полностью уверен)
- ВСЕГДА возвращай только JSON, без дополнительного текста
"""
        
        if user_context:
            goal = user_context.get('goal', '')
            if goal == 'weight_loss':
                prompt += "\n\nПользователь хочет похудеть. Предлагай низкокалорийные альтернативы."
            elif goal == 'muscle_gain':
                prompt += "\n\nПользователь набирает массу. Акцентируй внимание на белке."
        
        return prompt
    
    def _parse_food_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse Gemini response for food analysis."""
        import json
        
        try:
            # Clean response
            cleaned = response_text.strip()
            
            # Remove markdown code blocks
            if cleaned.startswith('```'):
                lines = cleaned.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                cleaned = '\n'.join(lines)
            
            # Extract JSON
            start_idx = cleaned.find('{')
            end_idx = cleaned.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = cleaned[start_idx:end_idx]
            else:
                json_str = cleaned
            
            data = json.loads(json_str)
            
            # Validate structure
            if 'foods' not in data or not isinstance(data['foods'], list):
                return None
            
            # Process foods
            processed_foods = []
            total_calories = 0
            
            for food in data['foods']:
                if not all(k in food for k in ['name', 'weight_grams']):
                    continue
                
                weight = food.get('weight_grams', 100)
                calories_per_100 = food.get('calories_per_100g', 0)
                protein_per_100 = food.get('protein_per_100g', 0)
                fat_per_100 = food.get('fat_per_100g', 0)
                carbs_per_100 = food.get('carbs_per_100g', 0)
                
                # Calculate nutrition for actual portion
                portion_data = {
                    'name': food.get('name', 'Неизвестный продукт'),
                    'weight_g': weight,
                    'calories': round((calories_per_100 * weight) / 100, 1),
                    'protein': round((protein_per_100 * weight) / 100, 1),
                    'fat': round((fat_per_100 * weight) / 100, 1),
                    'carbs': round((carbs_per_100 * weight) / 100, 1),
                    'confidence': food.get('confidence', 0.5),
                    'per_100g': {
                        'calories': calories_per_100,
                        'protein': protein_per_100,
                        'fat': fat_per_100,
                        'carbs': carbs_per_100
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
    
    async def analyze_blood_test_image(
        self,
        image_path: str
    ) -> Tuple[bool, List[Dict[str, Any]], str]:
        """
        Analyze blood test image using Gemini Vision (OCR).
        
        Args:
            image_path: Path to image file
        
        Returns:
            Tuple of (success, results_list, message)
            results_list contains extracted test results
        """
        if not self.gemini_available:
            return False, [], "❌ Сервис распознавания анализов недоступен"
        
        try:
            from PIL import Image
            image = Image.open(image_path)
            
            # Build OCR prompt for blood tests
            prompt = """
Ты - медицинский OCR-эксперт. Извлеки все результаты анализов крови из изображения.

Верни ответ ТОЛЬКО в формате JSON:
{
    "tests": [
        {
            "name": "название показателя на русском",
            "value": числовое_значение,
            "unit": "единица_измерения",
            "reference_min": мин_норма (если есть),
            "reference_max": макс_норма (если есть)
        }
    ],
    "test_date": "дата_анализа (если указана)",
    "lab_name": "название_лаборатории (если указана)"
}

Распознавай следующие показатели:
- Гемоглобин, Эритроциты, Лейкоциты, Тромбоциты
- Глюкоза, Холестерин, Триглицериды
- АЛТ, АСТ, Билирубин, Креатинин
- ТТГ, Тестостерон, Витамин D, Ферритин
- И другие показатели

ВСЕГДА возвращай только JSON."""
            
            # Call Gemini
            response = self.gemini_model.generate_content([
                prompt,
                image
            ], generation_config={
                'temperature': 0.1,
                'max_output_tokens': 2048,
            })
            
            # Parse response
            results = self._parse_blood_test_response(response.text)
            
            if results:
                return True, results, "✅ Анализы распознаны"
            else:
                return False, [], "❌ Не удалось распознать анализы"
                
        except Exception as e:
            logger.error(f"Error analyzing blood test image: {e}")
            return False, [], f"❌ Ошибка распознавания: {e}"
    
    def _parse_blood_test_response(
        self,
        response_text: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Parse blood test OCR response."""
        import json
        
        try:
            cleaned = response_text.strip()
            
            # Remove markdown
            if cleaned.startswith('```'):
                lines = cleaned.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                cleaned = '\n'.join(lines)
            
            start_idx = cleaned.find('{')
            end_idx = cleaned.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = cleaned[start_idx:end_idx]
            else:
                json_str = cleaned
            
            data = json.loads(json_str)
            
            if 'tests' not in data or not isinstance(data['tests'], list):
                return None
            
            return data['tests']
            
        except Exception as e:
            logger.error(f"Error parsing blood test response: {e}")
            return None
    
    async def analyze_body_composition_image(
        self,
        image_path: str
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Analyze body composition image (Samsung Health screenshot, scale display).
        
        Args:
            image_path: Path to image file
        
        Returns:
            Tuple of (success, metrics_dict, message)
        """
        if not self.gemini_available:
            return False, {}, "❌ Сервис распознавания недоступен"
        
        try:
            from PIL import Image
            image = Image.open(image_path)
            
            prompt = """
Ты - OCR-эксперт для изображений состава тела.
Извлеки все метрики здоровья из изображения.

Верни ответ ТОЛЬКО в формате JSON:
{
    "weight_kg": вес_в_кг,
    "body_fat_percent": процент_жира,
    "muscle_mass_kg": мышечная_масса,
    "water_percent": процент_воды,
    "bmi": индекс_массы_тела,
    "visceral_fat": висцеральный_жир,
    "bone_mass": костная_масса,
    "protein": белок,
    "date": "дата_измерения (если есть)"
}

Извлеки только числовые значения. Если показатель не найден, не включай его.
ВСЕГДА возвращай только JSON."""
            
            response = self.gemini_model.generate_content([
                prompt,
                image
            ], generation_config={
                'temperature': 0.1,
                'max_output_tokens': 1024,
            })
            
            result = self._parse_body_composition_response(response.text)
            
            if result:
                return True, result, "✅ Данные распознаны"
            else:
                return False, {}, "❌ Не удалось распознать данные"
                
        except Exception as e:
            logger.error(f"Error analyzing body composition image: {e}")
            return False, {}, f"❌ Ошибка распознавания: {e}"
    
    def _parse_body_composition_response(
        self,
        response_text: str
    ) -> Optional[Dict[str, Any]]:
        """Parse body composition response."""
        import json
        
        try:
            cleaned = response_text.strip()
            
            if cleaned.startswith('```'):
                lines = cleaned.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                cleaned = '\n'.join(lines)
            
            start_idx = cleaned.find('{')
            end_idx = cleaned.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = cleaned[start_idx:end_idx]
            else:
                json_str = cleaned
            
            data = json.loads(json_str)
            
            # Filter out None values
            return {k: v for k, v in data.items() if v is not None}
            
        except Exception as e:
            logger.error(f"Error parsing body composition response: {e}")
            return None


class FoodScannerIntegration:
    """Integration with FoodScanner API (GitHub Lifeiser)."""
    
    def __init__(self):
        self.api_url = config.foodscanner_api_url
        self.is_available = bool(self.api_url)
        
        if self.is_available:
            logger.info(f"FoodScanner API URL: {self.api_url}")
        else:
            logger.warning("FoodScanner API not configured")
    
    async def scan_food(
        self,
        image_path: str
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Scan food using FoodScanner API.
        
        Args:
            image_path: Path to image file
        
        Returns:
            Tuple of (success, result_dict, message)
        """
        if not self.is_available:
            return False, {}, "❌ FoodScanner API не настроен"
        
        try:
            # Read image
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            # Send to FoodScanner API
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field('image', image_data, filename='food.jpg')
                
                async with session.post(
                    f"{self.api_url}/api/scan",
                    data=form
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return True, result, "✅ FoodScanner: еда распознана"
                    else:
                        error = await response.text()
                        logger.error(f"FoodScanner error: {error}")
                        return False, {}, "❌ Ошибка FoodScanner API"
                        
        except Exception as e:
            logger.error(f"Error calling FoodScanner: {e}")
            return False, {}, f"❌ Ошибка: {e}"


# Global instances
image_processor = ImageProcessor()
foodscanner = FoodScannerIntegration()
