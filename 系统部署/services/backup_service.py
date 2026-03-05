import os
import shutil
import logging
from datetime import datetime
from typing import Optional
import json

logger = logging.getLogger(__name__)


class BackupService:
    """数据库备份服务"""

    def __init__(self, backup_dir: str = None, max_backups: int = 10):
        """
        初始化备份服务
        
        Args:
            backup_dir: 备份目录路径，默认为 instance/backups
            max_backups: 最多保留的备份文件数量
        """
        self.base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        self.backup_dir = backup_dir or os.path.join(self.base_dir, 'instance', 'backups')
        self.max_backups = max_backups
        self.db_path = os.path.join(self.base_dir, 'instance', 'douyin_system.db')
        
        os.makedirs(self.backup_dir, exist_ok=True)

    def get_backup_filename(self) -> str:
        """生成备份文件名"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'douyin_system_{timestamp}.db'

    def create_backup(self) -> Optional[str]:
        """
        创建数据库备份
        
        Returns:
            备份文件路径，失败返回 None
        """
        try:
            if not os.path.exists(self.db_path):
                logger.error(f"数据库文件不存在: {self.db_path}")
                return None

            backup_filename = self.get_backup_filename()
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            shutil.copy2(self.db_path, backup_path)
            
            logger.info(f"数据库备份成功: {backup_path}")
            
            self.cleanup_old_backups()
            
            self._save_backup_info(backup_path)
            
            return backup_path

        except Exception as e:
            logger.error(f"数据库备份失败: {str(e)}")
            return None

    def cleanup_old_backups(self):
        """清理旧备份，保留最近的 N 个"""
        try:
            backup_files = []
            for f in os.listdir(self.backup_dir):
                if f.startswith('douyin_system_') and f.endswith('.db'):
                    full_path = os.path.join(self.backup_dir, f)
                    backup_files.append((full_path, os.path.getmtime(full_path)))
            
            backup_files.sort(key=lambda x: x[1], reverse=True)
            
            for old_file, _ in backup_files[self.max_backups:]:
                try:
                    os.remove(old_file)
                    info_file = old_file.replace('.db', '_info.json')
                    if os.path.exists(info_file):
                        os.remove(info_file)
                    logger.info(f"已删除旧备份: {old_file}")
                except Exception as e:
                    logger.warning(f"删除旧备份失败: {old_file}, {str(e)}")

        except Exception as e:
            logger.warning(f"清理旧备份时出错: {str(e)}")

    def _save_backup_info(self, backup_path: str):
        """保存备份元信息"""
        info = {
            'backup_file': os.path.basename(backup_path),
            'created_at': datetime.now().isoformat(),
            'size_bytes': os.path.getsize(backup_path),
            'db_source': self.db_path
        }
        info_path = backup_path.replace('.db', '_info.json')
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

    def restore_backup(self, backup_filename: str) -> bool:
        """
        恢复数据库备份
        
        Args:
            backup_filename: 备份文件名
            
        Returns:
            是否恢复成功
        """
        try:
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            if not os.path.exists(backup_path):
                logger.error(f"备份文件不存在: {backup_path}")
                return False
            
            backup_file = f"{backup_path}.bak"
            if os.path.exists(self.db_path):
                shutil.copy2(self.db_path, backup_file)
            
            shutil.copy2(backup_path, self.db_path)
            
            logger.info(f"数据库恢复成功: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"数据库恢复失败: {str(e)}")
            return False

    def list_backups(self) -> list:
        """
        列出所有备份文件
        
        Returns:
            备份文件信息列表
        """
        backups = []
        try:
            for f in os.listdir(self.backup_dir):
                if f.startswith('douyin_system_') and f.endswith('.db'):
                    full_path = os.path.join(self.backup_dir, f)
                    info_path = full_path.replace('.db', '_info.json')
                    
                    info = {}
                    if os.path.exists(info_path):
                        with open(info_path, 'r', encoding='utf-8') as fp:
                            info = json.load(fp)
                    
                    backups.append({
                        'filename': f,
                        'path': full_path,
                        'size': os.path.getsize(full_path),
                        'created': info.get('created_at', datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat())
                    })
            
            backups.sort(key=lambda x: x['created'], reverse=True)
            
        except Exception as e:
            logger.error(f"列出备份文件失败: {str(e)}")
        
        return backups

    def get_latest_backup(self) -> Optional[str]:
        """获取最新的备份文件路径"""
        backups = self.list_backups()
        return backups[0]['path'] if backups else None


backup_service = BackupService()
