"""
DSPy 範例加載器

將 YAML 格式的範例轉換為 DSPy Example 格式，
並提供範例驗證和批量處理功能。
"""

import dspy
import yaml
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import logging

logger = logging.getLogger(__name__)

class ExampleLoader:
    """YAML 範例加載器
    
    負責將 prompts/context_examples/ 下的 YAML 檔案
    轉換為 DSPy Example 對象。
    """
    
    def __init__(self, examples_dir: str = "/app/prompts/context_examples"):
        """初始化範例加載器
        
        Args:
            examples_dir: 範例檔案目錄路徑
        """
        self.examples_dir = Path(examples_dir)
        self.loaded_examples: Dict[str, List[dspy.Example]] = {}
        
    def load_yaml_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """加載單個 YAML 檔案
        
        Args:
            file_path: YAML 檔案路徑
            
        Returns:
            解析後的 YAML 內容
            
        Raises:
            FileNotFoundError: 檔案不存在
            yaml.YAMLError: YAML 格式錯誤
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"範例檔案不存在: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)
            logger.info(f"成功加載 YAML 檔案: {file_path}")
            return content
        except yaml.YAMLError as e:
            logger.error(f"YAML 解析錯誤 {file_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"檔案讀取錯誤 {file_path}: {e}")
            raise
    
    def yaml_to_dspy_examples(self, yaml_data: Dict[str, Any], 
                             context_name: str) -> List[dspy.Example]:
        """將 YAML 資料轉換為 DSPy Examples
        
        Args:
            yaml_data: YAML 檔案內容
            context_name: 情境名稱
            
        Returns:
            DSPy Example 列表
        """
        examples = []
        
        # 查找範例資料 - 適應實際的 YAML 結構
        examples_data = None
        
        # 實際結構: vital_signs_examples -> [{'context': '生命徵象相關', 'examples': [...]}]
        if context_name in yaml_data:
            context_list = yaml_data[context_name]
            if isinstance(context_list, list) and len(context_list) > 0:
                # 每個 context_list 項目都包含 context 和 examples
                for context_item in context_list:
                    if isinstance(context_item, dict) and 'examples' in context_item:
                        context = context_item.get('context', context_name)
                        examples_list = context_item['examples']
                        
                        # 處理這個 context 的所有範例
                        context_examples = self._process_examples_list(
                            examples_list, context
                        )
                        examples.extend(context_examples)
        
        logger.info(f"成功轉換 {len(examples)} 個範例 ({context_name})")
        return examples
    
    def _process_examples_list(self, examples_list: List[Dict[str, Any]], 
                              context: str) -> List[dspy.Example]:
        """處理範例列表
        
        Args:
            examples_list: 範例資料列表
            context: 情境名稱
            
        Returns:
            DSPy Example 列表
        """
        examples = []
        
        for i, example_data in enumerate(examples_list):
            try:
                dspy_example = self._convert_single_example(
                    example_data, context, i
                )
                if dspy_example:
                    examples.append(dspy_example)
            except Exception as e:
                logger.error(f"轉換範例失敗 {context}[{i}]: {e}")
                continue
        
        return examples
    
    def _convert_single_example(self, example_data: Dict[str, Any], 
                               context: str, index: int) -> Optional[dspy.Example]:
        """轉換單個範例
        
        Args:
            example_data: 範例資料
            context: 情境名稱
            index: 範例索引
            
        Returns:
            DSPy Example 或 None
        """
        try:
            # 提取必要欄位
            question = example_data.get('question', '')
            responses = example_data.get('responses', [])
            keyword = example_data.get('keyword', '')
            
            if not question or not responses:
                logger.warning(f"範例 {context}[{index}] 缺少必要欄位")
                return None
            
            # 創建 DSPy Example
            # 使用與 PatientResponseSignature 相容的格式
            example = dspy.Example(
                user_input=question,
                character_name="測試病患",  # 預設值，實際使用時會替換
                character_persona="",
                character_backstory="",
                character_goal="",
                character_details="",
                conversation_history="",
                responses=responses,  # 直接使用回應列表
                state="NORMAL",
                dialogue_context=context
            ).with_inputs(
                "user_input", "character_name", "character_persona", 
                "character_backstory", "character_goal", "character_details",
                "conversation_history"
            )
            
            # 添加元數據
            example.metadata = {
                'keyword': keyword,
                'context': context,
                'original_index': index,
                'source_file': context
            }
            
            return example
            
        except Exception as e:
            logger.error(f"轉換單個範例失敗 {context}[{index}]: {e}")
            return None
    
    def load_context_examples(self, context_name: str) -> List[dspy.Example]:
        """加載特定情境的範例
        
        Args:
            context_name: 情境名稱 (不含 .yaml 副檔名)
            
        Returns:
            DSPy Example 列表
        """
        # 檢查是否已加載
        if context_name in self.loaded_examples:
            return self.loaded_examples[context_name]
        
        # 構建檔案路徑
        file_path = self.examples_dir / f"{context_name}.yaml"
        
        try:
            # 加載 YAML 檔案
            yaml_data = self.load_yaml_file(file_path)
            
            # 轉換為 DSPy Examples
            examples = self.yaml_to_dspy_examples(yaml_data, context_name)
            
            # 快取結果
            self.loaded_examples[context_name] = examples
            
            return examples
            
        except Exception as e:
            logger.error(f"加載情境範例失敗 {context_name}: {e}")
            return []
    
    def load_all_examples(self) -> Dict[str, List[dspy.Example]]:
        """加載所有範例檔案
        
        Returns:
            情境名稱到 DSPy Examples 的映射
        """
        if not self.examples_dir.exists():
            logger.error(f"範例目錄不存在: {self.examples_dir}")
            return {}
        
        # 找出所有 YAML 檔案
        yaml_files = list(self.examples_dir.glob("*.yaml"))
        
        if not yaml_files:
            logger.warning(f"在 {self.examples_dir} 中找不到 YAML 檔案")
            return {}
        
        logger.info(f"找到 {len(yaml_files)} 個範例檔案")
        
        # 加載每個檔案
        for yaml_file in yaml_files:
            context_name = yaml_file.stem  # 檔案名不含副檔名
            self.load_context_examples(context_name)
        
        return self.loaded_examples.copy()
    
    def validate_example(self, example: dspy.Example) -> bool:
        """驗證單個範例的完整性
        
        Args:
            example: DSPy Example
            
        Returns:
            是否有效
        """
        try:
            # 檢查必要欄位
            required_inputs = ['user_input']
            required_outputs = ['responses', 'state', 'dialogue_context']
            
            # 檢查輸入欄位
            for field in required_inputs:
                if not hasattr(example, field) or not getattr(example, field):
                    logger.warning(f"範例缺少輸入欄位: {field}")
                    return False
            
            # 檢查輸出欄位
            for field in required_outputs:
                if not hasattr(example, field) or getattr(example, field) is None:
                    logger.warning(f"範例缺少輸出欄位: {field}")
                    return False
            
            # 檢查回應格式
            responses = getattr(example, 'responses', [])
            if not isinstance(responses, list) or len(responses) == 0:
                logger.warning("範例回應格式無效或為空")
                return False
            
            # 檢查狀態值
            state = getattr(example, 'state', '')
            valid_states = ['NORMAL', 'CONFUSED', 'TRANSITIONING', 'TERMINATED']
            if state not in valid_states:
                logger.warning(f"無效的狀態值: {state}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"範例驗證失敗: {e}")
            return False
    
    def validate_examples(self, examples: List[dspy.Example]) -> Dict[str, Any]:
        """驗證範例列表
        
        Args:
            examples: DSPy Example 列表
            
        Returns:
            驗證結果統計
        """
        stats = {
            'total': len(examples),
            'valid': 0,
            'invalid': 0,
            'errors': []
        }
        
        for i, example in enumerate(examples):
            try:
                if self.validate_example(example):
                    stats['valid'] += 1
                else:
                    stats['invalid'] += 1
                    stats['errors'].append(f"範例 {i} 無效")
            except Exception as e:
                stats['invalid'] += 1
                stats['errors'].append(f"範例 {i} 驗證錯誤: {e}")
        
        return stats
    
    def get_example_statistics(self) -> Dict[str, Any]:
        """獲取範例統計信息
        
        Returns:
            統計信息
        """
        stats = {
            'contexts': len(self.loaded_examples),
            'total_examples': 0,
            'contexts_details': {}
        }
        
        for context, examples in self.loaded_examples.items():
            validation_stats = self.validate_examples(examples)
            stats['contexts_details'][context] = {
                'count': len(examples),
                'valid': validation_stats['valid'],
                'invalid': validation_stats['invalid']
            }
            stats['total_examples'] += len(examples)
        
        return stats

# 便利函數
def load_examples_from_yaml(examples_dir: str = "/app/prompts/context_examples") -> Dict[str, List[dspy.Example]]:
    """便利函數：加載所有 YAML 範例
    
    Args:
        examples_dir: 範例目錄路徑
        
    Returns:
        情境名稱到 DSPy Examples 的映射
    """
    loader = ExampleLoader(examples_dir)
    return loader.load_all_examples()

def validate_loaded_examples(examples: Dict[str, List[dspy.Example]]) -> Dict[str, Any]:
    """便利函數：驗證已加載的範例
    
    Args:
        examples: 範例字典
        
    Returns:
        驗證統計結果
    """
    loader = ExampleLoader()
    total_stats = {
        'contexts': len(examples),
        'total_examples': 0,
        'total_valid': 0,
        'total_invalid': 0,
        'context_details': {}
    }
    
    for context, example_list in examples.items():
        validation_stats = loader.validate_examples(example_list)
        total_stats['context_details'][context] = validation_stats
        total_stats['total_examples'] += validation_stats['total']
        total_stats['total_valid'] += validation_stats['valid']
        total_stats['total_invalid'] += validation_stats['invalid']
    
    return total_stats

# 測試函數
def test_example_loader():
    """測試範例加載器功能"""
    print("🧪 測試 DSPy 範例加載器...")
    
    try:
        loader = ExampleLoader()
        
        # 測試加載單個情境
        print("\n測試加載單個情境 (vital_signs_examples):")
        examples = loader.load_context_examples("vital_signs_examples")
        print(f"  加載 {len(examples)} 個範例")
        
        if examples:
            # 顯示第一個範例
            example = examples[0]
            print(f"  範例預覽:")
            print(f"    用戶輸入: {getattr(example, 'user_input', 'N/A')}")
            print(f"    回應數量: {len(getattr(example, 'responses', []))}")
            print(f"    對話情境: {getattr(example, 'dialogue_context', 'N/A')}")
            
            # 驗證範例
            validation_stats = loader.validate_examples(examples)
            print(f"  驗證結果: {validation_stats['valid']}/{validation_stats['total']} 個有效")
        
        # 測試加載所有範例
        print("\n測試加載所有範例:")
        all_examples = loader.load_all_examples()
        print(f"  加載 {len(all_examples)} 個情境")
        
        # 顯示統計
        stats = loader.get_example_statistics()
        print(f"  總範例數: {stats['total_examples']}")
        
        for context, details in stats['contexts_details'].items():
            print(f"    {context}: {details['count']} 個範例 ({details['valid']} 有效)")
        
        print("✅ 範例加載器測試完成")
        return True
        
    except Exception as e:
        print(f"❌ 範例加載器測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_example_loader()