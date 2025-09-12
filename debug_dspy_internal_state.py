#!/usr/bin/env python3
"""
DSPy 內部狀態檢查工具 (DSPy Internal State Debugger)

這個工具專門用於深度檢查和分析 DSPy 系統的內部狀態，
包括模型參數、ChainOfThought 推理路徑、LLM 調用詳情等。

主要功能：
1. DSPy 模型狀態檢查：檢查模型配置、參數和內部狀態
2. ChainOfThought 推理路徑分析：追蹤推理過程的每個步驟
3. LLM 調用監控：監控 LLM 調用的詳細資訊和性能
4. 內存使用分析：檢查系統資源使用情況
5. 配置驗證：驗證 DSPy 配置的正確性

Author: DSPy Analysis Team
Date: 2025-09-12  
Version: 1.0.0
"""

import sys
import os
import json
import time
import logging
import traceback
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import inspect

# 可選依賴處理
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("⚠️ psutil 未安裝，將跳過系統資源監控功能")

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dspy_internal_debug.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class DSPyInternalState:
    """DSPy 內部狀態數據類"""
    model_info: Dict[str, Any]
    signature_info: Dict[str, Any]
    chain_of_thought_info: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    memory_usage: Dict[str, Any]
    configuration: Dict[str, Any]
    timestamp: str


class DSPyInternalStateDebugger:
    """DSPy 內部狀態檢查器主類"""
    
    def __init__(self):
        """初始化檢查器"""
        self.logger = logging.getLogger(__name__)
        self.dspy_modules = {}
        self.internal_states: List[DSPyInternalState] = []
        
        # 系統資源基線
        if HAS_PSUTIL:
            self.baseline_memory = psutil.virtual_memory().used
            self.baseline_cpu = psutil.cpu_percent()
        else:
            self.baseline_memory = 0
            self.baseline_cpu = 0
        
        self.logger.info("🔍 DSPy 內部狀態檢查器初始化完成")
    
    def load_dspy_modules(self) -> bool:
        """載入 DSPy 相關模組"""
        
        self.logger.info("📦 開始載入 DSPy 相關模組...")
        
        try:
            # 添加專案路徑
            sys.path.append('/app/src/core/dspy')
            sys.path.append('/app/src/core')
            
            # 導入 DSPy 相關模組
            import dspy
            self.dspy_modules['dspy'] = dspy
            self.logger.info("✅ DSPy 核心模組載入成功")
            
            # 導入專案特定模組
            try:
                from unified_dialogue_module import UnifiedDialogueModule
                self.dspy_modules['unified_dialogue_module'] = UnifiedDialogueModule
                self.logger.info("✅ 統一對話模組載入成功")
            except ImportError as e:
                self.logger.warning(f"⚠️ 統一對話模組載入失敗: {e}")
            
            try:
                from optimized_dialogue_manager import OptimizedDialogueManager  
                self.dspy_modules['optimized_dialogue_manager'] = OptimizedDialogueManager
                self.logger.info("✅ 優化對話管理器載入成功")
            except ImportError as e:
                self.logger.warning(f"⚠️ 優化對話管理器載入失敗: {e}")
            
            try:
                from degradation_monitor import DegradationMonitor
                self.dspy_modules['degradation_monitor'] = DegradationMonitor
                self.logger.info("✅ 退化監控系統載入成功")
            except ImportError as e:
                self.logger.warning(f"⚠️ 退化監控系統載入失敗: {e}")
            
            return True
            
        except ImportError as e:
            self.logger.error(f"❌ DSPy 模組載入失敗: {e}")
            return False
    
    def inspect_dspy_model_state(self, dialogue_module=None) -> Dict[str, Any]:
        """檢查 DSPy 模型狀態"""
        
        self.logger.info("🔬 開始檢查 DSPy 模型狀態...")
        
        model_state = {
            'dspy_version': 'unknown',
            'lm_model': {},
            'signatures': [],
            'predictors': [],
            'configuration': {},
            'module_instance': {}
        }
        
        try:
            # 檢查 DSPy 版本和配置
            if 'dspy' in self.dspy_modules:
                dspy = self.dspy_modules['dspy']
                model_state['dspy_version'] = getattr(dspy, '__version__', 'unknown')
                
                # 檢查設置的 LM 模型
                if hasattr(dspy, 'settings') and hasattr(dspy.settings, 'lm'):
                    lm = dspy.settings.lm
                    if lm:
                        model_state['lm_model'] = {
                            'type': type(lm).__name__,
                            'model': getattr(lm, 'model', 'unknown'),
                            'kwargs': getattr(lm, 'kwargs', {}),
                            'history': getattr(lm, 'history', [])[-5:] if hasattr(lm, 'history') else []
                        }
                        self.logger.info(f"🤖 檢測到 LM 模型: {model_state['lm_model']['type']}")
                
                # 檢查已註冊的 Signature
                try:
                    signatures = []
                    for name, obj in globals().items():
                        if hasattr(obj, '__bases__') and any('Signature' in str(base) for base in obj.__bases__):
                            signatures.append({
                                'name': name,
                                'fields': getattr(obj, '__annotations__', {})
                            })
                    model_state['signatures'] = signatures
                except Exception as e:
                    self.logger.warning(f"⚠️ Signature 檢查失敗: {e}")
            
            # 檢查對話模組實例狀態
            if dialogue_module:
                model_state['module_instance'] = self._inspect_dialogue_module_instance(dialogue_module)
            
            return model_state
            
        except Exception as e:
            self.logger.error(f"❌ 模型狀態檢查失敗: {e}")
            return model_state
    
    def _inspect_dialogue_module_instance(self, dialogue_module) -> Dict[str, Any]:
        """檢查對話模組實例"""
        
        instance_info = {
            'class_name': type(dialogue_module).__name__,
            'attributes': {},
            'methods': [],
            'predictors': {},
            'internal_state': {}
        }
        
        try:
            # 檢查實例屬性
            for attr_name in dir(dialogue_module):
                if not attr_name.startswith('_'):
                    try:
                        attr_value = getattr(dialogue_module, attr_name)
                        
                        if callable(attr_value):
                            instance_info['methods'].append(attr_name)
                        else:
                            # 檢查是否為 DSPy Predictor
                            if hasattr(attr_value, '__class__') and 'dspy' in str(type(attr_value)):
                                predictor_info = {
                                    'type': type(attr_value).__name__,
                                    'signature': getattr(attr_value, 'signature', None),
                                    'lm': getattr(attr_value, 'lm', None)
                                }
                                instance_info['predictors'][attr_name] = predictor_info
                            else:
                                # 一般屬性
                                attr_str = str(attr_value)
                                if len(attr_str) > 100:
                                    attr_str = attr_str[:100] + "..."
                                instance_info['attributes'][attr_name] = attr_str
                    
                    except Exception as e:
                        instance_info['attributes'][attr_name] = f"Error: {str(e)}"
            
            # 檢查內部狀態（如果有統計資料）
            if hasattr(dialogue_module, 'stats'):
                instance_info['internal_state']['stats'] = dialogue_module.stats
            
            if hasattr(dialogue_module, 'conversation_history'):
                history = dialogue_module.conversation_history
                instance_info['internal_state']['conversation_history_length'] = len(history) if history else 0
                
        except Exception as e:
            self.logger.error(f"❌ 實例檢查失敗: {e}")
            instance_info['error'] = str(e)
        
        return instance_info
    
    def analyze_chain_of_thought(self, dialogue_module=None) -> Dict[str, Any]:
        """分析 ChainOfThought 推理路徑"""
        
        self.logger.info("🧠 開始分析 ChainOfThought 推理路徑...")
        
        cot_analysis = {
            'predictors_found': [],
            'signature_analysis': {},
            'reasoning_patterns': [],
            'performance_characteristics': {}
        }
        
        try:
            if dialogue_module and hasattr(dialogue_module, 'unified_response_generator'):
                generator = dialogue_module.unified_response_generator
                
                # 檢查 ChainOfThought 類型
                if hasattr(generator, '__class__'):
                    cot_analysis['predictor_type'] = type(generator).__name__
                    self.logger.info(f"🔗 檢測到推理器類型: {cot_analysis['predictor_type']}")
                
                # 檢查 Signature
                if hasattr(generator, 'signature'):
                    signature = generator.signature
                    cot_analysis['signature_analysis'] = self._analyze_signature(signature)
                
                # 檢查 LM 配置
                if hasattr(generator, 'lm'):
                    lm = generator.lm
                    cot_analysis['lm_config'] = {
                        'type': type(lm).__name__ if lm else None,
                        'model': getattr(lm, 'model', 'unknown') if lm else None
                    }
                
                # 分析推理模式
                cot_analysis['reasoning_patterns'] = self._analyze_reasoning_patterns(generator)
            
            return cot_analysis
            
        except Exception as e:
            self.logger.error(f"❌ ChainOfThought 分析失敗: {e}")
            cot_analysis['error'] = str(e)
            return cot_analysis
    
    def _analyze_signature(self, signature) -> Dict[str, Any]:
        """分析 Signature 結構"""
        
        signature_info = {
            'class_name': type(signature).__name__ if signature else 'Unknown',
            'input_fields': [],
            'output_fields': [],
            'total_complexity': 0
        }
        
        try:
            if signature and hasattr(signature, '__annotations__'):
                annotations = signature.__annotations__
                
                for field_name, field_type in annotations.items():
                    field_info = {
                        'name': field_name,
                        'type': str(field_type),
                        'is_input': True,  # 預設
                        'is_output': False
                    }
                    
                    # 檢查是否為輸出欄位（基於命名約定）
                    if field_name in ['reasoning', 'responses', 'state', 'dialogue_context', 
                                    'confidence', 'character_consistency_check', 'context_classification']:
                        field_info['is_output'] = True
                        field_info['is_input'] = False
                        signature_info['output_fields'].append(field_info)
                    else:
                        signature_info['input_fields'].append(field_info)
                
                # 計算複雜度
                signature_info['total_complexity'] = len(signature_info['input_fields']) + len(signature_info['output_fields'])
                
                self.logger.info(f"📋 Signature 分析: {len(signature_info['input_fields'])} 輸入, {len(signature_info['output_fields'])} 輸出")
            
        except Exception as e:
            self.logger.error(f"❌ Signature 分析失敗: {e}")
            signature_info['error'] = str(e)
        
        return signature_info
    
    def _analyze_reasoning_patterns(self, predictor) -> List[Dict[str, Any]]:
        """分析推理模式"""
        
        patterns = []
        
        try:
            # 檢查是否有歷史記錄
            if hasattr(predictor, 'lm') and hasattr(predictor.lm, 'history'):
                history = predictor.lm.history
                
                if history:
                    # 分析最近的推理記錄
                    recent_history = history[-5:] if len(history) > 5 else history
                    
                    for i, record in enumerate(recent_history):
                        pattern = {
                            'sequence': i + 1,
                            'prompt_length': len(str(record)) if record else 0,
                            'has_reasoning': 'reasoning' in str(record).lower() if record else False,
                            'timestamp': getattr(record, 'timestamp', 'unknown')
                        }
                        patterns.append(pattern)
            
            # 檢查推理複雜度指標
            if patterns:
                avg_prompt_length = sum(p['prompt_length'] for p in patterns) / len(patterns)
                reasoning_frequency = sum(1 for p in patterns if p['has_reasoning']) / len(patterns)
                
                patterns.append({
                    'summary': {
                        'average_prompt_length': avg_prompt_length,
                        'reasoning_frequency': reasoning_frequency,
                        'total_calls': len(patterns) - 1  # 排除這個summary
                    }
                })
        
        except Exception as e:
            self.logger.error(f"❌ 推理模式分析失敗: {e}")
            patterns.append({'error': str(e)})
        
        return patterns
    
    def monitor_llm_calls(self, dialogue_module=None, duration_seconds: int = 30) -> Dict[str, Any]:
        """監控 LLM 調用"""
        
        self.logger.info(f"📡 開始監控 LLM 調用 ({duration_seconds} 秒)...")
        
        monitoring_data = {
            'monitoring_duration': duration_seconds,
            'start_time': datetime.now().isoformat(),
            'call_records': [],
            'performance_summary': {}
        }
        
        start_time = time.time()
        initial_memory = psutil.virtual_memory().used if HAS_PSUTIL else 0
        
        try:
            # 如果有對話模組，嘗試訪問其 LM
            if dialogue_module and hasattr(dialogue_module, 'unified_response_generator'):
                generator = dialogue_module.unified_response_generator
                
                if hasattr(generator, 'lm') and hasattr(generator.lm, 'history'):
                    initial_history_length = len(generator.lm.history)
                    
                    # 監控循環
                    while time.time() - start_time < duration_seconds:
                        current_history_length = len(generator.lm.history)
                        
                        # 檢查是否有新的調用
                        if current_history_length > initial_history_length:
                            new_calls = current_history_length - initial_history_length
                            
                            call_record = {
                                'timestamp': datetime.now().isoformat(),
                                'new_calls_detected': new_calls,
                                'total_history_length': current_history_length,
                                'memory_usage': psutil.virtual_memory().used if HAS_PSUTIL else 0,
                                'cpu_usage': psutil.cpu_percent() if HAS_PSUTIL else 0
                            }
                            
                            monitoring_data['call_records'].append(call_record)
                            initial_history_length = current_history_length
                        
                        time.sleep(1)  # 每秒檢查一次
            
            # 計算性能摘要
            end_time = time.time()
            final_memory = psutil.virtual_memory().used if HAS_PSUTIL else 0
            
            monitoring_data['performance_summary'] = {
                'actual_duration': end_time - start_time,
                'total_calls_detected': len(monitoring_data['call_records']),
                'memory_change_mb': (final_memory - initial_memory) / 1024 / 1024,
                'average_cpu_usage': sum(r['cpu_usage'] for r in monitoring_data['call_records']) / max(len(monitoring_data['call_records']), 1)
            }
            
            self.logger.info(f"📊 監控完成: 檢測到 {len(monitoring_data['call_records'])} 次調用")
            
        except Exception as e:
            self.logger.error(f"❌ LLM 調用監控失敗: {e}")
            monitoring_data['error'] = str(e)
        
        return monitoring_data
    
    def check_memory_usage(self) -> Dict[str, Any]:
        """檢查記憶體使用情況"""
        
        memory_info = {
            'virtual_memory': {},
            'swap_memory': {},
            'process_memory': {},
            'memory_change_from_baseline': 0
        }
        
        try:
            if not HAS_PSUTIL:
                memory_info['error'] = 'psutil not available'
                self.logger.warning("⚠️ psutil 不可用，跳過記憶體檢查")
                return memory_info
            
            # 虛擬記憶體
            vm = psutil.virtual_memory()
            memory_info['virtual_memory'] = {
                'total_gb': vm.total / 1024 / 1024 / 1024,
                'available_gb': vm.available / 1024 / 1024 / 1024,
                'used_gb': vm.used / 1024 / 1024 / 1024,
                'percentage': vm.percent
            }
            
            # Swap 記憶體
            swap = psutil.swap_memory()
            memory_info['swap_memory'] = {
                'total_gb': swap.total / 1024 / 1024 / 1024,
                'used_gb': swap.used / 1024 / 1024 / 1024,
                'percentage': swap.percent
            }
            
            # 當前程序記憶體
            process = psutil.Process(os.getpid())
            process_memory = process.memory_info()
            memory_info['process_memory'] = {
                'rss_mb': process_memory.rss / 1024 / 1024,
                'vms_mb': process_memory.vms / 1024 / 1024
            }
            
            # 與基線比較
            memory_info['memory_change_from_baseline'] = (vm.used - self.baseline_memory) / 1024 / 1024
            
            self.logger.info(f"💾 記憶體使用: {memory_info['virtual_memory']['percentage']:.1f}%")
            
        except Exception as e:
            self.logger.error(f"❌ 記憶體檢查失敗: {e}")
            memory_info['error'] = str(e)
        
        return memory_info
    
    def verify_configuration(self) -> Dict[str, Any]:
        """驗證配置正確性"""
        
        self.logger.info("🔧 開始驗證 DSPy 配置...")
        
        config_check = {
            'dspy_loaded': False,
            'lm_configured': False,
            'modules_available': {},
            'configuration_issues': [],
            'recommendations': []
        }
        
        try:
            # 檢查 DSPy 是否正確載入
            if 'dspy' in self.dspy_modules:
                config_check['dspy_loaded'] = True
                dspy = self.dspy_modules['dspy']
                
                # 檢查 LM 配置
                if hasattr(dspy, 'settings') and hasattr(dspy.settings, 'lm') and dspy.settings.lm:
                    config_check['lm_configured'] = True
                else:
                    config_check['configuration_issues'].append("LM 模型未正確配置")
                    config_check['recommendations'].append("請使用 dspy.settings.configure() 設置 LM 模型")
            
            # 檢查專案模組可用性
            for module_name, module_class in self.dspy_modules.items():
                if module_name != 'dspy':
                    config_check['modules_available'][module_name] = True
            
            # 生成配置建議
            if not config_check['lm_configured']:
                config_check['recommendations'].append("建議檢查 LLM API 金鑰和端點配置")
            
            if len(config_check['modules_available']) < 2:
                config_check['recommendations'].append("建議檢查專案模組導入路徑")
            
            self.logger.info(f"✅ 配置驗證完成: {len(config_check['configuration_issues'])} 個問題")
            
        except Exception as e:
            self.logger.error(f"❌ 配置驗證失敗: {e}")
            config_check['error'] = str(e)
        
        return config_check
    
    def run_comprehensive_debug(self, create_test_instance: bool = True) -> DSPyInternalState:
        """執行綜合除錯檢查"""
        
        self.logger.info("🔍 開始 DSPy 綜合內部狀態檢查")
        self.logger.info("=" * 60)
        
        # 載入模組
        if not self.load_dspy_modules():
            self.logger.error("❌ 模組載入失敗，無法繼續檢查")
            return None
        
        # 創建測試實例（如果需要）
        dialogue_module = None
        if create_test_instance and 'unified_dialogue_module' in self.dspy_modules:
            try:
                # 嘗試創建對話模組實例
                DialogueModule = self.dspy_modules['unified_dialogue_module']
                dialogue_module = DialogueModule()
                self.logger.info("✅ 測試實例創建成功")
            except Exception as e:
                self.logger.warning(f"⚠️ 測試實例創建失敗: {e}")
        
        # 執行各項檢查
        self.logger.info("\n🔬 執行模型狀態檢查...")
        model_info = self.inspect_dspy_model_state(dialogue_module)
        
        self.logger.info("\n🧠 執行 ChainOfThought 分析...")
        cot_info = self.analyze_chain_of_thought(dialogue_module)
        
        self.logger.info("\n💾 執行記憶體使用檢查...")
        memory_usage = self.check_memory_usage()
        
        self.logger.info("\n🔧 執行配置驗證...")
        configuration = self.verify_configuration()
        
        # 性能指標
        performance_metrics = {}
        if HAS_PSUTIL:
            performance_metrics = {
                'cpu_usage': psutil.cpu_percent(),
                'memory_percentage': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent,
                'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else None
            }
        else:
            performance_metrics = {
                'cpu_usage': 0,
                'memory_percentage': 0,
                'disk_usage': 0,
                'load_average': None,
                'note': 'psutil not available'
            }
        
        # 創建內部狀態對象
        internal_state = DSPyInternalState(
            model_info=model_info,
            signature_info=cot_info.get('signature_analysis', {}),
            chain_of_thought_info=cot_info,
            performance_metrics=performance_metrics,
            memory_usage=memory_usage,
            configuration=configuration,
            timestamp=datetime.now().isoformat()
        )
        
        self.internal_states.append(internal_state)
        
        # 生成綜合報告
        self._generate_debug_report(internal_state)
        
        return internal_state
    
    def _generate_debug_report(self, state: DSPyInternalState):
        """生成除錯報告"""
        
        self.logger.info("\n" + "=" * 60)
        self.logger.info("📋 DSPy 內部狀態綜合報告")
        self.logger.info("=" * 60)
        
        # 模型資訊摘要
        self.logger.info("\n🤖 模型資訊:")
        model_info = state.model_info
        self.logger.info(f"  DSPy 版本: {model_info.get('dspy_version', 'unknown')}")
        
        lm_model = model_info.get('lm_model', {})
        if lm_model:
            self.logger.info(f"  LM 模型: {lm_model.get('type', 'unknown')} ({lm_model.get('model', 'unknown')})")
        else:
            self.logger.info("  LM 模型: 未配置")
        
        # Signature 資訊
        self.logger.info("\n📋 Signature 資訊:")
        sig_info = state.signature_info
        if sig_info:
            self.logger.info(f"  類型: {sig_info.get('class_name', 'unknown')}")
            self.logger.info(f"  輸入欄位: {len(sig_info.get('input_fields', []))}")
            self.logger.info(f"  輸出欄位: {len(sig_info.get('output_fields', []))}")
            self.logger.info(f"  總複雜度: {sig_info.get('total_complexity', 0)}")
        
        # 性能指標
        self.logger.info("\n📊 性能指標:")
        perf = state.performance_metrics
        self.logger.info(f"  CPU 使用率: {perf.get('cpu_usage', 0):.1f}%")
        self.logger.info(f"  記憶體使用率: {perf.get('memory_percentage', 0):.1f}%")
        self.logger.info(f"  磁碟使用率: {perf.get('disk_usage', 0):.1f}%")
        
        # 配置狀態
        self.logger.info("\n🔧 配置狀態:")
        config = state.configuration
        self.logger.info(f"  DSPy 載入: {'✅' if config.get('dspy_loaded', False) else '❌'}")
        self.logger.info(f"  LM 配置: {'✅' if config.get('lm_configured', False) else '❌'}")
        self.logger.info(f"  可用模組: {len(config.get('modules_available', {}))}")
        
        # 配置問題和建議
        issues = config.get('configuration_issues', [])
        if issues:
            self.logger.warning("\n⚠️ 配置問題:")
            for issue in issues:
                self.logger.warning(f"  - {issue}")
        
        recommendations = config.get('recommendations', [])
        if recommendations:
            self.logger.info("\n💡 建議:")
            for rec in recommendations:
                self.logger.info(f"  - {rec}")
        
        # 保存詳細報告
        self._save_debug_report(state)
        
        self.logger.info("\n" + "=" * 60)
    
    def _save_debug_report(self, state: DSPyInternalState):
        """保存詳細除錯報告"""
        
        report_filename = f"dspy_debug_report_{int(time.time())}.json"
        
        report_data = {
            'timestamp': state.timestamp,
            'model_info': state.model_info,
            'signature_info': state.signature_info,
            'chain_of_thought_info': state.chain_of_thought_info,
            'performance_metrics': state.performance_metrics,
            'memory_usage': state.memory_usage,
            'configuration': state.configuration
        }
        
        try:
            with open(report_filename, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"📄 詳細報告已保存: {report_filename}")
            
        except Exception as e:
            self.logger.error(f"❌ 報告保存失敗: {str(e)}")


def main():
    """主函數"""
    print("🔍 DSPy 內部狀態檢查工具")
    print("=" * 50)
    
    debugger = DSPyInternalStateDebugger()
    
    try:
        # 執行綜合除錯
        internal_state = debugger.run_comprehensive_debug()
        
        if internal_state:
            print(f"\n✅ 內部狀態檢查完成！")
            print("📄 詳細日誌請查看: dspy_internal_debug.log")
        else:
            print("\n❌ 內部狀態檢查失敗")
        
        return internal_state
        
    except KeyboardInterrupt:
        print("\n⚠️ 檢查被用戶中斷")
    except Exception as e:
        print(f"\n❌ 檢查過程發生錯誤: {str(e)}")
        logger.error(f"檢查失敗: {str(e)}", exc_info=True)
    
    return None


if __name__ == "__main__":
    main()