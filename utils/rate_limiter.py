"""
Rate limiting utilities for API calls.
Prevents hitting API limits for Gemini, DeepSeek, and other services.
"""

import asyncio
import time
from typing import Optional, Dict, Any
from functools import wraps
from aiolimiter import AsyncLimiter
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter for API calls.
    Uses token bucket algorithm via aiolimiter.
    """

    def __init__(self):
        # Gemini API limits (free tier): 60 requests/minute
        self.gemini_limiter = AsyncLimiter(max_rate=50, time_period=60)
        
        # DeepSeek API limits: 100 requests/minute (adjust as needed)
        self.deepseek_limiter = AsyncLimiter(max_rate=80, time_period=60)
        
        # General API limiter for other services
        self.general_limiter = AsyncLimiter(max_rate=30, time_period=60)
        
        # Request tracking
        self.request_counts: Dict[str, int] = {
            'gemini': 0,
            'deepseek': 0,
            'general': 0
        }
        self.last_reset_time = time.time()

    async def acquire(self, service: str = 'general') -> bool:
        """
        Acquire permission to make a request.
        
        Args:
            service: Service name ('gemini', 'deepseek', 'general')
            
        Returns:
            True when permission granted
        """
        limiter = getattr(self, f'{service}_limiter', self.general_limiter)
        
        try:
            async with limiter:
                self.request_counts[service] = self.request_counts.get(service, 0) + 1
                return True
        except Exception as e:
            logger.error(f"Rate limiter error for {service}: {e}")
            # Wait and retry
            await asyncio.sleep(5)
            return await self.acquire(service)

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics."""
        current_time = time.time()
        
        # Reset counts every minute
        if current_time - self.last_reset_time > 60:
            self.request_counts = {k: 0 for k in self.request_counts}
            self.last_reset_time = current_time
        
        return {
            'gemini_requests': self.request_counts.get('gemini', 0),
            'deepseek_requests': self.request_counts.get('deepseek', 0),
            'general_requests': self.request_counts.get('general', 0),
            'gemini_limit': 50,
            'deepseek_limit': 80,
            'general_limit': 30
        }

    def reset_stats(self):
        """Reset request statistics."""
        self.request_counts = {k: 0 for k in self.request_counts}
        self.last_reset_time = time.time()


def rate_limit(service: str = 'general'):
    """
    Decorator for rate limiting async functions.
    
    Usage:
        @rate_limit('gemini')
        async def analyze_image(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            limiter = rate_limiter
            await limiter.acquire(service)
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Global instance
rate_limiter = RateLimiter()


class CircuitBreaker:
    """
    Circuit breaker pattern for API calls.
    Prevents cascading failures when API is down.
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time: Optional[float] = None
        self.state = 'closed'  # closed, open, half-open
        self._lock = asyncio.Lock()

    async def call(self, func, *args, **kwargs):
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Async function to call
            *args, **kwargs: Function arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        async with self._lock:
            # Check if we should try to recover
            if self.state == 'open':
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = 'half-open'
                    logger.info("Circuit breaker entering half-open state")
                else:
                    raise Exception(f"Circuit breaker is open. Retry in {self.recovery_timeout}s")

        try:
            result = await func(*args, **kwargs)
            
            # Success - reset failures
            async with self._lock:
                self.failures = 0
                self.state = 'closed'
            
            return result
            
        except Exception as e:
            async with self._lock:
                self.failures += 1
                self.last_failure_time = time.time()
                
                if self.failures >= self.failure_threshold:
                    self.state = 'open'
                    logger.warning(f"Circuit breaker opened after {self.failures} failures")
            
            raise e

    def get_state(self) -> Dict[str, Any]:
        """Get circuit breaker state."""
        return {
            'state': self.state,
            'failures': self.failures,
            'threshold': self.failure_threshold,
            'last_failure': self.last_failure_time
        }


# Circuit breakers for each API
gemini_circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
deepseek_circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
general_circuit = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
