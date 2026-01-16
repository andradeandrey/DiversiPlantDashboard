"""Crawler scheduler for automated data updates."""
from datetime import datetime
from typing import Dict, List, Optional
import logging
import os

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    HAS_SCHEDULER = True
except ImportError:
    HAS_SCHEDULER = False

from . import get_crawler, list_crawlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('crawler.scheduler')


class CrawlerScheduler:
    """
    Automated scheduler for crawler execution.

    Uses APScheduler for cron-based scheduling.
    Schedules are optimized to avoid API rate limits and server load.
    """

    # Default schedules (cron format)
    DEFAULT_SCHEDULES: Dict[str, str] = {
        'reflora': '0 2 * * 0',      # Sunday 2:00 AM
        'gbif': '0 3 * * 0',         # Sunday 3:00 AM
        'gift': '0 4 1 * *',         # 1st of month 4:00 AM
        'wcvp': '0 5 1 * *',         # 1st of month 5:00 AM
        'worldclim': '0 6 1 1,7 *',  # Jan 1 and Jul 1, 6:00 AM
        'treegoer': '0 2 15 * *',    # 15th of month 2:00 AM
        'iucn': '0 3 1 * *',         # 1st of month 3:00 AM
    }

    def __init__(self, db_url: str, job_store_url: str = None):
        """
        Initialize the scheduler.

        Args:
            db_url: Database URL for crawlers
            job_store_url: Optional SQLAlchemy URL for job persistence
        """
        if not HAS_SCHEDULER:
            raise ImportError(
                "APScheduler not installed. Install with: pip install apscheduler"
            )

        self.db_url = db_url
        self._schedules = self.DEFAULT_SCHEDULES.copy()

        # Configure job stores
        jobstores = {}
        if job_store_url:
            jobstores['default'] = SQLAlchemyJobStore(url=job_store_url)

        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            job_defaults={
                'coalesce': True,
                'max_instances': 1,
                'misfire_grace_time': 3600
            }
        )

        self._setup_jobs()

    def _setup_jobs(self):
        """Configure scheduled jobs for all crawlers."""
        for crawler_name, cron_expr in self._schedules.items():
            try:
                trigger = CronTrigger.from_crontab(cron_expr)
                self.scheduler.add_job(
                    func=self._run_crawler,
                    trigger=trigger,
                    args=[crawler_name],
                    id=f"crawler_{crawler_name}",
                    name=f"Crawler: {crawler_name}",
                    replace_existing=True
                )
                logger.info(f"Scheduled {crawler_name}: {cron_expr}")
            except Exception as e:
                logger.error(f"Error scheduling {crawler_name}: {e}")

    def _run_crawler(self, crawler_name: str, mode: str = 'incremental'):
        """
        Execute a crawler.

        Args:
            crawler_name: Name of the crawler to run
            mode: 'full' or 'incremental'
        """
        logger.info(f"Starting scheduled run of {crawler_name}")

        try:
            crawler = get_crawler(crawler_name, self.db_url)
            if crawler:
                crawler.run(mode=mode)
                logger.info(f"Completed {crawler_name}: {crawler.stats}")
            else:
                logger.error(f"Crawler not found: {crawler_name}")

        except Exception as e:
            logger.error(f"Crawler {crawler_name} failed: {e}")
            raise

    def set_schedule(self, crawler_name: str, cron_expr: str):
        """
        Update schedule for a crawler.

        Args:
            crawler_name: Name of the crawler
            cron_expr: Cron expression (e.g., "0 2 * * 0")
        """
        if crawler_name not in list_crawlers():
            raise ValueError(f"Unknown crawler: {crawler_name}")

        self._schedules[crawler_name] = cron_expr

        try:
            trigger = CronTrigger.from_crontab(cron_expr)
            job_id = f"crawler_{crawler_name}"

            if self.scheduler.get_job(job_id):
                self.scheduler.reschedule_job(job_id, trigger=trigger)
            else:
                self.scheduler.add_job(
                    func=self._run_crawler,
                    trigger=trigger,
                    args=[crawler_name],
                    id=job_id,
                    name=f"Crawler: {crawler_name}",
                    replace_existing=True
                )

            logger.info(f"Updated schedule for {crawler_name}: {cron_expr}")

        except Exception as e:
            logger.error(f"Error updating schedule for {crawler_name}: {e}")
            raise

    def disable_crawler(self, crawler_name: str):
        """Disable scheduled runs for a crawler."""
        job_id = f"crawler_{crawler_name}"
        if self.scheduler.get_job(job_id):
            self.scheduler.pause_job(job_id)
            logger.info(f"Disabled {crawler_name}")

    def enable_crawler(self, crawler_name: str):
        """Re-enable scheduled runs for a crawler."""
        job_id = f"crawler_{crawler_name}"
        if self.scheduler.get_job(job_id):
            self.scheduler.resume_job(job_id)
            logger.info(f"Enabled {crawler_name}")

    def run_now(self, crawler_name: str, mode: str = 'incremental'):
        """
        Trigger immediate execution of a crawler.

        Args:
            crawler_name: Name of the crawler
            mode: 'full' or 'incremental'
        """
        logger.info(f"Triggering immediate run of {crawler_name}")
        self._run_crawler(crawler_name, mode)

    def get_status(self) -> List[Dict]:
        """Get status of all scheduled jobs."""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': str(job.next_run_time) if job.next_run_time else None,
                'pending': job.pending,
            })
        return jobs

    def get_schedules(self) -> Dict[str, str]:
        """Get current schedules for all crawlers."""
        return self._schedules.copy()

    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")

    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")

    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self.scheduler.running


# Singleton instance
_scheduler: Optional[CrawlerScheduler] = None


def get_scheduler(db_url: str = None) -> Optional[CrawlerScheduler]:
    """Get or create the scheduler instance."""
    global _scheduler

    if _scheduler is None:
        if db_url is None:
            db_url = os.environ.get('DATABASE_URL', '')

        if db_url:
            _scheduler = CrawlerScheduler(db_url)

    return _scheduler
