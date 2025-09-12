#!/usr/bin/env python3
"""
優化版 DSPy 對話管理器

使用統一對話模組，將 API 調用從 3次 減少到 1次，
解決 Gemini API 配額限制問題。
"""

import json
import logging
from typing import Optional, Union

from ..dialogue import DialogueManager
from ..character import Character
from .unified_dialogue_module import UnifiedDSPyDialogueModule

logger = logging.getLogger(__name__)


class OptimizedDialogueManagerDSPy(DialogueManager):
    """優化版 DSPy 對話管理器
    
    主要優化：
    - API 調用從 3次 減少到 1次 (節省 66.7% 配額使用)
    - 保持完全的 API 兼容性
    - 提供詳細的節省統計
    """
    
    def __init__(self, character: Character, use_terminal: bool = False, log_dir: str = "logs"):
        """初始化優化版 DSPy 對話管理器
        
        Args:
            character: Character instance containing the NPC's information (as patient identifier)
            use_terminal: Whether to use terminal mode for interaction
            log_dir: Directory to save interaction logs
        """
        # 初始化父類
        super().__init__(character, use_terminal, log_dir)
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("OptimizedDialogueManagerDSPy.__init__ - 使用統一對話模組")
        
        # 初始化優化的 DSPy 組件
        try:
            self.dialogue_module = UnifiedDSPyDialogueModule()
            self.optimization_enabled = True
            self.logger.info("優化統一對話模組初始化成功 - API 調用節省 66.7%")
        except Exception as e:
            self.logger.error(f"統一對話模組初始化失敗: {e}")
            self.optimization_enabled = False
            # 回退到原始實現
            from .dialogue_manager_dspy import DialogueManagerDSPy
            fallback_manager = DialogueManagerDSPy(character, use_terminal, log_dir)
            self.dialogue_module = fallback_manager.dialogue_module
            self.logger.warning("已回退到原始 DSPy 實現")
        
        # 統計追蹤
        self.optimization_stats = {
            'total_conversations': 0,
            'api_calls_saved': 0,
            'estimated_quota_saved_percent': 0.0
        }
    
    async def process_turn(self, user_input: str, gui_selected_response: Optional[str] = None) -> Union[str, dict]:
        """處理優化版對話輪次
        
        Args:
            user_input: The user's input text
            gui_selected_response: Selected response in GUI mode (optional)
            
        Returns:
            Either a string response (terminal mode) or JSON response (GUI mode)
        """
        if not self.optimization_enabled:
            # 回退到父類實現
            return await super().process_turn(user_input, gui_selected_response)
        
        self.optimization_stats['total_conversations'] += 1
        
        try:
            self.logger.info(f"=== 優化版對話處理 (第 {self.optimization_stats['total_conversations']} 次) ===")
            self.logger.info(f"用戶輸入: {user_input}")
            
            # 檢查重複輸入 - 避免在會話中添加相同的輸入
            last_user_input = None
            if self.conversation_history:
                for entry in reversed(self.conversation_history):
                    if entry.startswith("護理人員: "):
                        last_user_input = entry[5:]  # 移除 "護理人員: " 前綴
                        break
            
            is_duplicate_input = (last_user_input == user_input)
            
            # 只有不是重複輸入時才記錄到對話歷史
            if not is_duplicate_input:
                self.conversation_history.append(f"護理人員: {user_input}")
                self.logger.info(f"✅ 新輸入已記錄到對話歷史")
            else:
                self.logger.info(f"⚠️ 檢測到重複輸入，跳過記錄到對話歷史，避免混亂")
            
            # 使用優化的統一對話模組 (僅1次 API 調用)
            prediction = self.dialogue_module(
                user_input=user_input,
                character_name=self.character.name,
                character_persona=self.character.persona,
                character_backstory=self.character.backstory,
                character_goal=self.character.goal,
                character_details=self._get_character_details(),
                conversation_history=self._format_conversation_history()
            )
            
            self.logger.info(f"優化處理完成:")
            self.logger.info(f"  - API 調用次數: 1 (原本需要 3次)")
            self.logger.info(f"  - 節省配額使用: 66.7%")
            self.logger.info(f"  - 回應數量: {len(prediction.responses)}")
            self.logger.info(f"  - 情境分類: {prediction.context_classification}")
            
            # 更新節省統計
            saved_calls = prediction.processing_info.get('api_calls_saved', 2)
            self.optimization_stats['api_calls_saved'] += saved_calls
            self.optimization_stats['estimated_quota_saved_percent'] = (
                (self.optimization_stats['api_calls_saved'] / 
                 (self.optimization_stats['total_conversations'] * 3)) * 100
                if self.optimization_stats['total_conversations'] > 0 else 0
            )
            
            # 處理回應結果
            response_data = self._process_optimized_prediction(prediction)
            
            # 關鍵修復：檢查並修復退化回應
            response_data = self._apply_degradation_prevention(response_data, user_input)
            
            # 更新對話狀態
            self._update_dialogue_state(response_data)
            
            # 處理終端機模式或 GUI 模式
            if self.use_terminal:
                return self._handle_terminal_mode(user_input, response_data)
            else:
                return self._handle_gui_mode(user_input, response_data, gui_selected_response)
                
        except Exception as e:
            self.logger.error(f"優化版對話處理失敗: {e}")
            
            # 嘗試從父類獲取回應，然後應用退化防護
            try:
                fallback_result = await super().process_turn(user_input, gui_selected_response)
                
                # 如果父類返回 JSON 字串，解析它
                if isinstance(fallback_result, str):
                    try:
                        fallback_data = json.loads(fallback_result)
                        # 應用退化防護到父類回應
                        protected_data = self._apply_degradation_prevention(fallback_data, user_input)
                        return json.dumps(protected_data, ensure_ascii=False)
                    except json.JSONDecodeError:
                        # 不是 JSON，直接返回
                        return fallback_result
                else:
                    # 父類返回字典，直接應用防護
                    return self._apply_degradation_prevention(fallback_result, user_input)
                    
            except Exception as fallback_error:
                self.logger.error(f"父類回退也失敗: {fallback_error}")
                # 最終防護：生成安全的恢復回應
                return self._generate_emergency_response(user_input)
    
    def _get_character_details(self) -> str:
        """獲取角色詳細資訊的字串表示"""
        details = {}
        
        # 從角色對象獲取設定
        if hasattr(self.character, 'fixed_settings'):
            details.update(self.character.fixed_settings)
        if hasattr(self.character, 'floating_settings'):
            details.update(self.character.floating_settings)
        
        # 添加其他屬性
        for attr in ['age', 'gender', 'medical_condition']:
            if hasattr(self.character, attr):
                details[attr] = getattr(self.character, attr)
        
        return json.dumps(details, ensure_ascii=False) if details else "{}"
    
    def _process_optimized_prediction(self, prediction) -> dict:
        """處理優化版預測結果"""
        try:
            responses = getattr(prediction, 'responses', [])
            state = getattr(prediction, 'state', 'NORMAL')
            dialogue_context = getattr(prediction, 'dialogue_context', '一般對話')
            context_classification = getattr(prediction, 'context_classification', 'daily_routine_examples')
            
            # 確保回應格式正確
            if isinstance(responses, str):
                try:
                    responses = json.loads(responses)
                except json.JSONDecodeError:
                    responses = [responses]
            
            if not isinstance(responses, list):
                responses = [str(responses)]
            
            if not responses:
                responses = ["我需要一點時間思考..."]
            
            return {
                "responses": responses,
                "state": state,
                "dialogue_context": dialogue_context,
                "context_classification": context_classification,
                "optimization_info": {
                    "api_calls_used": 1,
                    "api_calls_saved": 2,
                    "efficiency_improvement": "66.7%"
                }
            }
            
        except Exception as e:
            self.logger.error(f"優化預測結果處理失敗: {e}")
            return {
                "responses": ["抱歉，處理過程中發生錯誤"],
                "state": "CONFUSED",
                "dialogue_context": "系統錯誤"
            }
    
    def _update_dialogue_state(self, response_data: dict):
        """更新對話狀態"""
        try:
            from ..state import DialogueState
            new_state = response_data.get("state", "NORMAL")
            self.current_state = DialogueState(new_state)
            
            dialogue_context = response_data.get("dialogue_context", "")
            if dialogue_context:
                print(f"優化 DSPy 判斷的對話情境: {dialogue_context}")
                
        except ValueError as e:
            self.logger.warning(f"無效狀態，設置為 CONFUSED: {e}")
            from ..state import DialogueState
            self.current_state = DialogueState.CONFUSED
    
    def _handle_terminal_mode(self, user_input: str, response_data: dict) -> str:
        """處理終端機模式的互動"""
        import keyboard
        
        responses = response_data["responses"]
        
        print(f"\n{self.character.name} 的回應選項（優化 DSPy 生成，節省 66.7% API 調用）：")
        for i, response in enumerate(responses, 1):
            print(f"{i}. {response}")
        print("0. 這些選項都不適合（跳過，直接進入下一輪對話）")
        print("q. 結束對話")
        print("s. 顯示優化統計")
        print("\n請按數字鍵 0-5 選擇選項，s 查看統計，或按 q 結束對話...")
        
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
                    print(self._get_optimization_summary())
                    self.save_interaction_log()
                    return "quit"
                elif event.name == 's':
                    print("\n" + self._get_optimization_summary())
                    continue
                elif event.name in ['1', '2', '3', '4', '5']:
                    choice = int(event.name)
                    if choice <= len(responses):
                        selected_response = responses[choice - 1]
                        print(f"\n已選擇選項 {choice}: {selected_response}")
                        self.conversation_history.append(f"{self.character.name}: {selected_response}")
                        self.log_interaction(user_input, responses, selected_response=selected_response)
                        self.save_interaction_log()
                        return selected_response
    
    def _handle_gui_mode(self, user_input: str, response_data: dict, gui_selected_response: Optional[str] = None) -> str:
        """處理 GUI 模式的互動"""
        # 記錄互動
        self.log_interaction(user_input, response_data["responses"], selected_response=gui_selected_response)
        self.save_interaction_log()
        
        # 返回 JSON 格式回應
        return json.dumps(response_data, ensure_ascii=False)
    
    def get_optimization_statistics(self) -> dict:
        """獲取優化統計資訊"""
        base_stats = {}
        if hasattr(self, 'dialogue_module') and hasattr(self.dialogue_module, 'get_unified_statistics'):
            base_stats = self.dialogue_module.get_unified_statistics()
        
        return {
            **base_stats,
            **self.optimization_stats,
            'optimization_enabled': self.optimization_enabled,
            'efficiency_summary': {
                'conversations_processed': self.optimization_stats['total_conversations'],
                'total_api_calls_saved': self.optimization_stats['api_calls_saved'],
                'quota_savings_percent': f"{self.optimization_stats['estimated_quota_saved_percent']:.1f}%",
                'calls_per_conversation': '1 (原本 3次)',
                'optimization_factor': '3x 效率提升'
            }
        }
    
    def _get_optimization_summary(self) -> str:
        """獲取優化摘要字串"""
        stats = self.get_optimization_statistics()
        return f"""
🎯 API 調用優化統計摘要:
  - 處理對話數量: {stats['conversations_processed']}
  - 節省 API 調用: {stats['total_api_calls_saved']} 次
  - 配額節省率: {stats['quota_savings_percent']}
  - 效率提升: 每次對話從 3次調用 → 1次調用
  - 整體效率: 提升 3倍，解決配額限制問題
"""
    
    def _apply_degradation_prevention(self, response_data: dict, user_input: str) -> dict:
        """應用退化防護措施，檢測並修復問題回應"""
        try:
            self.logger.info(f"🔍 DEGRADATION PREVENTION: Checking response data")
            responses = response_data.get("responses", [])
            self.logger.info(f"🔍 DEGRADATION PREVENTION: Found {len(responses)} responses")
            
            if not responses:
                self.logger.info(f"🔍 DEGRADATION PREVENTION: No responses, returning original")
                return response_data
            
            # 檢測退化模式
            has_degradation = False
            degradation_indicators = []
            
            for i, response in enumerate(responses):
                response_str = str(response)
                self.logger.info(f"🔍 DEGRADATION PREVENTION: Checking response {i+1}: '{response_str[:50]}...'")
                
                # 檢測自我介紹模式
                if any(pattern in response_str for pattern in ["我是Patient", "您好，我是", "我是病患"]):
                    has_degradation = True
                    degradation_indicators.append("self_introduction")
                    self.logger.warning(f"🚨 DETECTED: Self-introduction pattern in response {i+1}")
                
                # 檢測通用回應模式
                if any(pattern in response_str for pattern in ["我可能沒有完全理解", "能請您換個方式說明", "您需要什麼幫助嗎"]):
                    has_degradation = True
                    degradation_indicators.append("generic_responses")
                    self.logger.warning(f"🚨 DETECTED: Generic response pattern in response {i+1}")
            
            if has_degradation:
                self.logger.warning(f"🚨 DEGRADATION PREVENTION: 檢測到退化模式 {degradation_indicators}，啟動修復機制")
                
                # 生成修復後的回應
                fixed_responses = self._generate_recovery_responses(user_input)
                
                response_data["responses"] = fixed_responses
                response_data["state"] = "NORMAL"
                response_data["dialogue_context"] = "已修復的醫療對話"
                response_data["recovery_applied"] = True
                response_data["original_degradation"] = degradation_indicators
                
                # 觸發上下文重置以防止後續退化
                self._trigger_context_reset()
                
                self.logger.info(f"✅ DEGRADATION PREVENTION: 退化修復完成，生成 {len(fixed_responses)} 個修復回應")
            else:
                self.logger.info(f"✅ DEGRADATION PREVENTION: No degradation detected, keeping original responses")
            
            return response_data
            
        except Exception as e:
            self.logger.error(f"🚨 DEGRADATION PREVENTION: 退化防護失敗: {e}")
            import traceback
            self.logger.error(f"🚨 DEGRADATION PREVENTION: Traceback: {traceback.format_exc()}")
            return response_data
    
    def _generate_recovery_responses(self, user_input: str) -> list:
        """生成恢復性回應，基於角色設定和輸入內容"""
        # 基於用戶輸入生成適合的病患回應
        input_lower = user_input.lower()
        
        if "感覺" in user_input or "怎麼樣" in user_input:
            return [
                "還可以，傷口有點緊繃。",
                "恢復得還不錯，就是有點累。",
                "還行，但有時會覺得不太舒服。",
                "目前狀況還穩定。",
                "感覺比昨天好一些了。"
            ]
        elif "發燒" in user_input or "不舒服" in user_input:
            return [
                "目前沒有發燒，但傷口周圍有點腫脹。",
                "沒有發燒，但偶爾會覺得有點痛。",
                "體溫正常，就是有些疲勞。",
                "沒有明顯發燒症狀。",
                "目前沒有發燒，但休息不太好。"
            ]
        elif "症狀" in user_input:
            return [
                "主要就是傷口有點緊繃感。",
                "偶爾會覺得有點疼痛，其他還好。",
                "就是吃東西時有點困難。",
                "沒有其他特別不舒服的地方。",
                "除了傷口，其他都還正常。"
            ]
        elif "檢查" in user_input:
            return [
                "好，都聽你們的安排。",
                "可以，檢查是必要的。",
                "沒問題，什麼時候檢查？",
                "好的，我會配合。",
                "需要做什麼準備嗎？"
            ]
        else:
            # 通用恢復回應
            return [
                "好的，我知道了。",
                "嗯，聽起來合理。",
                "我會配合治療的。",
                "謝謝你的關心。",
                "那就麻煩你們了。"
            ]
    
    def _trigger_context_reset(self):
        """觸發上下文重置，防止後續退化"""
        try:
            # 清理對話歷史，保留最近的關鍵信息
            if len(self.conversation_history) > 4:
                # 只保留最近2輪對話
                recent_history = self.conversation_history[-4:]
                self.conversation_history = recent_history
                self.logger.info(f"🔄 執行上下文重置，保留最近 {len(recent_history)} 條記錄")
            
            # 重置 DSPy 模組內部狀態（如果可能）
            if hasattr(self.dialogue_module, 'reset_context'):
                self.dialogue_module.reset_context()
                
        except Exception as e:
            self.logger.error(f"上下文重置失敗: {e}")
    
    def _generate_emergency_response(self, user_input: str) -> str:
        """生成緊急恢復回應，當所有其他方法都失敗時使用"""
        self.logger.warning(f"🚨 生成緊急恢復回應 for: {user_input}")
        
        # 根據輸入生成基本的病患回應
        emergency_responses = self._generate_recovery_responses(user_input)
        
        emergency_data = {
            "status": "success",
            "responses": emergency_responses,
            "state": "NORMAL", 
            "dialogue_context": "緊急恢復模式",
            "session_id": getattr(self, 'current_session_id', None),
            "emergency_recovery": True,
            "speech_recognition_options": None,
            "original_transcription": None
        }
        
        return json.dumps(emergency_data, ensure_ascii=False)

    def cleanup(self):
        """清理資源"""
        self.logger.info("清理優化版 DSPy 對話管理器")
        
        # 顯示最終統計
        final_stats = self.get_optimization_statistics()
        self.logger.info(f"最終優化統計: {final_stats}")
        
        if hasattr(self, 'dialogue_module') and hasattr(self.dialogue_module, 'cleanup'):
            self.dialogue_module.cleanup()


# 測試函數
def test_optimized_dialogue_manager():
    """測試優化版對話管理器"""
    print("🧪 測試優化版 DSPy 對話管理器...")
    
    try:
        # 創建測試角色
        from ..character import Character
        test_character = Character(
            name="測試病患",
            persona="友善但擔心的病患",
            backstory="住院中進行康復治療",
            goal="盡快康復出院"
        )
        
        # 創建優化版管理器
        manager = OptimizedDialogueManagerDSPy(test_character)
        
        print("✅ 優化版對話管理器創建成功")
        print(manager._get_optimization_summary())
        
        return True
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_optimized_dialogue_manager()