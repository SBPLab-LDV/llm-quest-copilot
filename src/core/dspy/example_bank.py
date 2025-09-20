"""
DSPy 範例銀行

負責管理和檢索 DSPy Examples，提供基於相似度和情境的
範例選擇功能，支援動態範例管理。
"""

import dspy
import numpy as np
from typing import List, Dict, Any, Optional, Tuple, Union
from collections import defaultdict
import logging
import json
from pathlib import Path
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None

import pickle
from datetime import datetime

# 避免相對導入問題
try:
    from .example_loader import ExampleLoader
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    from example_loader import ExampleLoader

logger = logging.getLogger(__name__)

class ExampleBank:
    """DSPy 範例銀行
    
    管理所有範例，提供相似度計算、搜索和檢索功能。
    支援多種檢索策略和快取機制。
    """
    
    def __init__(self, examples_dir: str = "/app/prompts/context_examples",
                 embedding_model: str = "all-MiniLM-L6-v2",
                 cache_dir: str = "/app/cache/embeddings"):
        """初始化範例銀行
        
        Args:
            examples_dir: 範例檔案目錄
            embedding_model: 嵌入模型名稱
            cache_dir: 嵌入向量快取目錄
        """
        self.examples_dir = examples_dir
        self.embedding_model_name = embedding_model
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化組件
        self.loader = ExampleLoader(examples_dir)
        self.embedding_model = None
        
        # 資料儲存
        self.examples: Dict[str, List[dspy.Example]] = {}
        self.all_examples: List[dspy.Example] = []
        self.context_index: Dict[str, List[int]] = defaultdict(list)  # context -> example indices
        self.embeddings: Optional[np.ndarray] = None
        self.embedding_cache_file = self.cache_dir / "example_embeddings.pkl"
        
        # 統計資訊
        self.stats = {
            'total_examples': 0,
            'contexts': 0,
            'loaded_at': None,
            'embedding_model': embedding_model
        }
    
    def _init_embedding_model(self):
        """初始化嵌入模型"""
        if self.embedding_model is None:
            if not SENTENCE_TRANSFORMERS_AVAILABLE:
                logger.warning("sentence-transformers 未安裝，使用簡單文本相似度")
                self.embedding_model = "simple"
                return
            
            try:
                logger.info(f"初始化嵌入模型: {self.embedding_model_name}")
                self.embedding_model = SentenceTransformer(self.embedding_model_name)
                logger.info("嵌入模型初始化成功")
            except Exception as e:
                logger.error(f"嵌入模型初始化失敗: {e}")
                # 使用簡單的文本相似度作為備選
                self.embedding_model = "simple"
    
    def load_all_examples(self) -> bool:
        """載入所有範例
        
        Returns:
            是否成功載入
        """
        try:
            logger.info("開始載入所有範例...")
            
            # 使用範例加載器載入範例
            self.examples = self.loader.load_all_examples()
            
            if not self.examples:
                logger.warning("沒有載入任何範例")
                return False
            
            # 建立全域範例列表和索引
            self._build_indices()
            
            # 更新統計資訊
            self.stats.update({
                'total_examples': len(self.all_examples),
                'contexts': len(self.examples),
                'loaded_at': datetime.now().isoformat()
            })
            
            logger.info(f"成功載入 {self.stats['total_examples']} 個範例，"
                       f"涵蓋 {self.stats['contexts']} 個情境")
            
            return True
            
        except Exception as e:
            logger.error(f"載入範例失敗: {e}")
            return False
    
    def _build_indices(self):
        """建立範例索引"""
        self.all_examples = []
        self.context_index = defaultdict(list)
        
        for context, examples in self.examples.items():
            for example in examples:
                index = len(self.all_examples)
                self.all_examples.append(example)
                self.context_index[context].append(index)
        
        logger.info(f"建立索引完成: {len(self.all_examples)} 個範例")
    
    def compute_embeddings(self, force_recompute: bool = False) -> bool:
        """計算範例嵌入向量
        
        Args:
            force_recompute: 是否強制重新計算
            
        Returns:
            是否成功計算
        """
        # 檢查快取
        if not force_recompute and self._load_embeddings_cache():
            return True
        
        if not self.all_examples:
            logger.error("沒有範例可計算嵌入向量")
            return False
        
        try:
            self._init_embedding_model()
            
            if self.embedding_model == "simple":
                # 使用簡單相似度，不需要嵌入向量
                self.embeddings = None
                logger.info("使用簡單文本相似度，跳過嵌入向量計算")
                return True
            
            logger.info("開始計算嵌入向量...")
            
            # 提取文本用於嵌入
            texts = [self._extract_text_for_embedding(example) 
                    for example in self.all_examples]
            
            # 計算嵌入向量
            embeddings_list = self.embedding_model.encode(
                texts, 
                show_progress_bar=True,
                batch_size=32
            )
            
            self.embeddings = np.array(embeddings_list)
            
            # 儲存快取
            self._save_embeddings_cache()
            
            logger.info(f"嵌入向量計算完成: {self.embeddings.shape}")
            return True
            
        except Exception as e:
            logger.error(f"嵌入向量計算失敗: {e}")
            # 回退到簡單相似度
            self.embedding_model = "simple"
            self.embeddings = None
            return True
    
    def _extract_text_for_embedding(self, example: dspy.Example) -> str:
        """提取範例文本用於嵌入向量計算
        
        Args:
            example: DSPy Example
            
        Returns:
            用於嵌入的文本
        """
        text_parts = []
        
        # 使用者輸入
        if hasattr(example, 'user_input') and example.user_input:
            text_parts.append(example.user_input)
        
        # 對話情境
        if hasattr(example, 'dialogue_context') and example.dialogue_context:
            text_parts.append(example.dialogue_context)
        
        # 關鍵字 (如果有的話)
        if hasattr(example, 'metadata') and example.metadata:
            keyword = example.metadata.get('keyword', '')
            if keyword:
                text_parts.append(keyword)
        
        return " ".join(text_parts)
    
    def _load_embeddings_cache(self) -> bool:
        """載入嵌入向量快取
        
        Returns:
            是否成功載入快取
        """
        if not self.embedding_cache_file.exists():
            return False
        
        try:
            with open(self.embedding_cache_file, 'rb') as f:
                cache_data = pickle.load(f)
            
            # 檢查快取是否匹配當前資料
            if (cache_data.get('model') == self.embedding_model_name and
                cache_data.get('num_examples') == len(self.all_examples)):
                
                self.embeddings = cache_data['embeddings']
                logger.info("成功載入嵌入向量快取")
                return True
            else:
                logger.info("嵌入向量快取不匹配，需要重新計算")
                return False
                
        except Exception as e:
            logger.error(f"載入嵌入向量快取失敗: {e}")
            return False
    
    def _save_embeddings_cache(self):
        """儲存嵌入向量快取"""
        if self.embeddings is None:
            return
        
        try:
            cache_data = {
                'embeddings': self.embeddings,
                'model': self.embedding_model_name,
                'num_examples': len(self.all_examples),
                'created_at': datetime.now().isoformat()
            }
            
            with open(self.embedding_cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            
            logger.info("嵌入向量快取儲存成功")
            
        except Exception as e:
            logger.error(f"儲存嵌入向量快取失敗: {e}")
    
    def get_relevant_examples(self, query: str, context: Optional[str] = None,
                            k: int = 5, strategy: str = "hybrid") -> List[dspy.Example]:
        """獲取相關範例
        
        Args:
            query: 查詢文本
            context: 指定情境 (可選)
            k: 返回範例數量
            strategy: 檢索策略 ("similarity", "context", "hybrid")
            
        Returns:
            相關範例列表
        """
        if not self.all_examples:
            logger.warning("沒有可用範例")
            return []
        
        if strategy == "context" and context:
            return self._get_context_examples(context, k)
        elif strategy == "similarity":
            return self._get_similarity_examples(query, k)
        elif strategy == "hybrid":
            return self._get_hybrid_examples(query, context, k)
        else:
            logger.warning(f"未知檢索策略: {strategy}")
            return self.all_examples[:k]
    
    def _get_context_examples(self, context: str, k: int) -> List[dspy.Example]:
        """基於情境獲取範例
        
        Args:
            context: 情境名稱
            k: 返回數量
            
        Returns:
            情境範例列表
        """
        if context in self.examples:
            examples = self.examples[context][:k]
            logger.debug(f"從情境 {context} 獲取 {len(examples)} 個範例")
            return examples
        
        # 模糊匹配
        for ctx_name, examples in self.examples.items():
            if context.lower() in ctx_name.lower() or ctx_name.lower() in context.lower():
                logger.debug(f"模糊匹配情境 {ctx_name} -> {context}")
                return examples[:k]
        
        logger.warning(f"找不到情境: {context}")
        return []
    
    def _get_similarity_examples(self, query: str, k: int) -> List[dspy.Example]:
        """基於相似度獲取範例
        
        Args:
            query: 查詢文本
            k: 返回數量
            
        Returns:
            相似範例列表
        """
        if self.embedding_model == "simple":
            return self._get_simple_similarity_examples(query, k)
        
        if self.embeddings is None:
            logger.warning("嵌入向量未計算，使用簡單相似度")
            return self._get_simple_similarity_examples(query, k)
        
        try:
            # 計算查詢嵌入向量
            query_embedding = self.embedding_model.encode([query])
            
            # 計算相似度
            similarities = np.dot(self.embeddings, query_embedding.T).flatten()
            
            # 獲取最相似的 k 個範例
            top_indices = np.argsort(similarities)[-k:][::-1]
            
            result_examples = [self.all_examples[i] for i in top_indices]
            
            logger.debug(f"相似度檢索返回 {len(result_examples)} 個範例")
            return result_examples
            
        except Exception as e:
            logger.error(f"相似度檢索失敗: {e}")
            return self._get_simple_similarity_examples(query, k)
    
    def _get_simple_similarity_examples(self, query: str, k: int) -> List[dspy.Example]:
        """簡單文本相似度檢索
        
        Args:
            query: 查詢文本
            k: 返回數量
            
        Returns:
            相似範例列表
        """
        query_lower = query.lower()
        scored_examples = []
        
        for example in self.all_examples:
            score = 0
            
            # 檢查用戶輸入相似度
            if hasattr(example, 'user_input') and example.user_input:
                example_text = example.user_input.lower()
                # 簡單的單詞匹配評分
                common_words = set(query_lower.split()) & set(example_text.split())
                score += len(common_words) * 2
                
                # 包含檢查
                if query_lower in example_text or example_text in query_lower:
                    score += 5
            
            # 檢查關鍵字匹配
            if hasattr(example, 'metadata') and example.metadata:
                keyword = example.metadata.get('keyword', '').lower()
                if keyword:
                    common_words = set(query_lower.split()) & set(keyword.split())
                    score += len(common_words) * 3
            
            scored_examples.append((example, score))
        
        # 排序並返回前 k 個
        scored_examples.sort(key=lambda x: x[1], reverse=True)
        result_examples = [example for example, score in scored_examples[:k]]
        
        logger.debug(f"簡單相似度檢索返回 {len(result_examples)} 個範例")
        return result_examples
    
    def _get_hybrid_examples(self, query: str, context: Optional[str], 
                           k: int) -> List[dspy.Example]:
        """混合檢索策略
        
        Args:
            query: 查詢文本
            context: 情境 (可選)
            k: 返回數量
            
        Returns:
            混合檢索結果
        """
        examples = []
        
        # 先嘗試情境檢索 (如果指定情境)
        if context:
            context_examples = self._get_context_examples(context, k // 2)
            examples.extend(context_examples)
        
        # 補充相似度檢索
        remaining_k = k - len(examples)
        if remaining_k > 0:
            similarity_examples = self._get_similarity_examples(query, remaining_k * 2)
            
            # 過濾重複
            existing_inputs = {getattr(ex, 'user_input', '') for ex in examples}
            for example in similarity_examples:
                if getattr(example, 'user_input', '') not in existing_inputs:
                    examples.append(example)
                    if len(examples) >= k:
                        break
        
        logger.debug(f"混合檢索返回 {len(examples)} 個範例")
        return examples[:k]
    
    def get_context_list(self) -> List[str]:
        """獲取所有情境列表
        
        Returns:
            情境名稱列表
        """
        return list(self.examples.keys())
    
    def get_bank_statistics(self) -> Dict[str, Any]:
        """獲取範例銀行統計資訊
        
        Returns:
            統計資訊字典
        """
        context_stats = {}
        for context, examples in self.examples.items():
            context_stats[context] = {
                'count': len(examples),
                'avg_responses': np.mean([len(getattr(ex, 'responses', [])) 
                                        for ex in examples]),
                'unique_keywords': len(set([
                    ex.metadata.get('keyword', '') for ex in examples 
                    if hasattr(ex, 'metadata') and ex.metadata
                ]))
            }
        
        stats = self.stats.copy()
        stats['context_details'] = context_stats
        stats['has_embeddings'] = self.embeddings is not None
        stats['embedding_shape'] = self.embeddings.shape if self.embeddings is not None else None
        
        return stats
    
    def add_example(self, example: dspy.Example, context: str):
        """添加新範例
        
        Args:
            example: DSPy Example
            context: 情境名稱
        """
        if context not in self.examples:
            self.examples[context] = []
        
        self.examples[context].append(example)
        
        # 重建索引
        self._build_indices()
        
        # 標記需要重新計算嵌入向量
        if self.embeddings is not None:
            logger.info("添加新範例，嵌入向量需要重新計算")
            self.embeddings = None
        
        logger.info(f"添加範例到情境 {context}")

# 便利函數
def create_example_bank(examples_dir: str = "/app/prompts/context_examples",
                       embedding_model: str = "all-MiniLM-L6-v2") -> ExampleBank:
    """創建並初始化範例銀行
    
    Args:
        examples_dir: 範例目錄
        embedding_model: 嵌入模型
        
    Returns:
        初始化的 ExampleBank
    """
    bank = ExampleBank(examples_dir, embedding_model)
    
    if bank.load_all_examples():
        bank.compute_embeddings()
        return bank
    else:
        raise RuntimeError("無法初始化範例銀行")

# 測試函數
def test_example_bank():
    """測試範例銀行功能"""
    print("🧪 測試 DSPy 範例銀行...")
    
    try:
        # 創建範例銀行
        print("\n1. 創建範例銀行:")
        bank = ExampleBank()
        
        # 載入範例
        print("\n2. 載入範例:")
        if bank.load_all_examples():
            print(f"  ✅ 成功載入 {bank.stats['total_examples']} 個範例")
        else:
            print("  ❌ 範例載入失敗")
            return False
        
        # 計算嵌入向量
        print("\n3. 計算嵌入向量:")
        if bank.compute_embeddings():
            print("  ✅ 嵌入向量計算完成")
        else:
            print("  ❌ 嵌入向量計算失敗")
        
        # 測試檢索
        print("\n4. 測試檢索:")
        
        # 情境檢索
        context_examples = bank.get_relevant_examples(
            "測試", context="vital_signs_examples", k=3, strategy="context"
        )
        print(f"  情境檢索: {len(context_examples)} 個範例")
        
        # 相似度檢索
        similarity_examples = bank.get_relevant_examples(
            "你發燒了嗎", k=3, strategy="similarity"
        )
        print(f"  相似度檢索: {len(similarity_examples)} 個範例")
        
        # 混合檢索
        hybrid_examples = bank.get_relevant_examples(
            "血壓高", context="vital_signs", k=3, strategy="hybrid"
        )
        print(f"  混合檢索: {len(hybrid_examples)} 個範例")
        
        # 顯示統計
        print("\n5. 統計資訊:")
        stats = bank.get_bank_statistics()
        print(f"  總情境數: {stats['contexts']}")
        print(f"  總範例數: {stats['total_examples']}")
        print(f"  有嵌入向量: {stats['has_embeddings']}")
        
        print("\n✅ 範例銀行測試完成")
        return True
        
    except Exception as e:
        print(f"❌ 範例銀行測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_example_bank()