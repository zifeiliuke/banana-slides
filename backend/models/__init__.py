"""Database models package"""
from flask_sqlalchemy import SQLAlchemy

# 创建 SQLAlchemy 实例
# 连接池配置从 Config.SQLALCHEMY_ENGINE_OPTIONS 加载
db = SQLAlchemy()

from .project import Project
from .page import Page
from .task import Task
from .user_template import UserTemplate
from .page_image_version import PageImageVersion
from .material import Material
from .reference_file import ReferenceFile
from .settings import Settings
from .user import User
from .user_settings import UserSettings
from .recharge_code import RechargeCode, PremiumHistory

__all__ = [
    'db',
    'Project',
    'Page',
    'Task',
    'UserTemplate',
    'PageImageVersion',
    'Material',
    'ReferenceFile',
    'Settings',
    'User',
    'UserSettings',
    'RechargeCode',
    'PremiumHistory',
]

