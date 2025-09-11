#!/usr/bin/env python3
"""
DSPy 對話管理器適配器

繼承原有 DialogueManager 接口，使用 DSPy 實現內部邏輯，
保持完全的 API 兼容性。
"""

import json
import os
import datetime
import logging
from typing import Optional, List, Union, Dict, Any

from ..dialogue import DialogueManager
from ..character import Character
from ..state import DialogueState
from .dialogue_module import DSPyDialogueModule
from .evaluator import DSPyEvaluator
from .config import DSPyConfig


class DialogueManagerDSPy(DialogueManager):
    """DSPy 實現的對話管理器
    
    繼承原有 DialogueManager，提供完全兼容的接口，
    但內部使用 DSPy 框架進行對話處理。
    """
    
    def __init__(self, character: Character, use_terminal: bool = False, log_dir: str = "logs"):
        """Initialize the DSPy DialogueManager.
        
        Args:
            character: Character instance containing the NPC's information (as patient identifier)
            use_terminal: Whether to use terminal mode for interaction
            log_dir: Directory to save interaction logs
        """
        # 初始化父類，建立基本結構
        super().__init__(character, use_terminal, log_dir)
        
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"DialogueManagerDSPy.__init__ called with DSPy backend")
        
        # 初始化 DSPy 組件
        try:
            self.config = DSPyConfig()
            self.dspy_enabled = self.config.is_dspy_enabled()
            
            if self.dspy_enabled:
                self.logger.info("DSPy enabled - initializing DSPy components")
                self.dialogue_module = DSPyDialogueModule()
                self.evaluator = DSPyEvaluator()
                self.logger.info("DSPy components initialized successfully")
            else:
                self.logger.warning("DSPy disabled in config - falling back to parent implementation")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize DSPy components: {e}")
            self.dspy_enabled = False
            self.logger.warning("Falling back to parent implementation")
        
        # 統計追蹤
        self.stats = {
            'total_calls': 0,
            'dspy_calls': 0,
            'fallback_calls': 0,
            'error_count': 0
        }
    
    async def process_turn(self, user_input: str, gui_selected_response: Optional[str] = None) -> Union[str, dict]:
        """Process one turn of dialogue using DSPy.
        
        Args:
            user_input: The user's input text
            gui_selected_response: Selected response in GUI mode (optional)
            
        Returns:
            Either a string response (terminal mode) or JSON response (GUI mode)
        """
        self.stats['total_calls'] += 1
        
        # 如果 DSPy 未啟用，回退到父類實現
        if not self.dspy_enabled:
            self.stats['fallback_calls'] += 1
            self.logger.debug("DSPy disabled - using parent implementation")
            return await super().process_turn(user_input, gui_selected_response)
        
        try:
            self.stats['dspy_calls'] += 1
            self.logger.debug(f"Processing turn with DSPy: '{user_input}'")
            
            # 記錄用戶輸入到對話歷史
            self.conversation_history.append(f"護理人員: {user_input}")
            
            # 使用 DSPy 對話模組處理輸入
            prediction = self.dialogue_module(
                user_input=user_input,
                character_name=self.character.name,
                character_persona=self.character.persona,
                character_backstory=self.character.backstory,
                character_goal=self.character.goal,
                character_details=self._get_character_details(),
                conversation_history=self._format_conversation_history()
            )
            
            self.logger.debug(f"DSPy prediction: {prediction}")
            
            # 處理預測結果
            response_data = self._process_dspy_prediction(prediction)
            
            # 使用評估器評估回應品質
            try:
                evaluation = self.evaluator.evaluate_prediction(user_input, prediction)
                self.logger.debug(f"Response evaluation: {evaluation['overall_score']:.2f}")
            except Exception as e:
                self.logger.warning(f"Evaluation failed: {e}")
            
            # 更新對話狀態
            self._update_dialogue_state(response_data)
            
            # 處理終端機模式或 GUI 模式
            if self.use_terminal:
                return self._handle_terminal_mode(user_input, response_data)
            else:
                return self._handle_gui_mode(user_input, response_data, gui_selected_response)
                
        except Exception as e:
            self.stats['error_count'] += 1
            self.logger.error(f"DSPy processing failed: {e}")
            self.logger.debug("Falling back to parent implementation")
            
            # 出錯時回退到父類實現
            self.stats['fallback_calls'] += 1
            return await super().process_turn(user_input, gui_selected_response)
    
    def _get_character_details(self) -> Dict[str, Any]:
        """獲取角色詳細資訊"""
        details = {}
        
        # 從角色對象獲取固定設定
        if hasattr(self.character, 'fixed_settings'):
            details.update(self.character.fixed_settings)
        
        # 從角色對象獲取浮動設定
        if hasattr(self.character, 'floating_settings'):
            details.update(self.character.floating_settings)
        
        # 添加其他角色屬性
        if hasattr(self.character, 'age'):
            details['age'] = self.character.age
        if hasattr(self.character, 'gender'):
            details['gender'] = self.character.gender
        if hasattr(self.character, 'medical_condition'):
            details['medical_condition'] = self.character.medical_condition
            
        return details
    
    def _process_dspy_prediction(self, prediction) -> Dict[str, Any]:
        """處理 DSPy 預測結果，轉換為標準格式"""
        try:
            # 檢查 prediction 是否有所需屬性
            responses = getattr(prediction, 'responses', [])
            state = getattr(prediction, 'state', 'NORMAL')
            dialogue_context = getattr(prediction, 'dialogue_context', '一般對話')
            
            # 處理回應列表
            if isinstance(responses, str):
                try:
                    responses = json.loads(responses)
                except json.JSONDecodeError:
                    responses = [responses]
            
            if not isinstance(responses, list):
                responses = [str(responses)]
            
            # 確保至少有一個回應
            if not responses:
                responses = ["我需要一點時間思考..."]
            
            return {
                "responses": responses,
                "state": state,
                "dialogue_context": dialogue_context
            }
            
        except Exception as e:
            self.logger.error(f"Error processing DSPy prediction: {e}")
            return {
                "responses": ["抱歉，我現在無法正確回應"],
                "state": "CONFUSED",
                "dialogue_context": "錯誤情況"
            }
    
    def _update_dialogue_state(self, response_data: Dict[str, Any]):
        """更新對話狀態"""
        try:
            new_state = response_data.get("state", "NORMAL")
            self.current_state = DialogueState(new_state)
            
            dialogue_context = response_data.get("dialogue_context", "")
            if dialogue_context:
                print(f"DSPy 判斷的對話情境: {dialogue_context}")
                
        except ValueError:
            self.logger.warning(f"Invalid state: {new_state}, setting to CONFUSED")
            self.current_state = DialogueState.CONFUSED
    
    def _handle_terminal_mode(self, user_input: str, response_data: Dict[str, Any]) -> str:
        """處理終端機模式的互動"""
        import keyboard
        
        responses = response_data["responses"]
        
        print(f"\n{self.character.name} 的回應選項（DSPy 生成）：")
        for i, response in enumerate(responses, 1):
            print(f"{i}. {response}")
        print("0. 這些選項都不適合（跳過，直接進入下一輪對話）")
        print("q. 結束對話")
        print("\n請按數字鍵 0-5 選擇選項，或按 q 結束對話...")
        
        while True:
            event = keyboard.read_event(suppress=True)
            if event.event_type == 'down':
                if event.name == '0':
                    print("\n跳過此輪回應，請繼續對話")
                    self.conversation_history.append("(跳過此輪回應)")
                    self.log_interaction(user_input, responses, selected_response="(跳過此輪回應)")
                    self.save_interaction_log()
                    return ""
                elif event.name == 'q':
                    print("\n結束對話")
                    self.save_interaction_log()
                    return "quit"
                elif event.name in ['1', '2', '3', '4', '5']:
                    choice = int(event.name)
                    if choice <= len(responses):
                        selected_response = responses[choice - 1]
                        print(f"\n已選擇選項 {choice}: {selected_response}")
                        self.conversation_history.append(f"{self.character.name}: {selected_response}")
                        self.log_interaction(user_input, responses, selected_response=selected_response)
                        self.save_interaction_log()
                        return selected_response
    
    def _handle_gui_mode(self, user_input: str, response_data: Dict[str, Any], gui_selected_response: Optional[str] = None) -> str:
        """處理 GUI 模式的互動"""
        # 記錄互動
        self.log_interaction(user_input, response_data["responses"], selected_response=gui_selected_response)
        self.save_interaction_log()
        
        # 返回 JSON 格式回應
        return json.dumps(response_data, ensure_ascii=False)
    
    def get_dspy_statistics(self) -> Dict[str, Any]:
        """獲取 DSPy 相關統計資訊"""
        stats = self.stats.copy()
        
        # 添加組件統計
        if self.dspy_enabled:
            try:
                if hasattr(self, 'dialogue_module'):
                    module_stats = self.dialogue_module.get_statistics()
                    stats['module_stats'] = module_stats
                    
                if hasattr(self, 'evaluator'):
                    eval_stats = self.evaluator.get_evaluation_statistics()
                    stats['evaluation_stats'] = eval_stats
                    
            except Exception as e:
                self.logger.warning(f"Failed to get component statistics: {e}")
        
        # 計算比率
        if stats['total_calls'] > 0:
            stats['dspy_usage_rate'] = stats['dspy_calls'] / stats['total_calls']
            stats['error_rate'] = stats['error_count'] / stats['total_calls']
        else:
            stats['dspy_usage_rate'] = 0.0
            stats['error_rate'] = 0.0
        
        return stats
    
    def reset_statistics(self):
        """重置統計資訊"""
        self.stats = {
            'total_calls': 0,
            'dspy_calls': 0,
            'fallback_calls': 0,
            'error_count': 0
        }
        
        if self.dspy_enabled:
            try:
                if hasattr(self, 'dialogue_module'):
                    self.dialogue_module.reset_statistics()
                if hasattr(self, 'evaluator'):
                    # 評估器沒有 reset 方法，跳過
                    pass
            except Exception as e:
                self.logger.warning(f"Failed to reset component statistics: {e}")
    
    def cleanup(self):
        """清理資源"""
        self.logger.debug("Cleaning up DialogueManagerDSPy")
        
        if self.dspy_enabled:
            try:
                if hasattr(self, 'dialogue_module'):
                    self.dialogue_module.cleanup()
            except Exception as e:
                self.logger.warning(f"Failed to cleanup DSPy components: {e}")
        
        # 保存最終統計
        final_stats = self.get_dspy_statistics()
        self.logger.info(f"Final DSPy statistics: {final_stats}")