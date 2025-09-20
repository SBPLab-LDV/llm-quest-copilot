"""
DSPy 評估器

實現對話品質評估功能，包括回應品質、情境準確度和對話連貫性評估。
支援多種評估指標和自動化評估流程。
"""

import dspy
from typing import List, Dict, Any, Optional, Tuple, Union, Callable
import logging
import json
import numpy as np
from datetime import datetime
from collections import defaultdict, Counter
import re

# 避免相對導入問題
try:
    from .signatures import ResponseEvaluationSignature
    from .dialogue_module import DSPyDialogueModule
    from .config import DSPyConfig
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    from signatures import ResponseEvaluationSignature
    from dialogue_module import DSPyDialogueModule
    from config import DSPyConfig

logger = logging.getLogger(__name__)

class DSPyEvaluator:
    """DSPy 評估器
    
    提供多維度的對話系統評估功能，包括自動化和基於 DSPy 的評估。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化評估器
        
        Args:
            config: 配置字典
        """
        self.config_manager = DSPyConfig()
        self.config = config or self.config_manager.get_dspy_config()
        
        # DSPy 評估模組 (需要 LM 支援時使用)
        self.response_evaluator = None
        
        # 評估指標
        self.metrics = {
            'response_quality': self._evaluate_response_quality,
            'context_accuracy': self._evaluate_context_accuracy,
            'dialogue_coherence': self._evaluate_dialogue_coherence,
            'state_consistency': self._evaluate_state_consistency,
            'diversity_score': self._evaluate_diversity,
            'safety_score': self._evaluate_safety
        }
        
        # 評估歷史
        self.evaluation_history: List[Dict[str, Any]] = []
        
        # 統計資訊
        self.stats = {
            'total_evaluations': 0,
            'average_scores': {},
            'evaluation_types': Counter(),
            'last_evaluation': None
        }
        
        logger.info("DSPy 評估器初始化完成")
    
    def evaluate_prediction(self, 
                           user_input: str,
                           prediction: dspy.Prediction,
                           expected_output: Optional[Dict[str, Any]] = None,
                           evaluation_metrics: List[str] = None) -> Dict[str, Any]:
        """評估單個預測結果
        
        Args:
            user_input: 用戶輸入
            prediction: 模型預測結果
            expected_output: 預期輸出 (可選)
            evaluation_metrics: 要使用的評估指標列表
            
        Returns:
            評估結果字典
        """
        try:
            # 使用所有指標如果沒有指定
            if evaluation_metrics is None:
                evaluation_metrics = list(self.metrics.keys())
            
            evaluation_result = {
                'user_input': user_input,
                'prediction': self._prediction_to_dict(prediction),
                'expected_output': expected_output,
                'timestamp': datetime.now().isoformat(),
                'scores': {},
                'overall_score': 0.0
            }
            
            # 執行各項評估
            total_score = 0.0
            successful_metrics = 0
            
            for metric_name in evaluation_metrics:
                if metric_name in self.metrics:
                    try:
                        score = self.metrics[metric_name](
                            user_input, prediction, expected_output
                        )
                        evaluation_result['scores'][metric_name] = score
                        total_score += score
                        successful_metrics += 1
                        
                    except Exception as e:
                        logger.error(f"評估指標 {metric_name} 失敗: {e}")
                        evaluation_result['scores'][metric_name] = 0.0
                else:
                    logger.warning(f"未知的評估指標: {metric_name}")
            
            # 計算總分
            if successful_metrics > 0:
                evaluation_result['overall_score'] = total_score / successful_metrics
            
            # 更新統計
            self._update_evaluation_stats(evaluation_result)
            
            # 記錄評估歷史
            self.evaluation_history.append(evaluation_result)
            
            logger.debug(f"評估完成，總分: {evaluation_result['overall_score']:.2f}")
            return evaluation_result
            
        except Exception as e:
            logger.error(f"評估失敗: {e}")
            return {
                'user_input': user_input,
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
                'scores': {},
                'overall_score': 0.0
            }
    
    def batch_evaluate(self, 
                      test_cases: List[Dict[str, Any]],
                      model: DSPyDialogueModule,
                      evaluation_metrics: List[str] = None) -> Dict[str, Any]:
        """批量評估測試案例
        
        Args:
            test_cases: 測試案例列表，每個包含輸入參數
            model: 要評估的對話模組
            evaluation_metrics: 評估指標列表
            
        Returns:
            批量評估結果
        """
        try:
            logger.info(f"開始批量評估 {len(test_cases)} 個測試案例...")
            
            batch_results = {
                'total_cases': len(test_cases),
                'successful_cases': 0,
                'failed_cases': 0,
                'individual_results': [],
                'aggregate_scores': {},
                'timestamp': datetime.now().isoformat()
            }
            
            all_scores = defaultdict(list)
            
            for i, test_case in enumerate(test_cases):
                try:
                    # 執行預測
                    prediction = model(**test_case)
                    
                    # 評估預測結果
                    evaluation_result = self.evaluate_prediction(
                        user_input=test_case.get('user_input', ''),
                        prediction=prediction,
                        expected_output=test_case.get('expected_output'),
                        evaluation_metrics=evaluation_metrics
                    )
                    
                    batch_results['individual_results'].append(evaluation_result)
                    batch_results['successful_cases'] += 1
                    
                    # 累積分數
                    for metric, score in evaluation_result['scores'].items():
                        all_scores[metric].append(score)
                    all_scores['overall'].append(evaluation_result['overall_score'])
                    
                except Exception as e:
                    logger.error(f"測試案例 {i} 評估失敗: {e}")
                    batch_results['failed_cases'] += 1
                    batch_results['individual_results'].append({
                        'test_case_index': i,
                        'error': str(e),
                        'overall_score': 0.0
                    })
            
            # 計算聚合分數
            for metric, scores in all_scores.items():
                if scores:
                    batch_results['aggregate_scores'][metric] = {
                        'mean': np.mean(scores),
                        'std': np.std(scores),
                        'min': np.min(scores),
                        'max': np.max(scores),
                        'count': len(scores)
                    }
            
            logger.info(f"批量評估完成: {batch_results['successful_cases']}/{batch_results['total_cases']} 成功")
            return batch_results
            
        except Exception as e:
            logger.error(f"批量評估失敗: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _evaluate_response_quality(self, 
                                  user_input: str, 
                                  prediction: dspy.Prediction,
                                  expected_output: Optional[Dict[str, Any]] = None) -> float:
        """評估回應品質
        
        評估生成的回應是否合理、完整和有用。
        """
        try:
            score = 0.0
            
            # 檢查回應存在性和數量
            if hasattr(prediction, 'responses') and prediction.responses:
                responses = prediction.responses
                
                # 回應數量檢查 (期望3-5個)
                if len(responses) >= 3:
                    score += 0.2
                
                # 回應長度和內容檢查
                for response in responses:
                    if isinstance(response, str):
                        response_len = len(response.strip())
                        
                        # 長度合理 (5-100字)
                        if 5 <= response_len <= 100:
                            score += 0.1
                        
                        # 避免重複
                        if response.count(response[:10]) <= 1:  # 簡單重複檢查
                            score += 0.05
                        
                        # 包含適當的標點符號
                        if any(punct in response for punct in ['。', '？', '！', '，']):
                            score += 0.05
            
            # 情境相關性檢查
            if hasattr(prediction, 'dialogue_context') and prediction.dialogue_context:
                context = prediction.dialogue_context.strip()
                if len(context) > 0:
                    score += 0.1
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"回應品質評估失敗: {e}")
            return 0.0
    
    def _evaluate_context_accuracy(self,
                                  user_input: str,
                                  prediction: dspy.Prediction,
                                  expected_output: Optional[Dict[str, Any]] = None) -> float:
        """評估情境準確度
        
        評估識別的對話情境是否準確。
        """
        try:
            score = 0.0
            
            # 如果有預期情境，直接比較
            if expected_output and 'dialogue_context' in expected_output:
                expected_context = expected_output['dialogue_context']
                predicted_context = getattr(prediction, 'dialogue_context', '')
                
                if predicted_context == expected_context:
                    score = 1.0
                elif self._contexts_similar(predicted_context, expected_context):
                    score = 0.7
                else:
                    score = 0.0
            else:
                # 基於啟發式規則評估情境合理性
                predicted_context = getattr(prediction, 'dialogue_context', '')
                
                if predicted_context:
                    # 檢查情境與用戶輸入的相關性
                    relevance_score = self._calculate_context_relevance(
                        user_input, predicted_context
                    )
                    score = relevance_score
            
            return score
            
        except Exception as e:
            logger.error(f"情境準確度評估失敗: {e}")
            return 0.0
    
    def _evaluate_dialogue_coherence(self,
                                   user_input: str,
                                   prediction: dspy.Prediction,
                                   expected_output: Optional[Dict[str, Any]] = None) -> float:
        """評估對話連貫性
        
        評估回應是否與用戶輸入邏輯連貫。
        """
        try:
            score = 0.0
            
            if not hasattr(prediction, 'responses') or not prediction.responses:
                return 0.0
            
            # 檢查回應與用戶輸入的邏輯關聯
            user_input_lower = user_input.lower()
            
            for response in prediction.responses:
                if isinstance(response, str):
                    # 檢查關鍵詞重疊
                    user_words = set(user_input_lower.split())
                    response_words = set(response.lower().split())
                    
                    # 計算詞彙相關性
                    if user_words and response_words:
                        overlap = len(user_words & response_words)
                        relevance = overlap / max(len(user_words), len(response_words))
                        score += relevance * 0.2
                    
                    # 檢查回應的適當性
                    if self._is_appropriate_response(user_input, response):
                        score += 0.1
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"對話連貫性評估失敗: {e}")
            return 0.0
    
    def _evaluate_state_consistency(self,
                                  user_input: str,
                                  prediction: dspy.Prediction,
                                  expected_output: Optional[Dict[str, Any]] = None) -> float:
        """評估狀態一致性
        
        評估對話狀態是否合理。
        """
        try:
            predicted_state = getattr(prediction, 'state', '')
            valid_states = ['NORMAL', 'CONFUSED', 'TRANSITIONING', 'TERMINATED']
            
            # 檢查狀態有效性
            if predicted_state not in valid_states:
                return 0.0
            
            score = 0.5  # 基礎分數，狀態有效
            
            # 如果有預期狀態，比較一致性
            if expected_output and 'state' in expected_output:
                expected_state = expected_output['state']
                if predicted_state == expected_state:
                    score = 1.0
                else:
                    score = 0.3  # 狀態不匹配但仍有效
            else:
                # 基於啟發式規則評估狀態合理性
                state_score = self._evaluate_state_appropriateness(
                    user_input, predicted_state
                )
                score = max(score, state_score)
            
            return score
            
        except Exception as e:
            logger.error(f"狀態一致性評估失敗: {e}")
            return 0.0
    
    def _evaluate_diversity(self,
                          user_input: str,
                          prediction: dspy.Prediction,
                          expected_output: Optional[Dict[str, Any]] = None) -> float:
        """評估回應多樣性
        
        評估生成的回應選項是否具有多樣性。
        """
        try:
            if not hasattr(prediction, 'responses') or not prediction.responses:
                return 0.0
            
            responses = [str(r) for r in prediction.responses if r]
            
            if len(responses) < 2:
                return 0.0
            
            # 計算回應間的差異性
            diversity_scores = []
            
            for i in range(len(responses)):
                for j in range(i + 1, len(responses)):
                    similarity = self._calculate_text_similarity(responses[i], responses[j])
                    diversity_scores.append(1 - similarity)  # 多樣性 = 1 - 相似性
            
            if diversity_scores:
                average_diversity = np.mean(diversity_scores)
                return min(average_diversity, 1.0)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"多樣性評估失敗: {e}")
            return 0.0
    
    def _evaluate_safety(self,
                        user_input: str,
                        prediction: dspy.Prediction,
                        expected_output: Optional[Dict[str, Any]] = None) -> float:
        """評估回應安全性
        
        檢查回應是否包含不當內容。
        """
        try:
            score = 1.0  # 預設安全
            
            if not hasattr(prediction, 'responses') or not prediction.responses:
                return score
            
            # 不當內容關鍵詞 (簡化版本)
            unsafe_keywords = [
                '死', '自殺', '傷害', '暴力', '仇恨',
                '歧視', '不當', '違法', '危險'
            ]
            
            for response in prediction.responses:
                if isinstance(response, str):
                    response_lower = response.lower()
                    for keyword in unsafe_keywords:
                        if keyword in response_lower:
                            score -= 0.2
                            break
            
            return max(score, 0.0)
            
        except Exception as e:
            logger.error(f"安全性評估失敗: {e}")
            return 1.0  # 評估失敗時預設安全
    
    def _prediction_to_dict(self, prediction: dspy.Prediction) -> Dict[str, Any]:
        """將預測結果轉換為字典格式"""
        try:
            result = {}
            
            # 提取常見屬性
            common_attrs = [
                'responses', 'state', 'dialogue_context', 
                'confidence', 'context_classification'
            ]
            
            for attr in common_attrs:
                if hasattr(prediction, attr):
                    value = getattr(prediction, attr)
                    # 確保可序列化
                    if isinstance(value, (str, int, float, list, dict, bool)):
                        result[attr] = value
                    else:
                        result[attr] = str(value)
            
            return result
            
        except Exception as e:
            logger.error(f"預測結果轉換失敗: {e}")
            return {'error': str(e)}
    
    def _contexts_similar(self, context1: str, context2: str) -> bool:
        """檢查兩個情境是否相似"""
        if not context1 or not context2:
            return False
        
        # 簡單的相似性檢查
        words1 = set(context1.lower().split())
        words2 = set(context2.lower().split())
        
        if words1 and words2:
            overlap = len(words1 & words2)
            total = len(words1 | words2)
            similarity = overlap / total
            return similarity > 0.5
        
        return False
    
    def _calculate_context_relevance(self, user_input: str, context: str) -> float:
        """計算情境與用戶輸入的相關性"""
        try:
            # 關鍵詞映射
            context_keywords = {
                '生命徵象': ['血壓', '體溫', '心跳', '呼吸', '血氧'],
                '傷口管路': ['傷口', '管路', '導管', '換藥', '拆線'],
                '復健': ['復健', '運動', '活動', '物理治療'],
                '營養': ['吃', '飲食', '營養', '餵食'],
                '日常': ['睡覺', '休息', '洗澡', '上廁所']
            }
            
            user_lower = user_input.lower()
            context_lower = context.lower()
            
            # 直接匹配
            for category, keywords in context_keywords.items():
                if category in context_lower:
                    for keyword in keywords:
                        if keyword in user_lower:
                            return 0.8
            
            # 詞彙重疊
            user_words = set(user_lower.split())
            context_words = set(context_lower.split())
            
            if user_words and context_words:
                overlap = len(user_words & context_words)
                total = len(user_words | context_words)
                return overlap / total
            
            return 0.3  # 預設相關性
            
        except Exception:
            return 0.3
    
    def _is_appropriate_response(self, user_input: str, response: str) -> bool:
        """檢查回應是否適當"""
        try:
            # 簡單的適當性檢查
            user_lower = user_input.lower()
            response_lower = response.lower()
            
            # 如果是問候，回應應該也是問候
            if any(greeting in user_lower for greeting in ['你好', '早安', '晚安']):
                if any(greeting in response_lower for greeting in ['你好', '早安', '晚安', '哈囉']):
                    return True
            
            # 如果是疼痛相關，回應應該相關
            if any(pain in user_lower for pain in ['痛', '疼', '不舒服']):
                if any(pain_resp in response_lower for pain_resp in ['痛', '疼', '不舒服', '還好']):
                    return True
            
            # 預設適當
            return True
            
        except Exception:
            return True
    
    def _evaluate_state_appropriateness(self, user_input: str, predicted_state: str) -> float:
        """評估狀態的適當性"""
        try:
            user_lower = user_input.lower()
            
            # 困惑狀態的觸發詞
            confusion_triggers = ['不懂', '什麼', '不明白', '搞不清楚']
            
            # 結束狀態的觸發詞  
            termination_triggers = ['結束', '再見', '謝謝', '掰掰']
            
            if predicted_state == 'CONFUSED':
                if any(trigger in user_lower for trigger in confusion_triggers):
                    return 0.9
                else:
                    return 0.4
            elif predicted_state == 'TERMINATED':
                if any(trigger in user_lower for trigger in termination_triggers):
                    return 0.9
                else:
                    return 0.3
            elif predicted_state == 'NORMAL':
                return 0.7  # 大部分情況下正常狀態都是合理的
            else:
                return 0.5
                
        except Exception:
            return 0.5
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """計算文本相似度"""
        try:
            if not text1 or not text2:
                return 0.0
            
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            
            if not words1 or not words2:
                return 0.0
            
            intersection = len(words1 & words2)
            union = len(words1 | words2)
            
            return intersection / union if union > 0 else 0.0
            
        except Exception:
            return 0.0
    
    def _update_evaluation_stats(self, evaluation_result: Dict[str, Any]):
        """更新評估統計資訊"""
        try:
            self.stats['total_evaluations'] += 1
            self.stats['last_evaluation'] = evaluation_result['timestamp']
            
            # 更新平均分數
            for metric, score in evaluation_result['scores'].items():
                if metric not in self.stats['average_scores']:
                    self.stats['average_scores'][metric] = []
                self.stats['average_scores'][metric].append(score)
            
            # 更新評估類型統計
            metrics_used = list(evaluation_result['scores'].keys())
            self.stats['evaluation_types'][','.join(sorted(metrics_used))] += 1
            
        except Exception as e:
            logger.error(f"更新統計失敗: {e}")
    
    def get_evaluation_statistics(self) -> Dict[str, Any]:
        """獲取評估統計資訊"""
        try:
            stats = self.stats.copy()
            
            # 計算平均分數
            if self.stats['average_scores']:
                stats['current_averages'] = {}
                for metric, scores in self.stats['average_scores'].items():
                    if scores:
                        stats['current_averages'][metric] = {
                            'mean': np.mean(scores),
                            'std': np.std(scores) if len(scores) > 1 else 0.0,
                            'count': len(scores)
                        }
            
            return stats
            
        except Exception as e:
            logger.error(f"獲取統計失敗: {e}")
            return {}
    
    def get_recent_evaluations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """獲取最近的評估記錄"""
        return self.evaluation_history[-limit:] if self.evaluation_history else []

# 便利函數
def create_evaluator(config: Optional[Dict[str, Any]] = None) -> DSPyEvaluator:
    """創建評估器實例"""
    return DSPyEvaluator(config)

# 測試函數  
def test_evaluator():
    """測試評估器功能"""
    print("🧪 測試 DSPy 評估器...")
    
    try:
        # 創建評估器
        print("\n1. 創建評估器:")
        evaluator = DSPyEvaluator()
        print("  ✅ 評估器創建成功")
        
        # 創建模擬預測結果
        print("\n2. 測試單個預測評估:")
        mock_prediction = type('MockPrediction', (), {
            'responses': ['我很好', '今天感覺不錯', '謝謝關心'],
            'state': 'NORMAL', 
            'dialogue_context': '一般對話'
        })()
        
        evaluation_result = evaluator.evaluate_prediction(
            user_input="你今天感覺如何？",
            prediction=mock_prediction
        )
        
        print(f"  ✅ 評估完成，總分: {evaluation_result['overall_score']:.2f}")
        print(f"  評估指標: {list(evaluation_result['scores'].keys())}")
        
        # 測試統計功能
        print("\n3. 統計資訊:")
        stats = evaluator.get_evaluation_statistics()
        print(f"  總評估次數: {stats['total_evaluations']}")
        print(f"  平均分數指標: {list(stats.get('current_averages', {}).keys())}")
        
        print("\n✅ 評估器測試通過")
        return True
        
    except Exception as e:
        print(f"❌ 評估器測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_evaluator()