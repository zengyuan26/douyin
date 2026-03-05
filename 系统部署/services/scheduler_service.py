import logging
import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class SchedulerService:
    """定时任务调度服务"""

    _instance = None
    _scheduler = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, backup_service=None):
        if not hasattr(self, '_initialized'):
            from services.backup_service import backup_service as default_backup_service
            self.backup_service = backup_service or default_backup_service
            self._initialized = True
            self._scheduler = BackgroundScheduler()

    def start(self):
        """启动调度器"""
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("定时任务调度器已启动")

    def shutdown(self):
        """停止调度器"""
        if self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("定时任务调度器已停止")

    def add_daily_backup(self, hour: int = 2, minute: int = 0):
        """
        添加每日定时备份
        
        Args:
            hour: 小时 (0-23)
            minute: 分钟 (0-59)
        """
        job = self._scheduler.add_job(
            self.backup_service.create_backup,
            CronTrigger(hour=hour, minute=minute),
            id='daily_backup',
            name='每日数据库备份',
            replace_existing=True
        )
        logger.info(f"已添加每日备份任务: {hour:02d}:{minute:02d}")
        return job

    def add_interval_backup(self, hours: int = 6):
        """
        添加间隔定时备份
        
        Args:
            hours: 备份间隔（小时）
        """
        job = self._scheduler.add_job(
            self.backup_service.create_backup,
            IntervalTrigger(hours=hours),
            id='interval_backup',
            name=f'每{hours}小时数据库备份',
            replace_existing=True
        )
        logger.info(f"已添加间隔备份任务: 每{hours}小时")
        return job

    def remove_backup_job(self, job_id: str = 'daily_backup'):
        """移除备份任务"""
        try:
            self._scheduler.remove_job(job_id)
            logger.info(f"已移除备份任务: {job_id}")
        except Exception as e:
            logger.warning(f"移除备份任务失败: {str(e)}")

    def get_jobs(self) -> list:
        """获取所有定时任务"""
        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': str(job.next_run_time) if job.next_run_time else None
            })
        return jobs

    def trigger_backup_now(self):
        """立即触发一次备份"""
        return self.backup_service.create_backup()


scheduler_service = SchedulerService()
