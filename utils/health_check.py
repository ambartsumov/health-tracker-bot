"""
Health check and monitoring module for Health Bot.
Provides system status, metrics, and monitoring endpoints.
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class HealthChecker:
    """System health checker for monitoring."""

    def __init__(self):
        self.start_time = datetime.utcnow()
        self.last_db_check: Optional[datetime] = None
        self.last_api_check: Optional[datetime] = None
        self.db_healthy = True
        self.telegram_healthy = True
        self.gemini_healthy = True
        self.deepseek_healthy = True
        self.request_count = 0
        self.error_count = 0

    def get_uptime(self) -> str:
        """Get bot uptime as human-readable string."""
        delta = datetime.utcnow() - self.start_time
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        
        if days > 0:
            return f"{days}д {hours}ч {minutes}м"
        elif hours > 0:
            return f"{hours}ч {minutes}м"
        else:
            return f"{minutes}м"

    def increment_request(self):
        """Increment request counter."""
        self.request_count += 1

    def increment_error(self):
        """Increment error counter."""
        self.error_count += 1

    def get_error_rate(self) -> float:
        """Get error rate percentage."""
        if self.request_count == 0:
            return 0.0
        return round((self.error_count / self.request_count) * 100, 2)

    async def check_database(self, db_manager) -> bool:
        """
        Check database connectivity.
        
        Returns:
            True if database is healthy
        """
        try:
            # Try to get a user (simple query)
            with db_manager.session_scope() as session:
                session.execute("SELECT 1")
            self.db_healthy = True
            self.last_db_check = datetime.utcnow()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            self.db_healthy = False
            return False

    async def check_telegram_bot(self, bot) -> bool:
        """
        Check Telegram bot connectivity.
        
        Returns:
            True if bot is healthy
        """
        try:
            # Try to get bot info
            await bot.get_me()
            self.telegram_healthy = True
            return True
        except Exception as e:
            logger.error(f"Telegram bot health check failed: {e}")
            self.telegram_healthy = False
            return False

    async def check_gemini_api(self, gemini_client) -> bool:
        """
        Check Gemini API connectivity.
        
        Returns:
            True if API is healthy
        """
        try:
            # Simple API call
            await gemini_client.generate_content("test")
            self.gemini_healthy = True
            self.last_api_check = datetime.utcnow()
            return True
        except Exception as e:
            logger.error(f"Gemini API health check failed: {e}")
            self.gemini_healthy = False
            return False

    async def check_deepseek_api(self, deepseek_client) -> bool:
        """
        Check DeepSeek API connectivity.
        
        Returns:
            True if API is healthy
        """
        try:
            # Simple API call
            await deepseek_client.chat("test")
            self.deepseek_healthy = True
            self.last_api_check = datetime.utcnow()
            return True
        except Exception as e:
            logger.error(f"DeepSeek API health check failed: {e}")
            self.deepseek_healthy = False
            return False

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get current health status of all components.
        
        Returns:
            Dictionary with all health metrics
        """
        # Determine overall status
        all_healthy = (
            self.db_healthy and
            self.telegram_healthy and
            self.gemini_healthy and
            self.deepseek_healthy
        )
        
        if all_healthy:
            status = "healthy"
        elif self.db_healthy and self.telegram_healthy:
            status = "degraded"  # Some services down but core works
        else:
            status = "unhealthy"
        
        return {
            "status": status,
            "uptime": self.get_uptime(),
            "start_time": self.start_time.isoformat(),
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "database": {
                    "healthy": self.db_healthy,
                    "last_check": self.last_db_check.isoformat() if self.last_db_check else None
                },
                "telegram": {
                    "healthy": self.telegram_healthy
                },
                "gemini": {
                    "healthy": self.gemini_healthy,
                    "last_check": self.last_api_check.isoformat() if self.last_api_check else None
                },
                "deepseek": {
                    "healthy": self.deepseek_healthy
                }
            },
            "metrics": {
                "total_requests": self.request_count,
                "total_errors": self.error_count,
                "error_rate_percent": self.get_error_rate()
            }
        }

    def get_status_text(self) -> str:
        """Get human-readable status text."""
        status = self.get_health_status()
        
        emoji = "✅" if status["status"] == "healthy" else "⚠️" if status["status"] == "degraded" else "❌"
        
        text = f"{emoji} **Статус бота: {status['status'].upper()}**\n\n"
        text += f"⏱ **Время работы:** {status['uptime']}\n"
        text += f"📅 **Запущен:** {status['start_time'][:10]}\n\n"
        
        text += "**Сервисы:**\n"
        services = status["services"]
        text += f"{'✅' if services['database']['healthy'] else '❌'} База данных\n"
        text += f"{'✅' if services['telegram']['healthy'] else '❌'} Telegram Bot\n"
        text += f"{'✅' if services['gemini']['healthy'] else '❌'} Gemini API\n"
        text += f"{'✅' if services['deepseek']['healthy'] else '❌'} DeepSeek API\n\n"
        
        metrics = status["metrics"]
        text += "**Метрики:**\n"
        text += f"📊 Запросов: {metrics['total_requests']}\n"
        text += f"⚠️ Ошибок: {metrics['total_errors']}\n"
        text += f"📈 Error Rate: {metrics['error_rate_percent']}%\n"
        
        return text


# Global health checker instance
health_checker = HealthChecker()


# Health check endpoint for bot commands
async def health_check_command(user_id: int = None) -> str:
    """
    Get health check response for Telegram command.
    
    Args:
        user_id: Optional user ID for permission check
    
    Returns:
        Formatted health status text
    """
    return health_checker.get_status_text()


# Background health check scheduler
async def run_periodic_health_checks(interval: int = 300):
    """
    Run periodic health checks in background.
    
    Args:
        interval: Check interval in seconds (default 5 minutes)
    """
    from database.manager import db_manager
    from modules.integrations import deepseek_client, gemini_client
    
    while True:
        try:
            await asyncio.sleep(interval)
            
            # Check database
            await health_checker.check_database(db_manager)
            
            # Note: API checks are skipped to avoid using quota
            # They will be checked on first actual use
            
            logger.info(
                f"Health check: DB={health_checker.db_healthy}, "
                f"Requests={health_checker.request_count}, "
                f"Errors={health_checker.error_count}"
            )
            
        except Exception as e:
            logger.error(f"Error in periodic health check: {e}")
