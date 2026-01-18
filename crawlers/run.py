#!/usr/bin/env python3
"""
Command-line runner for DiversiPlant crawlers.

Usage:
    python -m crawlers.run --source gbif --mode incremental
    python -m crawlers.run --source all --mode full
    python -m crawlers.run --list
"""
import argparse
import os
import sys
import logging
from datetime import datetime

from . import get_crawler, list_crawlers
from .scheduler import get_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('crawler.run')


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Run DiversiPlant data crawlers'
    )

    parser.add_argument(
        '--source', '-s',
        choices=list_crawlers() + ['all'],
        help='Crawler source to run (or "all" for all crawlers)'
    )

    parser.add_argument(
        '--mode', '-m',
        choices=['full', 'incremental'],
        default='incremental',
        help='Run mode: full or incremental (default: incremental)'
    )

    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List available crawlers'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--max-records',
        type=int,
        default=None,
        help='Maximum records to process (for testing)'
    )

    parser.add_argument(
        '--db-url',
        default=None,
        help='Database URL (default: from DATABASE_URL env var)'
    )

    parser.add_argument(
        '--schedule',
        action='store_true',
        help='Start the scheduler daemon'
    )

    parser.add_argument(
        '--by-family',
        action='store_true',
        help='[GBIF] Paginate by family to get ALL species (bypasses 100k limit)'
    )

    return parser.parse_args()


def run_crawler(source: str, mode: str, db_url: str, **kwargs):
    """Run a single crawler."""
    logger.info(f"Running {source} crawler in {mode} mode")
    start_time = datetime.now()

    try:
        crawler = get_crawler(source, db_url)
        if crawler is None:
            logger.error(f"Unknown crawler: {source}")
            return False

        crawler.run(mode=mode, **kwargs)

        elapsed = datetime.now() - start_time
        logger.info(f"Completed {source} in {elapsed}")
        logger.info(f"Stats: {crawler.stats}")
        return True

    except Exception as e:
        logger.error(f"Crawler {source} failed: {e}")
        return False


def run_all_crawlers(mode: str, db_url: str, **kwargs):
    """Run all crawlers sequentially."""
    results = {}
    for source in list_crawlers():
        success = run_crawler(source, mode, db_url, **kwargs)
        results[source] = 'success' if success else 'failed'

    logger.info("All crawlers completed:")
    for source, status in results.items():
        logger.info(f"  {source}: {status}")


def start_scheduler(db_url: str):
    """Start the scheduler daemon."""
    logger.info("Starting crawler scheduler...")

    scheduler = get_scheduler(db_url)
    if scheduler is None:
        logger.error("Failed to initialize scheduler")
        sys.exit(1)

    scheduler.start()
    logger.info("Scheduler started. Press Ctrl+C to stop.")

    try:
        # Keep running until interrupted
        import time
        while True:
            time.sleep(60)
            # Log status periodically
            jobs = scheduler.get_status()
            logger.info(f"Scheduler active with {len(jobs)} jobs")

    except KeyboardInterrupt:
        logger.info("Shutting down scheduler...")
        scheduler.stop()


def main():
    """Main entry point."""
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Get database URL
    db_url = args.db_url or os.environ.get('DATABASE_URL', '')
    if not db_url and not args.list:
        logger.error("Database URL not provided. Set DATABASE_URL environment variable or use --db-url")
        sys.exit(1)

    # List crawlers
    if args.list:
        print("Available crawlers:")
        for name in list_crawlers():
            print(f"  - {name}")
        sys.exit(0)

    # Start scheduler
    if args.schedule:
        start_scheduler(db_url)
        sys.exit(0)

    # Run crawler(s)
    if args.source:
        kwargs = {}
        if args.max_records:
            kwargs['max_records'] = args.max_records
        if args.by_family:
            kwargs['by_family'] = True

        if args.source == 'all':
            run_all_crawlers(args.mode, db_url, **kwargs)
        else:
            success = run_crawler(args.source, args.mode, db_url, **kwargs)
            sys.exit(0 if success else 1)
    else:
        logger.error("No source specified. Use --source or --list")
        sys.exit(1)


if __name__ == '__main__':
    main()
