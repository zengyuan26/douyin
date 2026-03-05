from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from services.backup_service import backup_service
from services.scheduler_service import scheduler_service
import logging

logger = logging.getLogger(__name__)

backup_api = Blueprint('backup_api', __name__)


@backup_api.route('/backup/create', methods=['POST'])
@login_required
def create_backup():
    """手动创建备份"""
    try:
        backup_path = backup_service.create_backup()
        if backup_path:
            return jsonify({
                'success': True,
                'message': '备份成功',
                'backup_file': backup_path
            })
        else:
            return jsonify({
                'success': False,
                'message': '备份失败'
            }), 500
    except Exception as e:
        logger.error(f"手动备份失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'备份失败: {str(e)}'
        }), 500


@backup_api.route('/backup/list', methods=['GET'])
@login_required
def list_backups():
    """获取备份列表"""
    try:
        backups = backup_service.list_backups()
        return jsonify({
            'success': True,
            'backups': backups
        })
    except Exception as e:
        logger.error(f"获取备份列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@backup_api.route('/backup/restore/<filename>', methods=['POST'])
@login_required
def restore_backup(filename):
    """恢复备份"""
    try:
        success = backup_service.restore_backup(filename)
        if success:
            return jsonify({
                'success': True,
                'message': f'恢复成功: {filename}'
            })
        else:
            return jsonify({
                'success': False,
                'message': '恢复失败'
            }), 500
    except Exception as e:
        logger.error(f"恢复备份失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'恢复失败: {str(e)}'
        }), 500


@backup_api.route('/backup/jobs', methods=['GET'])
@login_required
def get_jobs():
    """获取定时任务列表"""
    try:
        jobs = scheduler_service.get_jobs()
        return jsonify({
            'success': True,
            'jobs': jobs
        })
    except Exception as e:
        logger.error(f"获取定时任务失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@backup_api.route('/backup/jobs', methods=['POST'])
@login_required
def add_backup_job():
    """添加定时备份任务"""
    try:
        data = request.get_json() or {}
        job_type = data.get('type', 'daily')
        
        if job_type == 'daily':
            hour = data.get('hour', 2)
            minute = data.get('minute', 0)
            scheduler_service.add_daily_backup(hour=hour, minute=minute)
            message = f'已添加每日备份任务: {hour:02d}:{minute:02d}'
        else:
            hours = data.get('hours', 6)
            scheduler_service.add_interval_backup(hours=hours)
            message = f'已添加间隔备份任务: 每{hours}小时'
        
        return jsonify({
            'success': True,
            'message': message
        })
    except Exception as e:
        logger.error(f"添加定时任务失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@backup_api.route('/backup/jobs/<job_id>', methods=['DELETE'])
@login_required
def remove_backup_job(job_id):
    """删除定时备份任务"""
    try:
        scheduler_service.remove_backup_job(job_id)
        return jsonify({
            'success': True,
            'message': f'已删除任务: {job_id}'
        })
    except Exception as e:
        logger.error(f"删除定时任务失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
