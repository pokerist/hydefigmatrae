"""
Main entry point for HydePark sync system
"""
import time
import schedule
import threading
from config import Config
from processors.event_processor import EventProcessor
from dashboard.app import run_dashboard
from utils.logger import logger, request_logger


def run_sync_job():
    """Run the synchronization job"""
    try:
        logger.info("Starting sync job...")
        processor = EventProcessor()
        processor.process_events()
        logger.info("Sync job completed")
    except Exception as e:
        logger.error(f"Error in sync job: {e}")


def run_cleanup_job():
    """Run periodic cleanup of old logs"""
    try:
        logger.info("Running cleanup job...")
        request_logger.cleanup_old_logs()
        logger.info("Cleanup job completed")
    except Exception as e:
        logger.error(f"Error in cleanup job: {e}")


def start_scheduler():
    """Start the background scheduler"""
    logger.info("Starting scheduler...")
    
    # Schedule sync job
    schedule.every(Config.SYNC_INTERVAL_SECONDS).seconds.do(run_sync_job)
    
    # Schedule cleanup job (once per day at 2 AM)
    schedule.every().day.at("02:00").do(run_cleanup_job)
    
    # Run initial sync immediately
    run_sync_job()
    
    # Keep running scheduled jobs
    while True:
        schedule.run_pending()
        time.sleep(1)


def start_dashboard():
    """Start the dashboard web server"""
    logger.info(f"Starting dashboard on {Config.DASHBOARD_HOST}:{Config.DASHBOARD_PORT}")
    run_dashboard(Config.DASHBOARD_HOST, Config.DASHBOARD_PORT)


def main():
    """Main entry point"""
    try:
        # Ensure directories exist first (before validation)
        Config.ensure_directories()
        
        # Validate configuration
        Config.validate()
        
        logger.info("=" * 60)
        logger.info("HydePark Sync System Starting")
        logger.info("=" * 60)
        logger.info(f"Supabase URL: {Config.SUPABASE_BASE_URL}")
        logger.info(f"HikCentral URL: {Config.HIKCENTRAL_BASE_URL}")
        logger.info(f"Sync Interval: {Config.SYNC_INTERVAL_SECONDS} seconds")
        logger.info(f"Dashboard: http://{Config.DASHBOARD_HOST}:{Config.DASHBOARD_PORT}")
        logger.info(f"Data Directory: {Config.DATA_DIR.absolute()}")
        logger.info("=" * 60)
        
        # Start dashboard in separate thread
        dashboard_thread = threading.Thread(target=start_dashboard, daemon=True)
        dashboard_thread.start()
        
        # Wait a moment for dashboard to start
        time.sleep(2)
        logger.info("Dashboard started successfully")
        
        # Start scheduler in main thread
        start_scheduler()
    
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == '__main__':
    main()