"""
DSPy 提示優化器

實現 DSPy 的自動提示優化功能，包括訓練數據準備、
BootstrapFewShot 優化和結果保存/載入。
"""

import dspy
from typing import List, Dict, Any, Optional, Tuple, Union
import logging
import json
import pickle
import os
from pathlib import Path
from datetime import datetime
import yaml

# 避免相對導入問題
try:
    from .dialogue_module import DSPyDialogueModule
    from .example_selector import ExampleSelector
    from .config import DSPyConfig
    from .signatures import PatientResponseSignature
except ImportError:
    import sys
    sys.path.append(os.path.dirname(__file__))
    from dialogue_module import DSPyDialogueModule
    from example_selector import ExampleSelector
    from config import DSPyConfig
    from signatures import PatientResponseSignature

logger = logging.getLogger(__name__)

class DSPyOptimizer:
    """DSPy 提示優化器
    
    負責準備訓練資料、執行優化和管理優化結果。
    支援 BootstrapFewShot 和其他 DSPy 優化器。
    """
    
    def __init__(self, 
                 cache_dir: str = "/app/cache/dspy_optimizer",
                 config: Optional[Dict[str, Any]] = None):
        """初始化優化器
        
        Args:
            cache_dir: 快取和模型儲存目錄
            config: 配置字典
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_manager = DSPyConfig()
        self.config = config or self.config_manager.get_dspy_config()
        
        # 優化器實例
        self.optimizers = {}
        
        # 訓練資料
        self.training_data: List[dspy.Example] = []
        self.validation_data: List[dspy.Example] = []
        
        # 優化結果
        self.optimization_results: Dict[str, Any] = {}
        
        # 統計資訊
        self.stats = {
            'optimizations_run': 0,
            'best_scores': {},
            'optimization_history': [],
            'last_optimization': None
        }
        
        logger.info("DSPy 優化器初始化完成")
    
    def prepare_training_data(self, 
                            data_sources: List[str] = None,
                            train_ratio: float = 0.8,
                            max_examples: int = 100) -> Tuple[List[dspy.Example], List[dspy.Example]]:
        """準備訓練和驗證資料
        
        Args:
            data_sources: 資料來源列表（範例檔案或情境）
            train_ratio: 訓練資料比例
            max_examples: 最大範例數量
            
        Returns:
            (訓練資料, 驗證資料) 的元組
        """
        try:
            logger.info("開始準備訓練資料...")
            
            # 載入範例資料
            all_examples = self._load_examples(data_sources, max_examples)
            
            if len(all_examples) == 0:
                logger.warning("沒有找到訓練範例")
                return [], []
            
            # 分割訓練和驗證資料
            train_size = int(len(all_examples) * train_ratio)
            
            # 打亂資料
            import random
            random.shuffle(all_examples)
            
            self.training_data = all_examples[:train_size]
            self.validation_data = all_examples[train_size:]
            
            logger.info(f"訓練資料準備完成: {len(self.training_data)} 訓練, {len(self.validation_data)} 驗證")
            
            # 儲存資料到快取
            self._save_data_cache()
            
            return self.training_data, self.validation_data
            
        except Exception as e:
            logger.error(f"訓練資料準備失敗: {e}")
            return [], []
    
    def _load_examples(self, data_sources: List[str] = None, 
                      max_examples: int = 100) -> List[dspy.Example]:
        """載入範例資料
        
        Args:
            data_sources: 資料來源列表
            max_examples: 最大範例數量
            
        Returns:
            範例列表
        """
        try:
            example_selector = ExampleSelector()
            
            if not data_sources:
                # 使用所有可用的範例
                all_examples = example_selector.example_bank.all_examples
            else:
                # 根據指定來源載入範例
                all_examples = []
                for source in data_sources:
                    if source in example_selector.example_bank.examples:
                        all_examples.extend(example_selector.example_bank.examples[source])
                    else:
                        logger.warning(f"找不到資料來源: {source}")
            
            # 限制數量
            if len(all_examples) > max_examples:
                import random
                all_examples = random.sample(all_examples, max_examples)
            
            # 轉換為訓練格式
            training_examples = []
            for example in all_examples:
                if hasattr(example, 'user_input') and hasattr(example, 'responses'):
                    # 為每個原始範例創建多個訓練範例
                    training_examples.extend(
                        self._create_training_examples_from_raw(example)
                    )
            
            logger.info(f"從 {len(all_examples)} 個原始範例創建了 {len(training_examples)} 個訓練範例")
            return training_examples
            
        except Exception as e:
            logger.error(f"載入範例失敗: {e}")
            return []
    
    def _create_training_examples_from_raw(self, raw_example: dspy.Example) -> List[dspy.Example]:
        """從原始範例創建訓練範例
        
        Args:
            raw_example: 原始範例
            
        Returns:
            訓練範例列表
        """
        training_examples = []
        
        try:
            user_input = getattr(raw_example, 'user_input', '')
            responses = getattr(raw_example, 'responses', [])
            dialogue_context = getattr(raw_example, 'dialogue_context', '一般對話')
            
            if not user_input or not responses:
                return training_examples
            
            # 為每個回應創建一個訓練範例
            for response in responses[:3]:  # 最多使用前3個回應
                training_example = dspy.Example(
                    user_input=user_input,
                    character_name="訓練病患",
                    character_persona="配合的病患",
                    character_backstory="住院中的病患",
                    character_goal="配合治療",
                    character_details="",
                    conversation_history="",
                    # 預期輸出
                    responses=[response, "讓我想想...", "好的"],  # 包含原始回應和預設回應
                    state="NORMAL",
                    dialogue_context=dialogue_context
                ).with_inputs(
                    "user_input", "character_name", "character_persona",
                    "character_backstory", "character_goal", "character_details",
                    "conversation_history"
                )
                
                training_examples.append(training_example)
            
        except Exception as e:
            logger.error(f"創建訓練範例失敗: {e}")
        
        return training_examples
    
    def optimize_module(self, 
                       module: DSPyDialogueModule,
                       optimizer_type: str = "BootstrapFewShot",
                       metric_func: Optional[callable] = None,
                       **optimizer_kwargs) -> Dict[str, Any]:
        """優化對話模組
        
        Args:
            module: 要優化的對話模組
            optimizer_type: 優化器類型
            metric_func: 評估指標函數
            **optimizer_kwargs: 優化器參數
            
        Returns:
            優化結果
        """
        try:
            logger.info(f"開始優化模組 (優化器: {optimizer_type})...")
            
            # 檢查訓練資料
            if not self.training_data:
                logger.error("沒有訓練資料，請先執行 prepare_training_data()")
                return {"success": False, "error": "沒有訓練資料"}
            
            # 創建優化器
            optimizer = self._create_optimizer(optimizer_type, metric_func, **optimizer_kwargs)
            if not optimizer:
                return {"success": False, "error": f"無法創建優化器: {optimizer_type}"}
            
            # 執行優化
            start_time = datetime.now()
            
            try:
                # 使用 DSPy 優化器
                optimized_module = optimizer.compile(
                    module, 
                    trainset=self.training_data,
                    valset=self.validation_data[:10] if self.validation_data else []  # 限制驗證集大小
                )
                
                optimization_time = (datetime.now() - start_time).total_seconds()
                
                # 評估優化結果
                evaluation_results = self._evaluate_optimized_module(
                    optimized_module, self.validation_data[:5] if self.validation_data else []
                )
                
                # 儲存優化結果
                optimization_result = {
                    "success": True,
                    "optimizer_type": optimizer_type,
                    "optimization_time": optimization_time,
                    "training_examples": len(self.training_data),
                    "validation_examples": len(self.validation_data),
                    "evaluation": evaluation_results,
                    "timestamp": start_time.isoformat(),
                    "optimized_module": optimized_module
                }
                
                # 更新統計
                self.stats['optimizations_run'] += 1
                self.stats['optimization_history'].append({
                    'timestamp': start_time.isoformat(),
                    'optimizer_type': optimizer_type,
                    'score': evaluation_results.get('average_score', 0),
                    'success': True
                })
                self.stats['last_optimization'] = start_time.isoformat()
                
                # 儲存最佳結果
                self._save_optimization_result(optimizer_type, optimization_result)
                
                logger.info(f"優化完成，耗時 {optimization_time:.2f} 秒")
                return optimization_result
                
            except Exception as e:
                logger.error(f"優化執行失敗: {e}")
                return {
                    "success": False, 
                    "error": str(e),
                    "optimizer_type": optimizer_type,
                    "timestamp": start_time.isoformat()
                }
        
        except Exception as e:
            logger.error(f"模組優化失敗: {e}")
            return {"success": False, "error": str(e)}
    
    def _create_optimizer(self, optimizer_type: str, 
                         metric_func: Optional[callable] = None,
                         **kwargs) -> Optional[dspy.teleprompt.Teleprompter]:
        """創建優化器實例
        
        Args:
            optimizer_type: 優化器類型
            metric_func: 評估指標函數
            **kwargs: 優化器參數
            
        Returns:
            優化器實例
        """
        try:
            # 設定預設參數
            default_params = {
                'max_bootstrapped_demos': kwargs.get('max_bootstrapped_demos', 3),
                'max_labeled_demos': kwargs.get('max_labeled_demos', 5),
                'num_candidate_programs': kwargs.get('num_candidate_programs', 3),
                'num_threads': kwargs.get('num_threads', 1)
            }
            
            if optimizer_type == "BootstrapFewShot":
                # 使用預設評估函數如果沒有提供
                if not metric_func:
                    metric_func = self._default_metric_function
                
                optimizer = dspy.BootstrapFewShot(
                    metric=metric_func,
                    **default_params
                )
                
            elif optimizer_type == "LabeledFewShot":
                optimizer = dspy.LabeledFewShot(
                    k=kwargs.get('k', 3)
                )
                
            elif optimizer_type == "BootstrapFewShotWithRandomSearch":
                if not metric_func:
                    metric_func = self._default_metric_function
                
                optimizer = dspy.BootstrapFewShotWithRandomSearch(
                    metric=metric_func,
                    **default_params
                )
                
            else:
                logger.error(f"不支援的優化器類型: {optimizer_type}")
                return None
            
            logger.info(f"成功創建優化器: {optimizer_type}")
            return optimizer
            
        except Exception as e:
            logger.error(f"創建優化器失敗: {e}")
            return None
    
    def _default_metric_function(self, example, prediction, trace=None) -> float:
        """預設評估指標函數
        
        Args:
            example: 範例
            prediction: 預測結果
            trace: 追蹤資訊 (可選)
            
        Returns:
            評估分數 (0.0 到 1.0)
        """
        try:
            score = 0.0
            
            # 檢查回應格式
            if hasattr(prediction, 'responses') and prediction.responses:
                score += 0.3  # 有回應
                
                if len(prediction.responses) >= 3:
                    score += 0.2  # 有足夠的回應選項
            
            # 檢查狀態
            if hasattr(prediction, 'state') and prediction.state:
                valid_states = ['NORMAL', 'CONFUSED', 'TRANSITIONING', 'TERMINATED']
                if prediction.state in valid_states:
                    score += 0.2  # 有效狀態
            
            # 檢查情境
            if hasattr(prediction, 'dialogue_context') and prediction.dialogue_context:
                score += 0.2  # 有對話情境
            
            # 回應品質檢查 (簡單)
            if hasattr(prediction, 'responses') and prediction.responses:
                for response in prediction.responses:
                    if isinstance(response, str) and len(response) > 5:
                        score += 0.1  # 每個有意義的回應加分
                        break
            
            return min(score, 1.0)  # 確保不超過 1.0
            
        except Exception as e:
            logger.error(f"評估指標計算失敗: {e}")
            return 0.0
    
    def _evaluate_optimized_module(self, module, validation_data: List[dspy.Example]) -> Dict[str, Any]:
        """評估優化後的模組
        
        Args:
            module: 優化後的模組
            validation_data: 驗證資料
            
        Returns:
            評估結果
        """
        if not validation_data:
            return {"message": "沒有驗證資料", "average_score": 0.0}
        
        try:
            scores = []
            successful_predictions = 0
            
            for example in validation_data[:5]:  # 限制驗證數量
                try:
                    # 執行預測
                    prediction = module(
                        user_input=example.user_input,
                        character_name=getattr(example, 'character_name', '測試病患'),
                        character_persona=getattr(example, 'character_persona', ''),
                        character_backstory=getattr(example, 'character_backstory', ''),
                        character_goal=getattr(example, 'character_goal', ''),
                        character_details=getattr(example, 'character_details', ''),
                        conversation_history=getattr(example, 'conversation_history', [])
                    )
                    
                    # 計算分數
                    score = self._default_metric_function(example, prediction)
                    scores.append(score)
                    successful_predictions += 1
                    
                except Exception as e:
                    logger.debug(f"預測失敗: {e}")
                    scores.append(0.0)
            
            average_score = sum(scores) / len(scores) if scores else 0.0
            
            return {
                "total_examples": len(validation_data),
                "evaluated_examples": len(scores),
                "successful_predictions": successful_predictions,
                "average_score": average_score,
                "scores": scores
            }
            
        except Exception as e:
            logger.error(f"模組評估失敗: {e}")
            return {"error": str(e), "average_score": 0.0}
    
    def save_optimized_module(self, module, name: str, metadata: Dict[str, Any] = None):
        """儲存優化後的模組
        
        Args:
            module: 優化後的模組
            name: 模組名稱
            metadata: 元數據
        """
        try:
            save_path = self.cache_dir / f"{name}_optimized.pkl"
            
            save_data = {
                'module': module,
                'metadata': metadata or {},
                'timestamp': datetime.now().isoformat(),
                'config': self.config
            }
            
            with open(save_path, 'wb') as f:
                pickle.dump(save_data, f)
            
            logger.info(f"優化模組已儲存到: {save_path}")
            
        except Exception as e:
            logger.error(f"儲存優化模組失敗: {e}")
    
    def load_optimized_module(self, name: str) -> Optional[Tuple[Any, Dict[str, Any]]]:
        """載入優化後的模組
        
        Args:
            name: 模組名稱
            
        Returns:
            (模組, 元數據) 或 None
        """
        try:
            load_path = self.cache_dir / f"{name}_optimized.pkl"
            
            if not load_path.exists():
                logger.warning(f"找不到優化模組: {load_path}")
                return None
            
            with open(load_path, 'rb') as f:
                save_data = pickle.load(f)
            
            logger.info(f"成功載入優化模組: {load_path}")
            return save_data['module'], save_data.get('metadata', {})
            
        except Exception as e:
            logger.error(f"載入優化模組失敗: {e}")
            return None
    
    def _save_optimization_result(self, optimizer_type: str, result: Dict[str, Any]):
        """儲存優化結果"""
        try:
            result_path = self.cache_dir / f"optimization_results_{optimizer_type}.json"
            
            # 移除無法序列化的對象
            serializable_result = {k: v for k, v in result.items() 
                                 if k != 'optimized_module'}
            
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_result, f, indent=2, ensure_ascii=False)
            
            logger.info(f"優化結果已儲存: {result_path}")
            
        except Exception as e:
            logger.error(f"儲存優化結果失敗: {e}")
    
    def _save_data_cache(self):
        """儲存訓練資料快取"""
        try:
            cache_path = self.cache_dir / "training_data_cache.json"
            
            # 轉換為可序列化格式
            cache_data = {
                'training_data': [self._example_to_dict(ex) for ex in self.training_data],
                'validation_data': [self._example_to_dict(ex) for ex in self.validation_data],
                'timestamp': datetime.now().isoformat()
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"訓練資料快取已儲存: {cache_path}")
            
        except Exception as e:
            logger.error(f"儲存訓練資料快取失敗: {e}")
    
    def _example_to_dict(self, example: dspy.Example) -> Dict[str, Any]:
        """將 DSPy Example 轉換為字典"""
        try:
            return {
                'user_input': getattr(example, 'user_input', ''),
                'character_name': getattr(example, 'character_name', ''),
                'responses': getattr(example, 'responses', []),
                'state': getattr(example, 'state', ''),
                'dialogue_context': getattr(example, 'dialogue_context', '')
            }
        except Exception:
            return {}
    
    def get_optimization_statistics(self) -> Dict[str, Any]:
        """獲取優化統計資訊"""
        return self.stats.copy()
    
    def list_saved_modules(self) -> List[str]:
        """列出已儲存的模組"""
        try:
            saved_modules = []
            for file_path in self.cache_dir.glob("*_optimized.pkl"):
                module_name = file_path.stem.replace('_optimized', '')
                saved_modules.append(module_name)
            return saved_modules
        except Exception as e:
            logger.error(f"列出已儲存模組失敗: {e}")
            return []

# 便利函數
def create_optimizer(cache_dir: str = "/app/cache/dspy_optimizer") -> DSPyOptimizer:
    """創建優化器實例
    
    Args:
        cache_dir: 快取目錄
        
    Returns:
        DSPy 優化器實例
    """
    return DSPyOptimizer(cache_dir)

# 測試函數
def test_optimizer():
    """測試優化器功能"""
    print("🧪 測試 DSPy 優化器...")
    
    try:
        # 創建優化器
        print("\n1. 創建優化器:")
        optimizer = DSPyOptimizer()
        print("  ✅ 優化器創建成功")
        
        # 測試訓練資料準備
        print("\n2. 準備訓練資料:")
        train_data, val_data = optimizer.prepare_training_data(
            max_examples=10
        )
        print(f"  ✅ 訓練資料準備完成: {len(train_data)} 訓練, {len(val_data)} 驗證")
        
        # 測試指標函數
        print("\n3. 測試評估指標:")
        if train_data:
            example = train_data[0]
            # 創建模擬預測結果
            mock_prediction = type('MockPrediction', (), {
                'responses': ['回應1', '回應2', '回應3'],
                'state': 'NORMAL',
                'dialogue_context': '測試情境'
            })()
            
            score = optimizer._default_metric_function(example, mock_prediction)
            print(f"  ✅ 評估指標正常，分數: {score:.2f}")
        
        # 測試統計功能
        print("\n4. 統計資訊:")
        stats = optimizer.get_optimization_statistics()
        print(f"  已執行優化次數: {stats['optimizations_run']}")
        print(f"  優化歷史: {len(stats['optimization_history'])} 記錄")
        
        # 測試模組列表
        print("\n5. 已儲存模組:")
        saved_modules = optimizer.list_saved_modules()
        print(f"  找到 {len(saved_modules)} 個已儲存模組")
        
        print("\n✅ 優化器基本功能測試通過")
        return True
        
    except Exception as e:
        print(f"❌ 優化器測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_optimizer()