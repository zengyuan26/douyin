"""
公开内容生成平台 - 认证服务

功能：
1. 用户注册
2. 邮箱验证
3. 登录/登出
4. 密码重置
5. 邮箱发送
"""

import secrets
import random
import hashlib
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional, Tuple
from flask import current_app
from flask_bcrypt import generate_password_hash, check_password_hash

logger = logging.getLogger(__name__)
from models.public_models import PublicUser, PublicUserProfile
from models.models import db
from services.public_cache import public_cache


class EmailService:
    """邮件发送服务（使用 smtplib）"""

    @classmethod
    def _get_smtp_config(cls):
        """获取 SMTP 配置"""
        app = current_app._get_current_object()
        return {
            'smtp_host': app.config.get('MAIL_SERVER', 'smtp.gmail.com'),
            'smtp_port': app.config.get('MAIL_PORT', 587),
            'smtp_user': app.config.get('MAIL_USERNAME'),
            'smtp_password': app.config.get('MAIL_PASSWORD'),
            'mail_use_tls': app.config.get('MAIL_USE_TLS', True),
            'mail_use_ssl': app.config.get('MAIL_USE_SSL', False),
            'default_sender': app.config.get('MAIL_DEFAULT_SENDER', app.config.get('MAIL_USERNAME')),
        }

    @classmethod
    def send_email(cls, to_email: str, subject: str, body: str, html: str = None) -> bool:
        """
        发送邮件

        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            body: 纯文本内容
            html: HTML 内容（可选）

        Returns:
            bool: 是否发送成功
        """
        try:
            config = cls._get_smtp_config()

            # 如果没有配置 SMTP，跳过发送（开发模式）
            if not config['smtp_user'] or not config['smtp_password']:
                logger.info("[EmailService] SMTP 未配置，跳过发送邮件到 %s", to_email)
                logger.debug("[EmailService] 主题: %s", subject)
                return False

            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = config['default_sender']
            msg['To'] = to_email

            # 添加纯文本
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            # 添加 HTML（如果有）
            if html:
                msg.attach(MIMEText(html, 'html', 'utf-8'))

            # 连接 SMTP 服务器
            if config['mail_use_ssl']:
                server = smtplib.SMTP_SSL(config['smtp_host'], config['smtp_port'])
            else:
                server = smtplib.SMTP(config['smtp_host'], config['smtp_port'])
                if config['mail_use_tls']:
                    server.starttls()

            # 登录
            server.login(config['smtp_user'], config['smtp_password'])

            # 发送
            server.sendmail(config['default_sender'], [to_email], msg.as_string())
            server.quit()

            logger.info("[EmailService] 邮件已发送到 %s", to_email)
            return True

        except Exception as e:
            logger.warning("[EmailService] 发送邮件失败: %s", e)
            return False


class AuthService:
    """认证服务"""

    # 验证码有效期（分钟）
    VERIFICATION_CODE_EXPIRES = 10

    # 密码重置token有效期（小时）
    RESET_TOKEN_EXPIRES = 24

    @classmethod
    def register(cls, email: str, password: str, nickname: str = None) -> Tuple[bool, str, Optional[PublicUser]]:
        """
        用户注册

        Args:
            email: 邮箱
            password: 密码（明文，会进行hash）
            nickname: 昵称（可选）

        Returns:
            (success, message, user)
        """
        # 检查邮箱是否已存在
        existing = PublicUser.query.filter_by(email=email).first()
        if existing:
            return False, '该邮箱已注册', None

        # 密码hash
        password_hash = cls._hash_password(password)

        # 创建用户
        user = PublicUser(
            email=email,
            password_hash=password_hash,
            nickname=nickname or email.split('@')[0],
            is_verified=False,
            verification_code=cls._generate_code(),
            verification_expires=datetime.utcnow() + timedelta(minutes=cls.VERIFICATION_CODE_EXPIRES),
        )
        db.session.add(user)
        db.session.flush()

        # 创建用户档案
        profile = PublicUserProfile(user_id=user.id)
        db.session.add(profile)
        db.session.commit()

        # 发送验证邮件
        try:
            cls._send_verification_email(user)
        except Exception as e:
            logger.warning("[AuthService] 发送验证邮件失败: %s", e)

        return True, '注册成功，请查收验证邮件', user

    @classmethod
    def verify_email(cls, email: str, code: str) -> Tuple[bool, str]:
        """
        验证邮箱

        Args:
            email: 邮箱
            code: 验证码

        Returns:
            (success, message)
        """
        user = PublicUser.query.filter_by(email=email).first()
        if not user:
            return False, '用户不存在'

        if user.is_verified:
            return True, '邮箱已验证'

        if user.verification_code != code:
            return False, '验证码错误'

        if user.verification_expires < datetime.utcnow():
            return False, '验证码已过期'

        user.is_verified = True
        user.verification_code = None
        user.verification_expires = None
        db.session.commit()

        return True, '验证成功'

    @classmethod
    def login(cls, email: str, password: str) -> Tuple[bool, str, Optional[PublicUser]]:
        """
        用户登录

        Args:
            email: 邮箱
            password: 密码（明文）

        Returns:
            (success, message, user)
        """
        user = PublicUser.query.filter_by(email=email).first()
        if not user:
            return False, '用户不存在或密码错误', None

        if not cls._verify_password(password, user.password_hash):
            return False, '用户不存在或密码错误', None

        if not user.is_active:
            return False, '账号已被禁用', None

        # 更新最后登录时间
        user.last_login = datetime.utcnow()
        db.session.commit()

        # 清除配额缓存
        public_cache.invalidate_user_quota(user.id)

        return True, '登录成功', user

    @classmethod
    def logout(cls, user_id: int) -> bool:
        """用户登出"""
        return True

    @classmethod
    def change_password(cls, user: PublicUser, old_password: str,
                      new_password: str) -> Tuple[bool, str]:
        """
        修改密码

        Args:
            user: 用户对象
            old_password: 旧密码
            new_password: 新密码

        Returns:
            (success, message)
        """
        if not cls._verify_password(old_password, user.password_hash):
            return False, '原密码错误'

        user.password_hash = cls._hash_password(new_password)
        db.session.commit()

        return True, '密码修改成功'

    @classmethod
    def request_password_reset(cls, email: str) -> Tuple[bool, str]:
        """
        请求密码重置

        Args:
            email: 邮箱

        Returns:
            (success, message)
        """
        user = PublicUser.query.filter_by(email=email).first()
        if not user:
            # 为防止枚举攻击，提示发送成功
            return True, '如果邮箱存在，重置邮件已发送'

        # 生成重置token
        reset_token = secrets.token_urlsafe(32)
        user.verification_code = reset_token
        user.verification_expires = datetime.utcnow() + timedelta(hours=cls.RESET_TOKEN_EXPIRES)
        db.session.commit()

        try:
            cls._send_password_reset_email(user, reset_token)
        except Exception as e:
            logger.warning("[AuthService] 发送重置邮件失败: %s", e)

        return True, '如果邮箱存在，重置邮件已发送'

    @classmethod
    def reset_password(cls, email: str, token: str, new_password: str) -> Tuple[bool, str]:
        """
        重置密码

        Args:
            email: 邮箱
            token: 重置token
            new_password: 新密码

        Returns:
            (success, message)
        """
        user = PublicUser.query.filter_by(email=email).first()
        if not user:
            return False, '用户不存在'

        if user.verification_code != token:
            return False, '重置链接无效'

        if user.verification_expires < datetime.utcnow():
            return False, '重置链接已过期'

        user.password_hash = cls._hash_password(new_password)
        user.verification_code = None
        user.verification_expires = None
        db.session.commit()

        return True, '密码重置成功'

    @classmethod
    def resend_verification(cls, email: str) -> Tuple[bool, str]:
        """
        重新发送验证邮件

        Args:
            email: 邮箱

        Returns:
            (success, message)
        """
        user = PublicUser.query.filter_by(email=email).first()
        if not user:
            return True, '验证邮件已发送'

        if user.is_verified:
            return False, '邮箱已验证'

        user.verification_code = cls._generate_code()
        user.verification_expires = datetime.utcnow() + timedelta(minutes=cls.VERIFICATION_CODE_EXPIRES)
        db.session.commit()

        try:
            cls._send_verification_email(user)
        except Exception as e:
            logger.warning("[AuthService] 发送验证邮件失败: %s", e)
            return False, '发送失败，请稍后重试'

        return True, '验证邮件已发送'

    @classmethod
    def _hash_password(cls, password: str) -> str:
        """密码hash（bcrypt，自动加salt）"""
        return generate_password_hash(password).decode('utf-8')

    @classmethod
    def _verify_password(cls, password: str, password_hash: str) -> bool:
        """验证密码（bcrypt + 兼容旧SHA256）"""
        # 优先用 bcrypt 验证（新格式）
        if password_hash and len(password_hash) == 60:
            return check_password_hash(password_hash, password)
        # 兼容旧 SHA256 格式（迁移时一次性验证成功后会重新hash）
        return hashlib.sha256(password.encode()).hexdigest() == password_hash

    @classmethod
    def _generate_code(cls) -> str:
        """生成6位验证码"""
        return ''.join([str(random.randint(0, 9)) for _ in range(6)])

    @classmethod
    def _send_verification_email(cls, user: PublicUser) -> None:
        """发送验证邮件"""
        subject = '验证您的邮箱 - 内容生成平台'
        body = f'''欢迎！请验证您的邮箱。

您的验证码是：{user.verification_code}

验证码 {cls.VERIFICATION_CODE_EXPIRES} 分钟内有效。
'''
        EmailService.send_email(user.email, subject, body)

    @classmethod
    def _send_password_reset_email(cls, user: PublicUser, token: str) -> None:
        """发送密码重置邮件"""
        app = current_app._get_current_object()
        reset_url = f"{app.config.get('PUBLIC_BASE_URL', 'http://localhost:5001')}/public/reset-password?email={user.email}&token={token}"
        subject = '重置您的密码 - 内容生成平台'
        body = f'''您收到这封邮件是因为您请求重置密码。

点击下面的链接重置密码：
{reset_url}

链接 {cls.RESET_TOKEN_EXPIRES} 小时内有效。

如果您没有请求重置密码，请忽略此邮件。
'''
        EmailService.send_email(user.email, subject, body)


# 全局实例
auth_service = AuthService()
