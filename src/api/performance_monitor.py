"""
API 性能監控和統計模組

用於追蹤 DSPy 和原始實現的性能指標、使用統計和錯誤率。
"""

import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
import threading

logger = logging.getLogger(__name__)

@dataclass
class RequestMetrics:
    """單次請求的性能指標"""
    implementation: str  # "dspy" or "original"
    endpoint: str       # API 端點名稱
    start_time: float
    end_time: float
    success: bool
    error_message: Optional[str] = None
    response_length: int = 0
    character_id: str = ""
    session_id: str = ""

    @property
    def duration(self) -> float:
        """請求持續時間（秒）"""
        return self.end_time - self.start_time

    @property
    def timestamp(self) -> datetime:
        """請求時間戳"""
        return datetime.fromtimestamp(self.start_time)

@dataclass
class AggregatedMetrics:
    """聚合的性能指標"""
    implementation: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_duration: float
    avg_response_time: float
    error_rate: float
    last_updated: datetime

class PerformanceMonitor:
    """性能監控器"""
    
    def __init__(self, max_history: int = 10000):
        """
        初始化性能監控器
        
        Args:
            max_history: 最多保存的歷史記錄數量
        """
        self.max_history = max_history
        self.request_history: deque = deque(maxlen=max_history)
        self.lock = threading.Lock()
        
        # 實時統計計數器
        self.stats = {
            "dspy": {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "total_duration": 0.0,
                "recent_errors": deque(maxlen=100)  # 最近的錯誤記錄
            },
            "original": {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "total_duration": 0.0,
                "recent_errors": deque(maxlen=100)
            }
        }
        
        logger.info(f"性能監控器初始化，最大歷史記錄數: {max_history}")
    
    def start_request(self, implementation: str, endpoint: str, 
                     character_id: str = "", session_id: str = "") -> Dict[str, Any]:
        """
        開始一次請求的監控
        
        Args:
            implementation: 實現類型 ("dspy" or "original")
            endpoint: API 端點
            character_id: 角色ID
            session_id: 會話ID
            
        Returns:
            請求上下文，用於 end_request
        """
        return {
            "implementation": implementation,
            "endpoint": endpoint,
            "character_id": character_id,
            "session_id": session_id,
            "start_time": time.time()
        }
    
    def end_request(self, context: Dict[str, Any], success: bool, 
                   error_message: Optional[str] = None, 
                   response_length: int = 0) -> RequestMetrics:
        """
        結束一次請求的監控
        
        Args:
            context: start_request 返回的上下文
            success: 請求是否成功
            error_message: 錯誤訊息（如果有）
            response_length: 回應長度
            
        Returns:
            請求指標對象
        """
        end_time = time.time()
        
        metrics = RequestMetrics(
            implementation=context["implementation"],
            endpoint=context["endpoint"],
            start_time=context["start_time"],
            end_time=end_time,
            success=success,
            error_message=error_message,
            response_length=response_length,
            character_id=context.get("character_id", ""),
            session_id=context.get("session_id", "")
        )
        
        self._record_metrics(metrics)
        return metrics
    
    def _record_metrics(self, metrics: RequestMetrics):
        """記錄指標到統計中"""
        with self.lock:
            # 添加到歷史記錄
            self.request_history.append(metrics)
            
            # 更新實時統計
            impl_stats = self.stats[metrics.implementation]
            impl_stats["total_requests"] += 1
            impl_stats["total_duration"] += metrics.duration
            
            if metrics.success:
                impl_stats["successful_requests"] += 1
            else:
                impl_stats["failed_requests"] += 1
                if metrics.error_message:
                    impl_stats["recent_errors"].append({
                        "timestamp": metrics.timestamp,
                        "endpoint": metrics.endpoint,
                        "error": metrics.error_message,
                        "character_id": metrics.character_id
                    })
            
            logger.debug(f"記錄指標: {metrics.implementation} - {metrics.endpoint}, "
                        f"成功: {metrics.success}, 耗時: {metrics.duration:.2f}s")
    
    def get_current_stats(self) -> Dict[str, AggregatedMetrics]:
        """獲取當前統計數據"""
        with self.lock:
            result = {}
            
            for impl_name, stats in self.stats.items():
                total_requests = stats["total_requests"]
                
                if total_requests > 0:
                    avg_response_time = stats["total_duration"] / total_requests
                    error_rate = stats["failed_requests"] / total_requests
                else:
                    avg_response_time = 0.0
                    error_rate = 0.0
                
                result[impl_name] = AggregatedMetrics(
                    implementation=impl_name,
                    total_requests=total_requests,
                    successful_requests=stats["successful_requests"],
                    failed_requests=stats["failed_requests"],
                    total_duration=stats["total_duration"],
                    avg_response_time=avg_response_time,
                    error_rate=error_rate,
                    last_updated=datetime.now()
                )
            
            return result
    
    def get_recent_history(self, minutes: int = 60) -> List[RequestMetrics]:
        """
        獲取最近一段時間的請求歷史
        
        Args:
            minutes: 時間範圍（分鐘）
            
        Returns:
            最近的請求指標列表
        """
        cutoff_time = time.time() - (minutes * 60)
        
        with self.lock:
            return [
                metrics for metrics in self.request_history 
                if metrics.start_time >= cutoff_time
            ]
    
    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        獲取錯誤摘要
        
        Args:
            hours: 時間範圍（小時）
            
        Returns:
            錯誤統計摘要
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self.lock:
            error_summary = {
                "dspy": {"total": 0, "by_endpoint": defaultdict(int), "recent_errors": []},
                "original": {"total": 0, "by_endpoint": defaultdict(int), "recent_errors": []}
            }
            
            for impl_name, stats in self.stats.items():
                recent_errors = [
                    error for error in stats["recent_errors"] 
                    if error["timestamp"] >= cutoff_time
                ]
                
                error_summary[impl_name]["total"] = len(recent_errors)
                error_summary[impl_name]["recent_errors"] = recent_errors
                
                for error in recent_errors:
                    error_summary[impl_name]["by_endpoint"][error["endpoint"]] += 1
            
            return error_summary
    
    def get_comparison_report(self) -> Dict[str, Any]:
        """獲取 DSPy vs 原始實現的對比報告"""
        stats = self.get_current_stats()
        
        if "dspy" not in stats or "original" not in stats:
            return {"error": "需要兩種實現都有數據才能對比"}
        
        dspy_stats = stats["dspy"]
        original_stats = stats["original"]
        
        # 計算改進比例
        def calculate_improvement(dspy_val, original_val, lower_is_better=True):
            if original_val == 0:
                return None
            
            improvement = (original_val - dspy_val) / original_val * 100
            return improvement if lower_is_better else -improvement
        
        response_time_improvement = calculate_improvement(
            dspy_stats.avg_response_time,
            original_stats.avg_response_time,
            lower_is_better=True
        )
        
        error_rate_improvement = calculate_improvement(
            dspy_stats.error_rate,
            original_stats.error_rate,
            lower_is_better=True
        )
        
        return {
            "comparison_time": datetime.now(),
            "dspy": asdict(dspy_stats),
            "original": asdict(original_stats),
            "improvements": {
                "response_time_improvement_percent": response_time_improvement,
                "error_rate_improvement_percent": error_rate_improvement
            },
            "summary": {
                "total_requests": dspy_stats.total_requests + original_stats.total_requests,
                "dspy_usage_percent": (
                    dspy_stats.total_requests / 
                    (dspy_stats.total_requests + original_stats.total_requests) * 100
                    if (dspy_stats.total_requests + original_stats.total_requests) > 0
                    else 0
                )
            }
        }
    
    def reset_stats(self):
        """重置統計數據"""
        with self.lock:
            self.request_history.clear()
            for impl_stats in self.stats.values():
                impl_stats["total_requests"] = 0
                impl_stats["successful_requests"] = 0
                impl_stats["failed_requests"] = 0
                impl_stats["total_duration"] = 0.0
                impl_stats["recent_errors"].clear()
            
            logger.info("性能監控統計數據已重置")

# 全局性能監控器實例
performance_monitor = PerformanceMonitor()

def get_performance_monitor() -> PerformanceMonitor:
    """獲取全局性能監控器實例"""
    return performance_monitor