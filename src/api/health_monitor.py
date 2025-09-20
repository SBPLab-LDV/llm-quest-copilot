"""
健康監控和自動回退機制

監控 DSPy 實現的健康狀況，在必要時自動回退到原始實現。
"""

import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass
import threading
import yaml
import os

logger = logging.getLogger(__name__)

@dataclass
class HealthStatus:
    """健康狀態"""
    implementation: str
    is_healthy: bool
    error_rate: float
    avg_response_time: float
    recent_errors: int
    last_check: datetime
    issues: List[str]

class HealthMonitor:
    """健康監控器"""
    
    def __init__(self, config_path: str = None):
        """
        初始化健康監控器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path or "/app/config/config.yaml"
        self.lock = threading.Lock()
        
        # 健康檢查閾值（可配置）
        self.thresholds = {
            "max_error_rate": 0.20,  # 20% 錯誤率閾值
            "max_response_time": 10.0,  # 10秒響應時間閾值
            "max_recent_errors": 5,  # 最近5個錯誤的閾值
            "check_interval": 60,  # 檢查間隔（秒）
            "recovery_time": 300  # 恢復等待時間（秒）
        }
        
        # 狀態追蹤
        self.last_check_time = 0
        self.fallback_enabled = False
        self.fallback_start_time = None
        self.health_history = deque(maxlen=100)
        
        logger.info("健康監控器初始化完成")
    
    def check_health(self, performance_monitor) -> Dict[str, HealthStatus]:
        """
        檢查實現的健康狀況
        
        Args:
            performance_monitor: 性能監控器實例
            
        Returns:
            各實現的健康狀況
        """
        current_time = time.time()
        
        # 檢查是否需要執行健康檢查
        if current_time - self.last_check_time < self.thresholds["check_interval"]:
            return self._get_cached_health_status()
        
        self.last_check_time = current_time
        
        # 獲取性能統計
        current_stats = performance_monitor.get_current_stats()
        error_summary = performance_monitor.get_error_summary(hours=1)
        
        health_statuses = {}
        
        for impl_name in ["dspy", "original"]:
            issues = []
            is_healthy = True
            
            if impl_name in current_stats:
                stats = current_stats[impl_name]
                
                # 檢查錯誤率
                if stats.error_rate > self.thresholds["max_error_rate"]:
                    issues.append(f"錯誤率過高: {stats.error_rate:.1%}")
                    is_healthy = False
                
                # 檢查響應時間
                if stats.avg_response_time > self.thresholds["max_response_time"]:
                    issues.append(f"響應時間過長: {stats.avg_response_time:.2f}s")
                    is_healthy = False
                
                # 檢查最近錯誤
                recent_errors = error_summary.get(impl_name, {}).get("total", 0)
                if recent_errors > self.thresholds["max_recent_errors"]:
                    issues.append(f"最近錯誤過多: {recent_errors} 個")
                    is_healthy = False
                
                health_status = HealthStatus(
                    implementation=impl_name,
                    is_healthy=is_healthy,
                    error_rate=stats.error_rate,
                    avg_response_time=stats.avg_response_time,
                    recent_errors=recent_errors,
                    last_check=datetime.now(),
                    issues=issues
                )
            else:
                # 沒有統計數據，假設不健康
                health_status = HealthStatus(
                    implementation=impl_name,
                    is_healthy=False,
                    error_rate=1.0,
                    avg_response_time=0.0,
                    recent_errors=0,
                    last_check=datetime.now(),
                    issues=["無統計數據"]
                )
            
            health_statuses[impl_name] = health_status
        
        # 記錄健康狀況
        with self.lock:
            self.health_history.append({
                "timestamp": datetime.now(),
                "statuses": health_statuses
            })
        
        # 檢查是否需要觸發自動回退
        self._evaluate_fallback(health_statuses)
        
        return health_statuses
    
    def _get_cached_health_status(self) -> Dict[str, HealthStatus]:
        """獲取緩存的健康狀況"""
        with self.lock:
            if self.health_history:
                return self.health_history[-1]["statuses"]
            else:
                # 返回默認狀態
                return {
                    "dspy": HealthStatus("dspy", True, 0.0, 0.0, 0, datetime.now(), []),
                    "original": HealthStatus("original", True, 0.0, 0.0, 0, datetime.now(), [])
                }
    
    def _evaluate_fallback(self, health_statuses: Dict[str, HealthStatus]):
        """
        評估是否需要觸發自動回退
        
        Args:
            health_statuses: 當前健康狀況
        """
        dspy_status = health_statuses.get("dspy")
        original_status = health_statuses.get("original")
        
        # 如果 DSPy 不健康但原始實現健康，觸發回退
        if (dspy_status and not dspy_status.is_healthy and 
            original_status and original_status.is_healthy):
            
            if not self.fallback_enabled:
                logger.warning("DSPy 實現不健康，觸發自動回退到原始實現")
                logger.warning(f"DSPy 問題: {', '.join(dspy_status.issues)}")
                self._enable_fallback()
        
        # 如果回退已啟用，檢查是否可以恢復
        elif self.fallback_enabled and dspy_status and dspy_status.is_healthy:
            if (self.fallback_start_time and 
                time.time() - self.fallback_start_time > self.thresholds["recovery_time"]):
                logger.info("DSPy 實現已恢復健康，停用自動回退")
                self._disable_fallback()
    
    def _enable_fallback(self):
        """啟用回退機制"""
        with self.lock:
            self.fallback_enabled = True
            self.fallback_start_time = time.time()
        
        # 更新配置文件，禁用 DSPy
        self._update_config(dspy_enabled=False, reason="自動回退")
    
    def _disable_fallback(self):
        """停用回退機制"""
        with self.lock:
            self.fallback_enabled = False
            self.fallback_start_time = None
        
        # 更新配置文件，啟用 DSPy
        self._update_config(dspy_enabled=True, reason="自動恢復")
    
    def _update_config(self, dspy_enabled: bool, reason: str):
        """
        更新配置文件
        
        Args:
            dspy_enabled: 是否啟用 DSPy
            reason: 修改原因
        """
        try:
            # 讀取當前配置
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 更新 DSPy 配置
            if 'dspy' not in config:
                config['dspy'] = {}
            
            config['dspy']['enabled'] = dspy_enabled
            config['dspy']['auto_fallback_reason'] = reason
            config['dspy']['last_auto_change'] = datetime.now().isoformat()
            
            # 寫回配置文件
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
            
            logger.info(f"配置已更新: DSPy enabled={dspy_enabled}, 原因={reason}")
            
        except Exception as e:
            logger.error(f"更新配置文件失敗: {e}")
    
    def manual_fallback(self, enable: bool, reason: str = "手動操作") -> bool:
        """
        手動觸發或停用回退
        
        Args:
            enable: True 啟用回退，False 停用回退
            reason: 操作原因
            
        Returns:
            操作是否成功
        """
        try:
            if enable:
                logger.info(f"手動啟用回退: {reason}")
                self._enable_fallback()
            else:
                logger.info(f"手動停用回退: {reason}")
                self._disable_fallback()
            
            return True
        except Exception as e:
            logger.error(f"手動回退操作失敗: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """獲取健康監控狀態"""
        with self.lock:
            return {
                "fallback_enabled": self.fallback_enabled,
                "fallback_start_time": (
                    datetime.fromtimestamp(self.fallback_start_time).isoformat()
                    if self.fallback_start_time else None
                ),
                "last_check_time": (
                    datetime.fromtimestamp(self.last_check_time).isoformat()
                    if self.last_check_time else None
                ),
                "thresholds": self.thresholds,
                "recent_health_checks": len(self.health_history)
            }
    
    def update_thresholds(self, new_thresholds: Dict[str, float]) -> bool:
        """
        更新健康檢查閾值
        
        Args:
            new_thresholds: 新的閾值設置
            
        Returns:
            更新是否成功
        """
        try:
            with self.lock:
                for key, value in new_thresholds.items():
                    if key in self.thresholds:
                        self.thresholds[key] = value
            
            logger.info(f"健康檢查閾值已更新: {new_thresholds}")
            return True
        except Exception as e:
            logger.error(f"更新閾值失敗: {e}")
            return False

# 全局健康監控器實例
health_monitor = HealthMonitor()

def get_health_monitor() -> HealthMonitor:
    """獲取全局健康監控器實例"""
    return health_monitor