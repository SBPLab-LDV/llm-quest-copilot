"""
DSPy 退化監控系統 (DSPy Degradation Monitor)

這個模組實現了實時對話品質監控和退化預警系統，用於檢測和預防 DSPy 對話模組的品質退化。

主要功能：
1. 實時品質評估：評估對話回應的品質和一致性
2. 退化模式識別：檢測自我介紹模式、通用回應等退化指標
3. 預警系統：基於品質閾值觸發退化預警
4. 品質指標計算：計算角色一致性、相關性等關鍵指標
5. 歷史趨勢分析：追蹤品質變化趨勢

Author: DSPy Analysis Team
Date: 2025-09-12
Version: 1.0.0
"""

import logging
import re
import statistics
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum


class DegradationRisk(Enum):
    """退化風險等級"""
    LOW = "low"
    MEDIUM = "medium"  
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class QualityMetrics:
    """品質指標數據類"""
    character_consistency_score: float
    response_relevance_score: float
    context_appropriateness_score: float
    self_introduction_detected: bool
    generic_response_detected: bool
    response_count_normal: bool
    reasoning_quality_score: float
    overall_quality_score: float
    risk_level: DegradationRisk


@dataclass
class DegradationPattern:
    """退化模式數據類"""
    pattern_name: str
    detection_confidence: float
    indicators: List[str]
    risk_contribution: float


class DegradationMonitor:
    """
    DSPy 退化監控系統主類
    
    負責監控對話品質、檢測退化模式、提供預警機制
    """
    
    def __init__(self, enable_logging: bool = True):
        """
        初始化退化監控系統
        
        Args:
            enable_logging: 是否啟用詳細日誌記錄
        """
        self.logger = logging.getLogger(__name__)
        self.enable_logging = enable_logging
        
        # 品質歷史記錄
        self.quality_history: List[QualityMetrics] = []
        self.degradation_events: List[Dict[str, Any]] = []
        
        # 退化檢測閾值
        self.thresholds = {
            'character_consistency': 0.7,
            'response_relevance': 0.6,
            'context_appropriateness': 0.6,
            'reasoning_quality': 0.5,
            'overall_quality': 0.6,
            'critical_round_start': 3  # 第3輪開始進入關鍵監控期
        }
        
        # 退化模式檢測規則
        self._init_degradation_patterns()
        
        if self.enable_logging:
            self.logger.info("🔍 DSPy 退化監控系統初始化完成")
    
    def _init_degradation_patterns(self):
        """初始化退化模式檢測規則"""
        self.degradation_patterns = {
            'self_introduction': {
                'patterns': [
                    r'您好，我是\w+',
                    r'我是\w+，\w+病患',
                    r'我是.*Patient_\d+',
                    r'您好.*我是.*病患'
                ],
                'risk_weight': 0.9,
                'description': '自我介紹模式'
            },
            'generic_response': {
                'patterns': [
                    r'我可能沒有完全理解您的問題',
                    r'能請您換個方式說明嗎',
                    r'您需要什麼幫助嗎',
                    r'抱歉.*沒法.*理解',
                    r'我理解您想了解'
                ],
                'risk_weight': 0.8,
                'description': '通用回應模式'
            },
            'context_confusion': {
                'patterns': [
                    r'一般問診對話',
                    r'不確定.*情境',
                    r'混亂.*狀態'
                ],
                'risk_weight': 0.7,
                'description': '情境混亂模式'
            },
            'role_inconsistency': {
                'patterns': [
                    r'助手.*模式',
                    r'AI.*系統',
                    r'忘記.*角色'
                ],
                'risk_weight': 0.8,
                'description': '角色不一致模式'
            }
        }
    
    def assess_dialogue_quality(self, response_data: Dict[str, Any], 
                              round_number: int, 
                              conversation_history: List[Dict] = None,
                              character_config: Dict[str, Any] = None) -> QualityMetrics:
        """
        評估對話品質
        
        Args:
            response_data: 對話回應數據
            round_number: 當前對話輪次
            conversation_history: 對話歷史
            character_config: 角色配置
            
        Returns:
            QualityMetrics: 品質評估結果
        """
        if self.enable_logging:
            self.logger.info(f"🔍 DEGRADATION MONITOR: 開始評估第 {round_number} 輪對話品質")
        
        try:
            # 提取回應內容
            responses = response_data.get('responses', [])
            dialogue_context = response_data.get('dialogue_context', '')
            reasoning = response_data.get('reasoning', '')
            state = response_data.get('state', 'NORMAL')
            
            # 計算各項品質指標
            character_consistency = self._calculate_character_consistency(
                responses, character_config, reasoning
            )
            
            response_relevance = self._calculate_response_relevance(
                responses, dialogue_context, conversation_history
            )
            
            context_appropriateness = self._calculate_context_appropriateness(
                dialogue_context, round_number
            )
            
            reasoning_quality = self._calculate_reasoning_quality(reasoning)
            
            # 檢測退化模式
            self_intro_detected = self._detect_self_introduction(responses)
            generic_detected = self._detect_generic_response(responses)
            count_normal = len(responses) >= 3  # 正常應該有3-5個回應選項
            
            # 計算總體品質分數
            overall_quality = self._calculate_overall_quality_score(
                character_consistency, response_relevance, context_appropriateness,
                reasoning_quality, self_intro_detected, generic_detected, count_normal
            )
            
            # 評估風險等級
            risk_level = self._assess_risk_level(
                overall_quality, round_number, self_intro_detected, generic_detected
            )
            
            # 建立品質指標對象
            metrics = QualityMetrics(
                character_consistency_score=character_consistency,
                response_relevance_score=response_relevance,
                context_appropriateness_score=context_appropriateness,
                self_introduction_detected=self_intro_detected,
                generic_response_detected=generic_detected,
                response_count_normal=count_normal,
                reasoning_quality_score=reasoning_quality,
                overall_quality_score=overall_quality,
                risk_level=risk_level
            )
            
            # 記錄品質歷史
            self.quality_history.append(metrics)
            
            # 記錄詳細日誌
            if self.enable_logging:
                self._log_quality_assessment(metrics, round_number)
            
            # 檢查是否需要觸發預警
            self._check_degradation_warning(metrics, round_number)
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"❌ DEGRADATION MONITOR: 品質評估錯誤: {str(e)}")
            # 返回低品質指標作為安全措施
            return QualityMetrics(
                character_consistency_score=0.0,
                response_relevance_score=0.0,
                context_appropriateness_score=0.0,
                self_introduction_detected=True,
                generic_response_detected=True,
                response_count_normal=False,
                reasoning_quality_score=0.0,
                overall_quality_score=0.0,
                risk_level=DegradationRisk.CRITICAL
            )
    
    def _calculate_character_consistency(self, responses: List[str], 
                                       character_config: Dict[str, Any], 
                                       reasoning: str) -> float:
        """計算角色一致性分數"""
        if not responses or not character_config:
            return 0.5
        
        try:
            score = 0.8  # 基礎分數
            
            # 檢查是否包含角色名稱但非自我介紹形式
            character_name = character_config.get('name', '')
            if character_name:
                for response in responses:
                    if character_name in response:
                        # 如果是自我介紹形式，扣分
                        if re.search(r'我是.*' + character_name, response):
                            score -= 0.3
                        else:
                            score += 0.1
            
            # 檢查推理中的角色意識
            if reasoning and '角色' in reasoning:
                score += 0.1
            
            # 檢查是否維持病患身份
            patient_indicators = ['病患', '手術', '治療', '醫師', '檢查']
            for response in responses:
                if any(indicator in response for indicator in patient_indicators):
                    score += 0.05
            
            return min(max(score, 0.0), 1.0)
            
        except Exception as e:
            self.logger.error(f"角色一致性計算錯誤: {str(e)}")
            return 0.5
    
    def _calculate_response_relevance(self, responses: List[str], 
                                    dialogue_context: str,
                                    conversation_history: List[Dict] = None) -> float:
        """計算回應相關性分數"""
        if not responses:
            return 0.0
        
        try:
            score = 0.7  # 基礎分數
            
            # 檢查對話情境相關性
            if dialogue_context:
                context_keywords = {
                    '醫師查房': ['查房', '醫師', '身體', '狀況'],
                    '身體評估': ['評估', '症狀', '感覺', '不舒服'],
                    '檢查相關': ['檢查', '安排', '準備', '配合']
                }
                
                for context_type, keywords in context_keywords.items():
                    if context_type in dialogue_context:
                        for response in responses:
                            if any(keyword in response for keyword in keywords):
                                score += 0.1
                        break
            
            # 檢查是否有具體醫療相關回應
            medical_terms = ['手術', '傷口', '腫脹', '疼痛', '治療', '康復']
            for response in responses:
                if any(term in response for term in medical_terms):
                    score += 0.05
            
            return min(max(score, 0.0), 1.0)
            
        except Exception as e:
            self.logger.error(f"回應相關性計算錯誤: {str(e)}")
            return 0.5
    
    def _calculate_context_appropriateness(self, dialogue_context: str, round_number: int) -> float:
        """計算情境適切性分數"""
        try:
            score = 0.8  # 基礎分數
            
            # 檢查是否退化為通用情境
            if '一般問診對話' in dialogue_context:
                score -= 0.4
            
            # 檢查情境是否與輪次相符
            expected_contexts = {
                1: ['醫師查房', '初次接觸'],
                2: ['身體評估', '症狀詢問'],
                3: ['身體評估', '詳細評估'],
                4: ['症狀評估', '醫師查房'],
                5: ['檢查相關', '治療安排']
            }
            
            if round_number in expected_contexts:
                expected = expected_contexts[round_number]
                if any(context in dialogue_context for context in expected):
                    score += 0.1
                else:
                    score -= 0.2
            
            return min(max(score, 0.0), 1.0)
            
        except Exception as e:
            self.logger.error(f"情境適切性計算錯誤: {str(e)}")
            return 0.5
    
    def _calculate_reasoning_quality(self, reasoning: str) -> float:
        """計算推理品質分數"""
        if not reasoning:
            return 0.3
        
        try:
            score = 0.5  # 基礎分數
            
            # 檢查推理長度（過短可能是退化）
            if len(reasoning) > 100:
                score += 0.2
            elif len(reasoning) < 30:
                score -= 0.3
            
            # 檢查推理內容品質
            quality_indicators = [
                '角色', '病患', '醫療', '情境', '症狀', 
                '評估', '分析', '考慮', '根據'
            ]
            
            for indicator in quality_indicators:
                if indicator in reasoning:
                    score += 0.05
            
            # 檢查是否有系統性思考
            reasoning_patterns = [
                r'考慮到.*情況',
                r'基於.*分析',
                r'從.*角度'
            ]
            
            for pattern in reasoning_patterns:
                if re.search(pattern, reasoning):
                    score += 0.1
            
            return min(max(score, 0.0), 1.0)
            
        except Exception as e:
            self.logger.error(f"推理品質計算錯誤: {str(e)}")
            return 0.3
    
    def _detect_self_introduction(self, responses: List[str]) -> bool:
        """檢測自我介紹模式"""
        if not responses:
            return False
        
        patterns = self.degradation_patterns['self_introduction']['patterns']
        
        for response in responses:
            for pattern in patterns:
                if re.search(pattern, response):
                    return True
        
        return False
    
    def _detect_generic_response(self, responses: List[str]) -> bool:
        """檢測通用回應模式"""
        if not responses:
            return False
        
        patterns = self.degradation_patterns['generic_response']['patterns']
        
        for response in responses:
            for pattern in patterns:
                if re.search(pattern, response):
                    return True
        
        return False
    
    def _calculate_overall_quality_score(self, character_consistency: float,
                                       response_relevance: float,
                                       context_appropriateness: float,
                                       reasoning_quality: float,
                                       self_intro_detected: bool,
                                       generic_detected: bool,
                                       count_normal: bool) -> float:
        """計算總體品質分數"""
        try:
            # 基礎品質分數（加權平均）
            base_score = (
                character_consistency * 0.3 +
                response_relevance * 0.25 +
                context_appropriateness * 0.25 +
                reasoning_quality * 0.2
            )
            
            # 退化模式懲罰
            if self_intro_detected:
                base_score -= 0.4
            
            if generic_detected:
                base_score -= 0.3
            
            if not count_normal:
                base_score -= 0.2
            
            return min(max(base_score, 0.0), 1.0)
            
        except Exception as e:
            self.logger.error(f"總體品質分數計算錯誤: {str(e)}")
            return 0.0
    
    def _assess_risk_level(self, overall_quality: float, 
                          round_number: int,
                          self_intro_detected: bool,
                          generic_detected: bool) -> DegradationRisk:
        """評估退化風險等級"""
        try:
            # 關鍵輪次（3-5輪）提高警戒
            is_critical_round = round_number >= self.thresholds['critical_round_start']
            
            # 嚴重退化指標
            if self_intro_detected or generic_detected:
                return DegradationRisk.CRITICAL
            
            # 根據品質分數判斷
            if overall_quality >= 0.8:
                return DegradationRisk.LOW
            elif overall_quality >= 0.6:
                return DegradationRisk.MEDIUM if is_critical_round else DegradationRisk.LOW
            elif overall_quality >= 0.4:
                return DegradationRisk.HIGH if is_critical_round else DegradationRisk.MEDIUM
            else:
                return DegradationRisk.CRITICAL
                
        except Exception as e:
            self.logger.error(f"風險等級評估錯誤: {str(e)}")
            return DegradationRisk.CRITICAL
    
    def _log_quality_assessment(self, metrics: QualityMetrics, round_number: int):
        """記錄品質評估詳細日誌"""
        self.logger.info(f"📊 QUALITY ASSESSMENT - Round {round_number}")
        self.logger.info(f"  🎯 Overall Quality: {metrics.overall_quality_score:.3f}")
        self.logger.info(f"  👤 Character Consistency: {metrics.character_consistency_score:.3f}")
        self.logger.info(f"  🎪 Response Relevance: {metrics.response_relevance_score:.3f}")
        self.logger.info(f"  🌍 Context Appropriateness: {metrics.context_appropriateness_score:.3f}")
        self.logger.info(f"  🧠 Reasoning Quality: {metrics.reasoning_quality_score:.3f}")
        self.logger.info(f"  🚨 Self Introduction: {metrics.self_introduction_detected}")
        self.logger.info(f"  🤖 Generic Response: {metrics.generic_response_detected}")
        self.logger.info(f"  📝 Response Count Normal: {metrics.response_count_normal}")
        self.logger.info(f"  ⚠️ Risk Level: {metrics.risk_level.value.upper()}")
    
    def _check_degradation_warning(self, metrics: QualityMetrics, round_number: int):
        """檢查是否需要觸發退化預警"""
        if metrics.risk_level in [DegradationRisk.HIGH, DegradationRisk.CRITICAL]:
            warning_event = {
                'timestamp': datetime.now().isoformat(),
                'round_number': round_number,
                'risk_level': metrics.risk_level.value,
                'quality_score': metrics.overall_quality_score,
                'degradation_indicators': []
            }
            
            if metrics.self_introduction_detected:
                warning_event['degradation_indicators'].append('self_introduction')
            
            if metrics.generic_response_detected:
                warning_event['degradation_indicators'].append('generic_response')
            
            if not metrics.response_count_normal:
                warning_event['degradation_indicators'].append('abnormal_response_count')
            
            self.degradation_events.append(warning_event)
            
            # 發出預警日誌
            self.logger.warning(f"🚨 DEGRADATION WARNING - Round {round_number}")
            self.logger.warning(f"  ⚠️ Risk Level: {metrics.risk_level.value.upper()}")
            self.logger.warning(f"  📊 Quality Score: {metrics.overall_quality_score:.3f}")
            self.logger.warning(f"  🔍 Indicators: {warning_event['degradation_indicators']}")
    
    def get_quality_trend_analysis(self, window_size: int = 3) -> Dict[str, Any]:
        """獲取品質趨勢分析"""
        if len(self.quality_history) < 2:
            return {
                'trend': 'insufficient_data',
                'average_quality': 0.0,
                'quality_variance': 0.0,
                'degradation_risk_trend': 'unknown'
            }
        
        try:
            recent_scores = [m.overall_quality_score for m in self.quality_history[-window_size:]]
            
            # 計算趋勢
            if len(recent_scores) >= 2:
                trend = 'improving' if recent_scores[-1] > recent_scores[-2] else 'declining'
            else:
                trend = 'stable'
            
            # 計算統計值
            avg_quality = statistics.mean(recent_scores)
            quality_variance = statistics.variance(recent_scores) if len(recent_scores) > 1 else 0.0
            
            # 風險趨勢
            recent_risks = [m.risk_level for m in self.quality_history[-window_size:]]
            risk_values = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
            risk_trend = 'stable'
            
            if len(recent_risks) >= 2:
                recent_risk_values = [risk_values[r.value] for r in recent_risks]
                if recent_risk_values[-1] > recent_risk_values[-2]:
                    risk_trend = 'increasing'
                elif recent_risk_values[-1] < recent_risk_values[-2]:
                    risk_trend = 'decreasing'
            
            return {
                'trend': trend,
                'average_quality': avg_quality,
                'quality_variance': quality_variance,
                'degradation_risk_trend': risk_trend,
                'recent_scores': recent_scores,
                'total_assessments': len(self.quality_history),
                'degradation_events_count': len(self.degradation_events)
            }
            
        except Exception as e:
            self.logger.error(f"品質趨勢分析錯誤: {str(e)}")
            return {'error': str(e)}
    
    def reset_monitoring_state(self):
        """重置監控狀態（用於新對話開始）"""
        self.quality_history.clear()
        self.degradation_events.clear()
        
        if self.enable_logging:
            self.logger.info("🔄 DEGRADATION MONITOR: 監控狀態已重置")
    
    def get_monitoring_summary(self) -> Dict[str, Any]:
        """獲取監控摘要報告"""
        if not self.quality_history:
            return {
                'total_assessments': 0,
                'degradation_events': 0,
                'current_quality': 0.0,
                'status': 'no_data'
            }
        
        latest_metrics = self.quality_history[-1]
        trend_analysis = self.get_quality_trend_analysis()
        
        return {
            'total_assessments': len(self.quality_history),
            'degradation_events': len(self.degradation_events),
            'current_quality': latest_metrics.overall_quality_score,
            'current_risk_level': latest_metrics.risk_level.value,
            'quality_trend': trend_analysis.get('trend', 'unknown'),
            'average_quality': trend_analysis.get('average_quality', 0.0),
            'degradation_indicators': {
                'self_introduction_detected': latest_metrics.self_introduction_detected,
                'generic_response_detected': latest_metrics.generic_response_detected,
                'response_count_normal': latest_metrics.response_count_normal
            },
            'status': 'active'
        }


# 創建全局監控實例
degradation_monitor = DegradationMonitor()


def assess_dialogue_quality_quick(response_data: Dict[str, Any], round_number: int) -> float:
    """
    快速品質評估函數（用於簡單檢查）
    
    Args:
        response_data: 對話回應數據
        round_number: 對話輪次
        
    Returns:
        float: 品質分數 (0-1)
    """
    metrics = degradation_monitor.assess_dialogue_quality(response_data, round_number)
    return metrics.overall_quality_score


def is_degradation_risk_high(response_data: Dict[str, Any], round_number: int) -> bool:
    """
    檢查是否存在高退化風險
    
    Args:
        response_data: 對話回應數據
        round_number: 對話輪次
        
    Returns:
        bool: 是否為高風險
    """
    metrics = degradation_monitor.assess_dialogue_quality(response_data, round_number)
    return metrics.risk_level in [DegradationRisk.HIGH, DegradationRisk.CRITICAL]


if __name__ == "__main__":
    # 測試用例
    print("🔍 DSPy 退化監控系統測試")
    
    # 模擬正常回應
    normal_response = {
        'responses': [
            '手術後感覺還好，就是有點腫。',
            '傷口癒合得不錯，但還有點緊。',
            '吃東西時還是有點困難。',
            '醫師說恢復得很順利。',
            '沒有特別的不適感。'
        ],
        'dialogue_context': '醫師查房',
        'reasoning': '考慮到病患是口腔癌術後，應該提供相關的身體狀況回應。',
        'state': 'NORMAL'
    }
    
    # 模擬退化回應
    degraded_response = {
        'responses': ['您好，我是Patient_1，口腔癌病患。您需要什麼幫助嗎？'],
        'dialogue_context': '一般問診對話',
        'reasoning': '提供幫助',
        'state': 'CONFUSED'
    }
    
    monitor = DegradationMonitor(enable_logging=True)
    
    print("\n--- 正常回應測試 ---")
    normal_metrics = monitor.assess_dialogue_quality(normal_response, 2)
    print(f"品質分數: {normal_metrics.overall_quality_score:.3f}")
    print(f"風險等級: {normal_metrics.risk_level.value}")
    
    print("\n--- 退化回應測試 ---")
    degraded_metrics = monitor.assess_dialogue_quality(degraded_response, 4)
    print(f"品質分數: {degraded_metrics.overall_quality_score:.3f}")
    print(f"風險等級: {degraded_metrics.risk_level.value}")
    
    print("\n--- 監控摘要 ---")
    summary = monitor.get_monitoring_summary()
    for key, value in summary.items():
        print(f"{key}: {value}")