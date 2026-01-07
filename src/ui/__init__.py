"""
醫護對話系統 v0.3.2 UI 模組

提供基於 Gradio 的網頁介面，用於與對話系統 API 交互
"""

from .app import create_app, DialogueApp
from .client import ApiClient

__all__ = ['create_app', 'DialogueApp', 'ApiClient'] 