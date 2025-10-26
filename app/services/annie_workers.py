"""
Annie Background Workers - Automated execution of Annie's 18 functions
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session
from app.config.db import get_db
from app.models.userModels import Companies
from app.services.annie_ai import annie_ai
import schedule
import time
from threading import Thread

logger = logging.getLogger(__name__)

class AnnieWorkerScheduler:
    """Scheduler for Annie's background workers"""
    
    def __init__(self):
        self.running = False
        self.worker_thread = None
        
    def start(self):
        """Start the background worker scheduler"""
        if self.running:
            logger.warning("Annie workers already running")
            return
            
        self.running = True
        self.worker_thread = Thread(target=self._run_scheduler, daemon=True)
        self.worker_thread.start()
        logger.info("Annie background workers started")
    
    def stop(self):
        """Stop the background worker scheduler"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join()
        logger.info("Annie background workers stopped")
    
    def _run_scheduler(self):
        """Run the scheduler in a separate thread"""
        # Schedule Annie's functions with different intervals
        
        # High-frequency functions (every hour)
        schedule.every().hour.do(self._run_high_frequency_functions)
        
        # Medium-frequency functions (every 4 hours)
        schedule.every(4).hours.do(self._run_medium_frequency_functions)
        
        # Low-frequency functions (daily)
        schedule.every().day.at("06:00").do(self._run_daily_functions)
        
        # Weekly functions (Monday at 8 AM)
        schedule.every().monday.at("08:00").do(self._run_weekly_functions)
        
        while self.running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    async def _run_for_all_subscribers(self, function_name: str):
        """Run a specific Annie function for all active subscribers"""
        try:
            db = next(get_db())
            subscribers = db.query(Companies.subscriber_id).filter(
                Companies.subscriber_id.isnot(None),
                Companies.isActive == True
            ).distinct().all()
            
            for (subscriber_id,) in subscribers:
                try:
                    function = getattr(annie_ai, function_name)
                    await function(subscriber_id)
                    logger.info(f"Ran {function_name} for subscriber {subscriber_id}")
                except Exception as e:
                    logger.error(f"Error running {function_name} for subscriber {subscriber_id}: {e}")
            
        except Exception as e:
            logger.error(f"Error in _run_for_all_subscribers: {e}")
        finally:
            db.close()
    
    def _run_high_frequency_functions(self):
        """Run functions that need frequent updates (every hour)"""
        high_frequency_functions = [
            "banking_cash_flow_assistant",
            "dispatch_coordinator",
            "safety_compliance_auditor",
            "weather_traffic_intelligence"
        ]
        
        for function_name in high_frequency_functions:
            asyncio.create_task(self._run_for_all_subscribers(function_name))
    
    def _run_medium_frequency_functions(self):
        """Run functions that need regular updates (every 4 hours)"""
        medium_frequency_functions = [
            "accounting_assistant",
            "payroll_manager",
            "load_board_rate_intelligence",
            "customer_relationship_monitor",
            "performance_analytics",
            "compliance_expiration_manager"
        ]
        
        for function_name in medium_frequency_functions:
            asyncio.create_task(self._run_for_all_subscribers(function_name))
    
    def _run_daily_functions(self):
        """Run functions that need daily updates"""
        daily_functions = [
            "equipment_maintenance_predictor",
            "document_management_assistant",
            "route_fuel_optimizer",
            "load_optimization_advisor",
            "customer_service_automation",
            "vendor_management"
        ]
        
        for function_name in daily_functions:
            asyncio.create_task(self._run_for_all_subscribers(function_name))
    
    def _run_weekly_functions(self):
        """Run functions that need weekly updates"""
        weekly_functions = [
            "multi_leg_load_coordinator",
            "compliance_score_tracker"
        ]
        
        for function_name in weekly_functions:
            asyncio.create_task(self._run_for_all_subscribers(function_name))

# Global scheduler instance
annie_scheduler = AnnieWorkerScheduler()

def start_annie_workers():
    """Start Annie's background workers"""
    annie_scheduler.start()

def stop_annie_workers():
    """Stop Annie's background workers"""
    annie_scheduler.stop()

# Manual trigger functions for testing and on-demand execution

async def trigger_annie_function(function_name: str, subscriber_id: str = None):
    """Manually trigger a specific Annie function"""
    try:
        if subscriber_id:
            # Run for specific subscriber
            function = getattr(annie_ai, function_name)
            await function(subscriber_id)
            logger.info(f"Manually triggered {function_name} for subscriber {subscriber_id}")
        else:
            # Run for all subscribers
            await annie_scheduler._run_for_all_subscribers(function_name)
            logger.info(f"Manually triggered {function_name} for all subscribers")
    except Exception as e:
        logger.error(f"Error manually triggering {function_name}: {e}")
        raise

async def run_all_annie_functions(subscriber_id: str):
    """Run all 18 Annie functions for a specific subscriber"""
    try:
        await annie_ai.run_all_functions(subscriber_id)
        logger.info(f"Ran all Annie functions for subscriber {subscriber_id}")
    except Exception as e:
        logger.error(f"Error running all Annie functions for subscriber {subscriber_id}: {e}")
        raise

# Function categories for organized execution
ANNIE_FUNCTIONS = {
    "accounting": [
        "accounting_assistant",
        "customer_relationship_monitor",
        "vendor_management"
    ],
    "operations": [
        "dispatch_coordinator",
        "load_board_rate_intelligence",
        "load_optimization_advisor",
        "multi_leg_load_coordinator"
    ],
    "compliance": [
        "safety_compliance_auditor",
        "compliance_expiration_manager",
        "compliance_score_tracker"
    ],
    "financial": [
        "payroll_manager",
        "banking_cash_flow_assistant",
        "performance_analytics"
    ],
    "logistics": [
        "equipment_maintenance_predictor",
        "route_fuel_optimizer",
        "document_management_assistant"
    ],
    "customer_service": [
        "customer_service_automation",
        "weather_traffic_intelligence"
    ]
}

async def run_annie_functions_by_category(category: str, subscriber_id: str = None):
    """Run Annie functions by category"""
    if category not in ANNIE_FUNCTIONS:
        raise ValueError(f"Invalid category: {category}")
    
    functions = ANNIE_FUNCTIONS[category]
    
    if subscriber_id:
        # Run for specific subscriber
        for function_name in functions:
            try:
                function = getattr(annie_ai, function_name)
                await function(subscriber_id)
                logger.info(f"Ran {function_name} for subscriber {subscriber_id}")
            except Exception as e:
                logger.error(f"Error running {function_name} for subscriber {subscriber_id}: {e}")
    else:
        # Run for all subscribers
        for function_name in functions:
            await annie_scheduler._run_for_all_subscribers(function_name)

# Health check function
async def annie_health_check():
    """Check if Annie workers are running properly"""
    try:
        db = next(get_db())
        subscriber_count = db.query(Companies.subscriber_id).filter(
            Companies.subscriber_id.isnot(None),
            Companies.isActive == True
        ).distinct().count()
        
        return {
            "status": "healthy" if annie_scheduler.running else "stopped",
            "active_subscribers": subscriber_count,
            "scheduler_running": annie_scheduler.running,
            "last_check": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error in Annie health check: {e}")
        return {
            "status": "error",
            "error": str(e),
            "last_check": datetime.utcnow().isoformat()
        }
    finally:
        db.close()
