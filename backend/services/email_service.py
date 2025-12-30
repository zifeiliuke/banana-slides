"""
Email Service - handles sending emails via SMTP
"""
import smtplib
import logging
import socket
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import Optional

logger = logging.getLogger(__name__)


class EmailService:
    """邮件发送服务"""

    def __init__(self, host: str, port: int, user: str, password: str,
                 use_ssl: bool = True, sender_name: str = 'Banana Slides'):
        """
        初始化邮件服务

        Args:
            host: SMTP服务器地址
            port: SMTP端口
            user: SMTP用户名（发件人邮箱）
            password: SMTP密码
            use_ssl: 是否使用SSL
            sender_name: 发件人名称
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.use_ssl = use_ssl
        self.sender_name = sender_name

    @classmethod
    def from_system_settings(cls):
        """从系统设置创建邮件服务实例"""
        from models import SystemSettings
        settings = SystemSettings.get_settings()

        if not settings.smtp_host or not settings.smtp_user or not settings.smtp_password:
            raise ValueError("SMTP配置不完整，请在管理后台配置邮件服务器")

        smtp_port = settings.smtp_port or 465
        # 常见的非SMTP端口（容易误填为 POP3/IMAP 等）
        if smtp_port in {110, 143, 993, 995}:
            raise ValueError(f"SMTP端口 {smtp_port} 看起来不是SMTP端口，请检查是否误填（常用SMTP端口：25/465/587）")

        return cls(
            host=settings.smtp_host,
            port=smtp_port,
            user=settings.smtp_user,
            password=settings.smtp_password,
            use_ssl=settings.smtp_use_ssl,
            sender_name=settings.smtp_sender_name or 'Banana Slides'
        )

    def _send_via_smtp(self, msg_as_string: str, to_email: str) -> None:
        """
        根据配置建立连接并发送邮件。

        约定：
        - use_ssl=True: 优先使用加密连接（465 用 SMTP_SSL；其他端口用 STARTTLS）
        - use_ssl=False: 明文 SMTP（不启用 STARTTLS）
        """
        if self.use_ssl:
            # 465：隐式 TLS；587/25：一般使用 STARTTLS
            if self.port == 465:
                with smtplib.SMTP_SSL(self.host, self.port, timeout=30) as server:
                    server.login(self.user, self.password)
                    server.sendmail(self.user, [to_email], msg_as_string)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=30) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(self.user, self.password)
                    server.sendmail(self.user, [to_email], msg_as_string)
        else:
            with smtplib.SMTP(self.host, self.port, timeout=30) as server:
                server.login(self.user, self.password)
                server.sendmail(self.user, [to_email], msg_as_string)

    def send_email(self, to_email: str, subject: str, html_content: str,
                   text_content: Optional[str] = None) -> tuple:
        """
        发送邮件

        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            html_content: HTML内容
            text_content: 纯文本内容（可选）

        Returns:
            (success: bool, message: str)
        """
        try:
            # 创建邮件
            msg = MIMEMultipart('alternative')
            msg['From'] = f'{self.sender_name} <{self.user}>'
            msg['To'] = to_email
            msg['Subject'] = Header(subject, 'utf-8')

            # 添加纯文本内容
            if text_content:
                text_part = MIMEText(text_content, 'plain', 'utf-8')
                msg.attach(text_part)

            # 添加HTML内容
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)

            # 发送邮件
            self._send_via_smtp(msg.as_string(), to_email)

            logger.info(f"Email sent successfully to {to_email}")
            return True, '邮件发送成功'

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return False, 'SMTP认证失败，请检查邮箱配置'

        except smtplib.SMTPServerDisconnected as e:
            logger.error(f"SMTP server disconnected unexpectedly: {e}")
            return False, (
                f'连接被服务器意外断开（{self.host}:{self.port}）。'
                '通常是端口/加密方式不匹配或服务器限制来源IP。'
                '请尝试：465+勾选加密；587+勾选加密；25+取消勾选（或按服务器要求勾选 STARTTLS）。'
            )

        except ssl.SSLError as e:
            logger.error(f"SMTP SSL error: {e}")
            return False, (
                f'TLS/SSL 握手失败（{self.host}:{self.port}）。'
                '请检查端口与加密方式是否匹配：465=SSL；587=STARTTLS；25=通常为明文/STARTTLS。'
            )

        except smtplib.SMTPNotSupportedError as e:
            logger.error(f"SMTP not supported: {e}")
            return False, f'邮件发送失败: {str(e)}'

        except smtplib.SMTPConnectError as e:
            logger.error(f"SMTP connect failed: {e}")
            return False, f'连接SMTP服务器失败: {str(e)}'

        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return False, f'邮件发送失败: {str(e)}'

        except (socket.gaierror, ConnectionRefusedError, TimeoutError) as e:
            logger.error(f"SMTP network error: {e}")
            return False, f'连接SMTP服务器失败: {str(e)}'

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False, f'邮件发送失败: {str(e)}'

    def send_verification_code(self, to_email: str, code: str) -> tuple:
        """
        发送验证码邮件

        Args:
            to_email: 收件人邮箱
            code: 6位验证码

        Returns:
            (success: bool, message: str)
        """
        subject = '【Banana Slides】邮箱验证码'

        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .header h1 {{ color: #333; margin: 0; font-size: 24px; }}
                .content {{ background: #fff; padding: 30px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 10px 10px; }}
                .code {{ font-size: 32px; font-weight: bold; color: #333; background: #f5f5f5; padding: 15px 30px; border-radius: 8px; display: inline-block; letter-spacing: 5px; margin: 20px 0; }}
                .note {{ color: #666; font-size: 14px; margin-top: 20px; }}
                .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🍌 Banana Slides</h1>
                </div>
                <div class="content">
                    <p>您好！</p>
                    <p>您正在注册 Banana Slides 账号，请使用以下验证码完成注册：</p>
                    <div style="text-align: center;">
                        <div class="code">{code}</div>
                    </div>
                    <p class="note">
                        ⏰ 验证码有效期为 10 分钟<br>
                        🔒 如果这不是您的操作，请忽略此邮件
                    </p>
                </div>
                <div class="footer">
                    <p>此邮件由系统自动发送，请勿回复</p>
                    <p>© Banana Slides - AI智能PPT生成</p>
                </div>
            </div>
        </body>
        </html>
        '''

        text_content = f'''
        Banana Slides 邮箱验证码

        您好！

        您正在注册 Banana Slides 账号，请使用以下验证码完成注册：

        验证码：{code}

        验证码有效期为 10 分钟。
        如果这不是您的操作，请忽略此邮件。

        © Banana Slides - AI智能PPT生成
        '''

        return self.send_email(to_email, subject, html_content, text_content)

    def send_referral_reward_notification(self, to_email: str, invitee_username: str,
                                          reward_days: int, reward_type: str) -> tuple:
        """
        发送邀请奖励通知邮件

        Args:
            to_email: 收件人邮箱
            invitee_username: 被邀请者用户名
            reward_days: 奖励天数
            reward_type: 奖励类型 ('register' | 'premium')

        Returns:
            (success: bool, message: str)
        """
        if reward_type == 'register':
            action = '完成了注册'
        else:
            action = '升级为高级会员'

        subject = f'【Banana Slides】恭喜获得 {reward_days} 天会员奖励！'

        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .header h1 {{ color: #333; margin: 0; font-size: 24px; }}
                .content {{ background: #fff; padding: 30px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 10px 10px; }}
                .reward {{ font-size: 48px; text-align: center; margin: 20px 0; }}
                .highlight {{ color: #FFA500; font-weight: bold; }}
                .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 恭喜获得邀请奖励！</h1>
                </div>
                <div class="content">
                    <div class="reward">🎁</div>
                    <p>您邀请的用户 <span class="highlight">{invitee_username}</span> {action}！</p>
                    <p>您已获得 <span class="highlight">{reward_days} 天</span> 高级会员时长奖励！</p>
                    <p>继续邀请更多好友，获取更多奖励吧！</p>
                </div>
                <div class="footer">
                    <p>© Banana Slides - AI智能PPT生成</p>
                </div>
            </div>
        </body>
        </html>
        '''

        return self.send_email(to_email, subject, html_content)


def get_email_service() -> EmailService:
    """获取邮件服务实例"""
    return EmailService.from_system_settings()
