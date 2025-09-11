"""
DSPy 範例選擇器

提供智能範例選擇功能，支援多種選擇策略和適應性調整。
整合範例銀行，為 DSPy 模組提供最相關的 few-shot examples。
"""

import dspy
from typing import List, Dict, Any, Optional, Tuple, Union, Callable
import logging
from collections import Counter
import random
from datetime import datetime
import json

# 避免相對導入問題
try:
    from .example_bank import ExampleBank
    from .signatures import ExampleRetrievalSignature
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    from example_bank import ExampleBank
    from signatures import ExampleRetrievalSignature

logger = logging.getLogger(__name__)

class ExampleSelector:
    """智能範例選擇器
    
    根據查詢內容和情境，從範例銀行中選擇最相關的範例。
    支援多種選擇策略和自適應調整。
    """
    
    def __init__(self, example_bank: Optional[ExampleBank] = None,
                 default_strategy: str = "hybrid",
                 default_k: int = 5):
        """初始化範例選擇器
        
        Args:
            example_bank: 範例銀行實例
            default_strategy: 預設選擇策略
            default_k: 預設返回數量
        """
        self.example_bank = example_bank or self._create_default_bank()
        self.default_strategy = default_strategy
        self.default_k = default_k
        
        # 策略配置
        self.strategies = {
            "random": self._random_selection,
            "context": self._context_based_selection,
            "similarity": self._similarity_based_selection,
            "hybrid": self._hybrid_selection,
            "adaptive": self._adaptive_selection,
            "keyword": self._keyword_based_selection,
            "balanced": self._balanced_selection
        }
        
        # 選擇歷史和統計
        self.selection_history: List[Dict[str, Any]] = []
        self.performance_metrics: Dict[str, float] = {}
        
        # 自適應參數
        self.context_weight = 0.4
        self.similarity_weight = 0.6
        self.diversity_threshold = 0.7
        
    def _create_default_bank(self) -> ExampleBank:
        """創建預設範例銀行"""
        try:
            bank = ExampleBank()
            bank.load_all_examples()
            bank.compute_embeddings()
            return bank
        except Exception as e:
            logger.error(f"創建預設範例銀行失敗: {e}")
            # 返回空的範例銀行
            return ExampleBank()
    
    def select_examples(self, 
                       query: str,
                       context: Optional[str] = None,
                       k: Optional[int] = None,
                       strategy: Optional[str] = None,
                       **kwargs) -> List[dspy.Example]:
        """選擇相關範例
        
        Args:
            query: 查詢文本
            context: 情境名稱 (可選)
            k: 返回數量 (可選)
            strategy: 選擇策略 (可選)
            **kwargs: 額外參數
            
        Returns:
            選中的範例列表
        """
        # 使用預設值
        k = k or self.default_k
        strategy = strategy or self.default_strategy
        
        # 記錄選擇請求
        selection_info = {
            'query': query,
            'context': context,
            'k': k,
            'strategy': strategy,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # 執行選擇策略
            if strategy in self.strategies:
                examples = self.strategies[strategy](
                    query, context, k, **kwargs
                )
            else:
                logger.warning(f"未知策略 {strategy}，使用預設策略")
                examples = self.strategies[self.default_strategy](
                    query, context, k, **kwargs
                )
            
            # 確保多樣性
            examples = self._ensure_diversity(examples, k)
            
            # 記錄選擇結果
            selection_info.update({
                'selected_count': len(examples),
                'success': True,
                'contexts_used': list(set([
                    getattr(ex, 'dialogue_context', 'unknown') 
                    for ex in examples
                ]))
            })
            
            self.selection_history.append(selection_info)
            
            logger.debug(f"選擇完成: {len(examples)} 個範例 (策略: {strategy})")
            return examples
            
        except Exception as e:
            logger.error(f"範例選擇失敗: {e}")
            selection_info.update({
                'selected_count': 0,
                'success': False,
                'error': str(e)
            })
            self.selection_history.append(selection_info)
            return []
    
    def _random_selection(self, query: str, context: Optional[str], 
                         k: int, **kwargs) -> List[dspy.Example]:
        """隨機選擇策略"""
        if context and context in self.example_bank.examples:
            # 從指定情境隨機選擇
            examples = self.example_bank.examples[context]
            return random.sample(examples, min(k, len(examples)))
        else:
            # 從所有範例隨機選擇
            return random.sample(
                self.example_bank.all_examples, 
                min(k, len(self.example_bank.all_examples))
            )
    
    def _context_based_selection(self, query: str, context: Optional[str],
                                k: int, **kwargs) -> List[dspy.Example]:
        """基於情境的選擇策略"""
        return self.example_bank.get_relevant_examples(
            query, context=context, k=k, strategy="context"
        )
    
    def _similarity_based_selection(self, query: str, context: Optional[str],
                                   k: int, **kwargs) -> List[dspy.Example]:
        """基於相似度的選擇策略"""
        return self.example_bank.get_relevant_examples(
            query, context=context, k=k, strategy="similarity"
        )
    
    def _hybrid_selection(self, query: str, context: Optional[str],
                         k: int, **kwargs) -> List[dspy.Example]:
        """混合選擇策略"""
        return self.example_bank.get_relevant_examples(
            query, context=context, k=k, strategy="hybrid"
        )
    
    def _adaptive_selection(self, query: str, context: Optional[str],
                           k: int, **kwargs) -> List[dspy.Example]:
        """自適應選擇策略
        
        根據歷史表現調整選擇策略
        """
        # 分析歷史表現，調整權重
        self._update_adaptive_weights()
        
        # 組合多種策略
        context_examples = []
        similarity_examples = []
        
        if context:
            context_examples = self.example_bank.get_relevant_examples(
                query, context=context, k=k, strategy="context"
            )
        
        similarity_examples = self.example_bank.get_relevant_examples(
            query, k=k*2, strategy="similarity"  # 獲取更多候選
        )
        
        # 根據權重組合結果
        context_count = int(k * self.context_weight)
        similarity_count = k - context_count
        
        selected_examples = []
        selected_examples.extend(context_examples[:context_count])
        
        # 避免重複
        used_inputs = {getattr(ex, 'user_input', '') for ex in selected_examples}
        for example in similarity_examples:
            if len(selected_examples) >= k:
                break
            if getattr(example, 'user_input', '') not in used_inputs:
                selected_examples.append(example)
                used_inputs.add(getattr(example, 'user_input', ''))
        
        return selected_examples[:k]
    
    def _keyword_based_selection(self, query: str, context: Optional[str],
                                k: int, **kwargs) -> List[dspy.Example]:
        """基於關鍵字的選擇策略"""
        query_words = set(query.lower().split())
        scored_examples = []
        
        search_pool = (self.example_bank.examples.get(context, []) 
                      if context else self.example_bank.all_examples)
        
        for example in search_pool:
            score = 0
            
            # 檢查問題匹配
            if hasattr(example, 'user_input') and example.user_input:
                example_words = set(example.user_input.lower().split())
                score += len(query_words & example_words) * 2
            
            # 檢查關鍵字匹配
            if hasattr(example, 'metadata') and example.metadata:
                keyword = example.metadata.get('keyword', '')
                if keyword:
                    keyword_words = set(keyword.lower().split('；'))
                    for kw in keyword_words:
                        kw_parts = set(kw.split())
                        score += len(query_words & kw_parts) * 3
            
            scored_examples.append((example, score))
        
        # 排序並返回前 k 個
        scored_examples.sort(key=lambda x: x[1], reverse=True)
        return [example for example, score in scored_examples[:k]]
    
    def _balanced_selection(self, query: str, context: Optional[str],
                           k: int, **kwargs) -> List[dspy.Example]:
        """平衡選擇策略
        
        確保從不同情境選擇範例，避免過度集中
        """
        examples = []
        contexts_used = set()
        
        # 如果指定情境，優先從該情境選擇部分範例
        if context and context in self.example_bank.examples:
            context_examples = self.example_bank.get_relevant_examples(
                query, context=context, k=k//2, strategy="similarity"
            )
            examples.extend(context_examples)
            contexts_used.add(context)
        
        # 從其他情境選擇範例
        remaining_k = k - len(examples)
        if remaining_k > 0:
            other_contexts = [c for c in self.example_bank.get_context_list() 
                            if c not in contexts_used]
            
            # 每個情境選擇一個最相關的範例
            for ctx in other_contexts[:remaining_k]:
                ctx_examples = self.example_bank.get_relevant_examples(
                    query, context=ctx, k=1, strategy="similarity"
                )
                if ctx_examples:
                    examples.extend(ctx_examples)
                    if len(examples) >= k:
                        break
        
        return examples[:k]
    
    def _ensure_diversity(self, examples: List[dspy.Example], 
                         target_k: int) -> List[dspy.Example]:
        """確保範例多樣性"""
        if len(examples) <= 1:
            return examples
        
        diverse_examples = [examples[0]]  # 第一個總是包含
        
        for candidate in examples[1:]:
            if len(diverse_examples) >= target_k:
                break
            
            # 檢查與已選範例的相似性
            is_diverse = True
            candidate_input = getattr(candidate, 'user_input', '').lower()
            
            for selected in diverse_examples:
                selected_input = getattr(selected, 'user_input', '').lower()
                
                # 簡單的多樣性檢查：避免太相似的問題
                similarity = self._calculate_text_similarity(
                    candidate_input, selected_input
                )
                
                if similarity > self.diversity_threshold:
                    is_diverse = False
                    break
            
            if is_diverse:
                diverse_examples.append(candidate)
        
        return diverse_examples
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """計算文本相似度（簡單版本）"""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _update_adaptive_weights(self):
        """更新自適應權重
        
        根據選擇歷史調整策略權重
        """
        if len(self.selection_history) < 10:
            return  # 需要足夠的歷史資料
        
        recent_history = self.selection_history[-10:]
        success_rate = sum(1 for h in recent_history if h.get('success', False)) / len(recent_history)
        
        # 根據成功率調整權重
        if success_rate > 0.8:
            # 表現良好，保持當前權重
            pass
        elif success_rate > 0.6:
            # 中等表現，略微調整
            self.similarity_weight = min(0.8, self.similarity_weight + 0.1)
            self.context_weight = 1.0 - self.similarity_weight
        else:
            # 表現較差，更多依賴相似度
            self.similarity_weight = min(0.9, self.similarity_weight + 0.2)
            self.context_weight = 1.0 - self.similarity_weight
    
    def get_selection_strategies(self) -> List[str]:
        """獲取可用的選擇策略列表"""
        return list(self.strategies.keys())
    
    def get_selection_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """獲取選擇歷史"""
        return self.selection_history[-limit:]
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """獲取性能指標"""
        if not self.selection_history:
            return {}
        
        total_selections = len(self.selection_history)
        successful_selections = sum(1 for h in self.selection_history 
                                  if h.get('success', False))
        
        strategy_counts = Counter([h.get('strategy', 'unknown') 
                                 for h in self.selection_history])
        
        context_usage = Counter()
        for h in self.selection_history:
            contexts = h.get('contexts_used', [])
            context_usage.update(contexts)
        
        return {
            'total_selections': total_selections,
            'success_rate': successful_selections / total_selections,
            'strategy_usage': dict(strategy_counts),
            'context_usage': dict(context_usage.most_common(10)),
            'adaptive_weights': {
                'context_weight': self.context_weight,
                'similarity_weight': self.similarity_weight
            }
        }
    
    def reset_metrics(self):
        """重置統計數據"""
        self.selection_history.clear()
        self.performance_metrics.clear()
        self.context_weight = 0.4
        self.similarity_weight = 0.6
    
    def configure_strategy(self, strategy: str, **params):
        """配置策略參數"""
        if strategy == "adaptive":
            self.context_weight = params.get('context_weight', self.context_weight)
            self.similarity_weight = params.get('similarity_weight', self.similarity_weight)
            self.diversity_threshold = params.get('diversity_threshold', self.diversity_threshold)
        # 可以為其他策略添加配置選項

# 便利函數
def create_example_selector(examples_dir: str = "/app/prompts/context_examples") -> ExampleSelector:
    """創建範例選擇器
    
    Args:
        examples_dir: 範例目錄
        
    Returns:
        配置好的 ExampleSelector
    """
    try:
        from example_bank import ExampleBank
        bank = ExampleBank(examples_dir)
        bank.load_all_examples()
        bank.compute_embeddings()
        return ExampleSelector(bank)
    except Exception as e:
        logger.error(f"創建範例選擇器失敗: {e}")
        return ExampleSelector()

# 測試函數
def test_example_selector():
    """測試範例選擇器功能"""
    print("🧪 測試 DSPy 範例選擇器...")
    
    try:
        # 創建選擇器
        print("\n1. 創建範例選擇器:")
        selector = ExampleSelector()
        
        if not selector.example_bank.all_examples:
            print("  ❌ 範例銀行為空，無法進行測試")
            return False
        
        print(f"  ✅ 選擇器創建成功，載入 {len(selector.example_bank.all_examples)} 個範例")
        
        # 測試不同的選擇策略
        strategies = ["random", "context", "similarity", "hybrid", "adaptive", "keyword", "balanced"]
        test_queries = [
            ("你發燒了嗎？", "vital_signs_examples"),
            ("血壓測量", "vital_signs"),
            ("傷口護理", "wound_tube_care"),
            ("復健運動", None)
        ]
        
        print("\n2. 測試不同策略:")
        for strategy in strategies:
            print(f"\n  策略: {strategy}")
            
            for query, context in test_queries[:2]:  # 只測試前兩個查詢
                try:
                    examples = selector.select_examples(
                        query, context=context, k=3, strategy=strategy
                    )
                    print(f"    查詢「{query}」-> {len(examples)} 個範例")
                    
                    if examples:
                        first_example = examples[0]
                        print(f"      第一個: {getattr(first_example, 'user_input', 'N/A')[:30]}...")
                        
                except Exception as e:
                    print(f"    ❌ 策略 {strategy} 測試失敗: {e}")
        
        # 測試性能指標
        print("\n3. 性能指標:")
        metrics = selector.get_performance_metrics()
        print(f"  總選擇次數: {metrics.get('total_selections', 0)}")
        print(f"  成功率: {metrics.get('success_rate', 0):.2%}")
        
        # 測試可用策略
        print("\n4. 可用策略:")
        available_strategies = selector.get_selection_strategies()
        print(f"  策略列表: {', '.join(available_strategies)}")
        
        print("\n✅ 範例選擇器測試完成")
        return True
        
    except Exception as e:
        print(f"❌ 範例選擇器測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_example_selector()