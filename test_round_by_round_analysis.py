#!/usr/bin/env python3
"""
DSPy 逐輪分析測試工具 (Round-by-Round Analysis Tool)

這個工具專門用於詳細分析 DSPy 對話模組在多輪對話中的逐輪變化，
幫助識別退化開始的精確時點和原因。

主要功能：
1. 逐輪對話測試：記錄每輪的詳細狀態變化
2. 推理過程追蹤：分析推理品質在各輪的變化
3. 退化檢測：精確識別退化開始時點
4. 趨勢分析：生成詳細的品質變化報告
5. 診斷報告：輸出結構化的分析結果

Author: DSPy Analysis Team  
Date: 2025-09-12
Version: 1.0.0
"""

import requests
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
import sys
import os

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('round_by_round_analysis.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# API 配置
API_BASE_URL = "http://localhost:8000"
DIALOGUE_ENDPOINT = f"{API_BASE_URL}/api/dialogue/text"

@dataclass
class RoundAnalysis:
    """單輪分析結果"""
    round_number: int
    user_input: str
    api_response: Dict[str, Any]
    response_time: float
    analysis_results: Dict[str, Any]
    degradation_detected: bool
    quality_score: float
    timestamp: str


class RoundByRoundAnalyzer:
    """逐輪分析器主類"""
    
    def __init__(self):
        """初始化分析器"""
        self.session_id = f"round_analysis_{int(time.time())}"
        self.round_analyses: List[RoundAnalysis] = []
        self.degradation_monitor = None
        
        # 導入監控系統
        try:
            sys.path.append('/app/src/core/dspy')
            from degradation_monitor import DegradationMonitor
            self.degradation_monitor = DegradationMonitor(enable_logging=True)
            logger.info("✅ 退化監控系統已加載")
        except ImportError as e:
            logger.warning(f"⚠️ 無法加載退化監控系統: {e}")
        
        # 標準測試序列
        self.test_sequence = [
            "你好，感覺怎麼樣？",
            "有沒有覺得發燒或不舒服？", 
            "從什麼時候開始的？",
            "還有其他症狀嗎？",
            "那我們安排一些檢查好嗎？"
        ]
        
        # 測試角色配置
        self.character_config = {
            "name": "Patient_1",
            "persona": "一位剛接受口腔癌手術的中年男性病患，術後恢復期需要密切關注身體狀況。性格溫和但略顯焦慮。",
            "backstory": "陳先生，50歲，口腔癌第二期，剛完成腫瘤切除手術，目前在住院觀察期。手術順利但仍在恢復中。",
            "goal": "配合醫師查房，如實反映身體狀況，希望早日康復出院。",
            "details": {
                "fixed_settings": {
                    "age": "50歲",
                    "condition": "口腔癌術後",
                    "surgery_status": "已完成腫瘤切除手術",
                    "current_status": "住院觀察期"
                },
                "floating_settings": {
                    "mood": "略顯焦慮但配合治療",
                    "pain_level": "輕度到中度不適",
                    "mobility": "可自理但需要休息"
                }
            }
        }
        
        logger.info(f"🔍 逐輪分析器初始化完成 - Session ID: {self.session_id}")
    
    def run_round_by_round_test(self) -> List[RoundAnalysis]:
        """執行逐輪分析測試"""
        logger.info("🚀 開始逐輪對話分析測試")
        logger.info(f"📋 測試序列: {len(self.test_sequence)} 輪對話")
        
        self.round_analyses.clear()
        
        for round_num, user_input in enumerate(self.test_sequence, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"🔵 第 {round_num} 輪分析開始")
            logger.info(f"📝 使用者輸入: \"{user_input}\"")
            
            try:
                # 執行單輪分析
                round_analysis = self._analyze_single_round(round_num, user_input)
                self.round_analyses.append(round_analysis)
                
                # 記錄分析結果
                self._log_round_results(round_analysis)
                
                # 檢查是否需要提早結束
                if round_analysis.degradation_detected and round_num >= 3:
                    logger.warning(f"🚨 第 {round_num} 輪檢測到嚴重退化，繼續分析以觀察後續變化")
                
                # 輪次間等待
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ 第 {round_num} 輪分析失敗: {str(e)}")
                continue
        
        logger.info(f"\n{'='*60}")
        logger.info("📊 逐輪分析測試完成")
        
        # 生成綜合分析報告
        self._generate_comprehensive_report()
        
        return self.round_analyses
    
    def _analyze_single_round(self, round_number: int, user_input: str) -> RoundAnalysis:
        """分析單輪對話"""
        
        # 準備 API 請求
        payload = {
            "text": user_input,
            "character_id": "Patient_1",
            "character_config": self.character_config
        }
        
        # 只在非首輪時加入 session_id
        if round_number > 1 and hasattr(self, 'actual_session_id'):
            payload["session_id"] = self.actual_session_id
        
        # 記錄請求開始時間
        start_time = time.time()
        
        try:
            # 發送 API 請求
            logger.info(f"📤 發送 API 請求...")
            response = requests.post(
                DIALOGUE_ENDPOINT,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            # 計算回應時間
            response_time = time.time() - start_time
            logger.info(f"⏱️ API 回應時間: {response_time:.2f} 秒")
            
            if response.status_code == 200:
                api_response = response.json()
                
                # 第一輪時保存 session_id
                if round_number == 1 and 'session_id' in api_response:
                    self.actual_session_id = api_response['session_id']
                    logger.info(f"📋 保存會話 ID: {self.actual_session_id}")
                
                # 執行詳細分析
                analysis_results = self._perform_detailed_analysis(
                    api_response, round_number, user_input, response_time
                )
                
                # 檢測退化
                degradation_detected = self._detect_round_degradation(
                    api_response, analysis_results
                )
                
                # 計算品質分數
                quality_score = self._calculate_round_quality_score(
                    api_response, analysis_results
                )
                
                return RoundAnalysis(
                    round_number=round_number,
                    user_input=user_input,
                    api_response=api_response,
                    response_time=response_time,
                    analysis_results=analysis_results,
                    degradation_detected=degradation_detected,
                    quality_score=quality_score,
                    timestamp=datetime.now().isoformat()
                )
                
            else:
                logger.error(f"❌ API 請求失敗: {response.status_code} - {response.text}")
                raise Exception(f"API error: {response.status_code}")
                
        except requests.exceptions.Timeout:
            logger.error(f"⏰ API 請求超時 (>{30}s)")
            raise Exception("API timeout")
        except Exception as e:
            logger.error(f"❌ 請求過程發生錯誤: {str(e)}")
            raise
    
    def _perform_detailed_analysis(self, api_response: Dict[str, Any], 
                                 round_number: int, user_input: str, 
                                 response_time: float) -> Dict[str, Any]:
        """執行詳細分析"""
        
        analysis = {
            'basic_info': {
                'response_count': len(api_response.get('responses', [])),
                'state': api_response.get('state', 'UNKNOWN'),
                'dialogue_context': api_response.get('dialogue_context', ''),
                'response_time': response_time,
                'has_reasoning': 'reasoning' in api_response
            },
            'content_analysis': {},
            'quality_metrics': {},
            'degradation_indicators': {},
            'reasoning_analysis': {}
        }
        
        # 內容分析
        responses = api_response.get('responses', [])
        if responses:
            analysis['content_analysis'] = self._analyze_response_content(responses)
        
        # 推理分析
        reasoning = api_response.get('reasoning', '')
        if reasoning:
            analysis['reasoning_analysis'] = self._analyze_reasoning_content(reasoning)
        
        # 使用監控系統進行品質評估
        if self.degradation_monitor:
            try:
                quality_metrics = self.degradation_monitor.assess_dialogue_quality(
                    api_response, round_number, None, self.character_config
                )
                analysis['quality_metrics'] = {
                    'overall_quality': quality_metrics.overall_quality_score,
                    'character_consistency': quality_metrics.character_consistency_score,
                    'response_relevance': quality_metrics.response_relevance_score,
                    'context_appropriateness': quality_metrics.context_appropriateness_score,
                    'reasoning_quality': quality_metrics.reasoning_quality_score,
                    'risk_level': quality_metrics.risk_level.value
                }
                
                analysis['degradation_indicators'] = {
                    'self_introduction_detected': quality_metrics.self_introduction_detected,
                    'generic_response_detected': quality_metrics.generic_response_detected,
                    'response_count_normal': quality_metrics.response_count_normal
                }
            except Exception as e:
                logger.warning(f"⚠️ 監控系統評估失敗: {e}")
        
        return analysis
    
    def _analyze_response_content(self, responses: List[str]) -> Dict[str, Any]:
        """分析回應內容"""
        
        analysis = {
            'total_responses': len(responses),
            'avg_length': sum(len(r) for r in responses) / len(responses) if responses else 0,
            'contains_medical_terms': False,
            'contains_self_introduction': False,
            'contains_generic_phrases': False,
            'response_diversity': 0
        }
        
        # 檢查醫療相關詞彙
        medical_terms = ['手術', '傷口', '疼痛', '腫脹', '治療', '康復', '醫師', '護理師']
        for response in responses:
            if any(term in response for term in medical_terms):
                analysis['contains_medical_terms'] = True
                break
        
        # 檢查自我介紹模式
        self_intro_patterns = ['我是Patient_1', '您好，我是', '口腔癌病患']
        for response in responses:
            if any(pattern in response for pattern in self_intro_patterns):
                analysis['contains_self_introduction'] = True
                break
        
        # 檢查通用回應
        generic_patterns = ['沒有完全理解', '換個方式說明', '需要什麼幫助']
        for response in responses:
            if any(pattern in response for pattern in generic_patterns):
                analysis['contains_generic_phrases'] = True
                break
        
        # 計算回應多樣性（簡單字符相似度）
        if len(responses) > 1:
            unique_chars = set(''.join(responses))
            total_chars = len(''.join(responses))
            analysis['response_diversity'] = len(unique_chars) / max(total_chars, 1)
        
        return analysis
    
    def _analyze_reasoning_content(self, reasoning: str) -> Dict[str, Any]:
        """分析推理內容"""
        
        analysis = {
            'length': len(reasoning),
            'contains_character_awareness': False,
            'contains_medical_context': False,
            'contains_systematic_thinking': False,
            'reasoning_depth_score': 0
        }
        
        # 檢查角色意識
        character_terms = ['病患', '角色', 'Patient_1', '口腔癌']
        if any(term in reasoning for term in character_terms):
            analysis['contains_character_awareness'] = True
        
        # 檢查醫療情境意識
        medical_context_terms = ['醫療', '手術', '術後', '症狀', '查房']
        if any(term in reasoning for term in medical_context_terms):
            analysis['contains_medical_context'] = True
        
        # 檢查系統性思考
        systematic_patterns = ['考慮到', '基於', '分析', '評估', '根據']
        if any(pattern in reasoning for pattern in systematic_patterns):
            analysis['contains_systematic_thinking'] = True
        
        # 計算推理深度分數
        depth_indicators = [
            analysis['contains_character_awareness'],
            analysis['contains_medical_context'],
            analysis['contains_systematic_thinking'],
            len(reasoning) > 50,
            '因為' in reasoning or '所以' in reasoning
        ]
        analysis['reasoning_depth_score'] = sum(depth_indicators) / len(depth_indicators)
        
        return analysis
    
    def _detect_round_degradation(self, api_response: Dict[str, Any], 
                                analysis_results: Dict[str, Any]) -> bool:
        """檢測輪次退化"""
        
        degradation_indicators = []
        
        # 檢查基本退化指標
        if analysis_results['basic_info']['response_count'] < 3:
            degradation_indicators.append('low_response_count')
        
        if analysis_results.get('content_analysis', {}).get('contains_self_introduction', False):
            degradation_indicators.append('self_introduction')
        
        if analysis_results.get('content_analysis', {}).get('contains_generic_phrases', False):
            degradation_indicators.append('generic_phrases')
        
        # 檢查對話情境退化
        dialogue_context = api_response.get('dialogue_context', '')
        if '一般問診對話' in dialogue_context:
            degradation_indicators.append('context_degradation')
        
        # 檢查推理品質
        reasoning_analysis = analysis_results.get('reasoning_analysis', {})
        if reasoning_analysis.get('reasoning_depth_score', 0) < 0.3:
            degradation_indicators.append('poor_reasoning')
        
        # 檢查監控系統的品質評估
        quality_metrics = analysis_results.get('quality_metrics', {})
        if quality_metrics.get('overall_quality', 1.0) < 0.5:
            degradation_indicators.append('low_overall_quality')
        
        is_degraded = len(degradation_indicators) >= 2
        
        if is_degraded:
            logger.warning(f"🚨 退化檢測: {degradation_indicators}")
        
        return is_degraded
    
    def _calculate_round_quality_score(self, api_response: Dict[str, Any], 
                                     analysis_results: Dict[str, Any]) -> float:
        """計算輪次品質分數"""
        
        # 如果有監控系統的評估，優先使用
        quality_metrics = analysis_results.get('quality_metrics', {})
        if quality_metrics.get('overall_quality') is not None:
            return quality_metrics['overall_quality']
        
        # 否則使用簡單評分
        score = 0.5  # 基礎分數
        
        content_analysis = analysis_results.get('content_analysis', {})
        
        # 回應數量評分
        response_count = analysis_results['basic_info']['response_count']
        if response_count >= 5:
            score += 0.2
        elif response_count >= 3:
            score += 0.1
        else:
            score -= 0.3
        
        # 內容品質評分
        if content_analysis.get('contains_medical_terms', False):
            score += 0.1
        
        if content_analysis.get('contains_self_introduction', False):
            score -= 0.4
        
        if content_analysis.get('contains_generic_phrases', False):
            score -= 0.2
        
        # 推理品質評分
        reasoning_analysis = analysis_results.get('reasoning_analysis', {})
        reasoning_score = reasoning_analysis.get('reasoning_depth_score', 0.5)
        score += reasoning_score * 0.2
        
        return min(max(score, 0.0), 1.0)
    
    def _log_round_results(self, round_analysis: RoundAnalysis):
        """記錄輪次結果"""
        
        logger.info(f"📊 第 {round_analysis.round_number} 輪分析結果:")
        logger.info(f"  ⏱️ 回應時間: {round_analysis.response_time:.2f}s")
        logger.info(f"  📝 回應數量: {round_analysis.analysis_results['basic_info']['response_count']}")
        logger.info(f"  🎯 品質分數: {round_analysis.quality_score:.3f}")
        logger.info(f"  🚨 退化檢測: {'是' if round_analysis.degradation_detected else '否'}")
        logger.info(f"  🌍 對話情境: {round_analysis.analysis_results['basic_info']['dialogue_context']}")
        
        # 顯示回應內容（前兩個）
        responses = round_analysis.api_response.get('responses', [])
        logger.info(f"  💬 回應預覽:")
        for i, response in enumerate(responses[:2], 1):
            logger.info(f"    [{i}] {response}")
        if len(responses) > 2:
            logger.info(f"    ... 共 {len(responses)} 個回應")
        
        # 品質指標詳情
        quality_metrics = round_analysis.analysis_results.get('quality_metrics', {})
        if quality_metrics:
            logger.info(f"  📈 品質指標:")
            for metric, value in quality_metrics.items():
                if isinstance(value, float):
                    logger.info(f"    {metric}: {value:.3f}")
                else:
                    logger.info(f"    {metric}: {value}")
    
    def _generate_comprehensive_report(self):
        """生成綜合分析報告"""
        
        logger.info(f"\n{'='*80}")
        logger.info("📋 DSPy 逐輪對話綜合分析報告")
        logger.info(f"{'='*80}")
        
        if not self.round_analyses:
            logger.warning("⚠️ 無分析數據，無法生成報告")
            return
        
        # 基本統計
        total_rounds = len(self.round_analyses)
        degraded_rounds = sum(1 for r in self.round_analyses if r.degradation_detected)
        avg_quality = sum(r.quality_score for r in self.round_analyses) / total_rounds
        
        logger.info(f"📊 基本統計:")
        logger.info(f"  🔵 總輪次: {total_rounds}")
        logger.info(f"  🔴 退化輪次: {degraded_rounds}")
        logger.info(f"  📈 平均品質: {avg_quality:.3f}")
        logger.info(f"  💯 退化率: {(degraded_rounds/total_rounds)*100:.1f}%")
        
        # 輪次品質趨勢
        logger.info(f"\n📈 輪次品質趨勢:")
        for i, analysis in enumerate(self.round_analyses, 1):
            status = "🔴 退化" if analysis.degradation_detected else "🟢 正常"
            logger.info(f"  第{i}輪: {analysis.quality_score:.3f} {status}")
        
        # 退化檢測總結
        if degraded_rounds > 0:
            first_degradation = next(
                (i+1 for i, r in enumerate(self.round_analyses) if r.degradation_detected),
                None
            )
            logger.info(f"\n🚨 退化分析:")
            logger.info(f"  🎯 首次退化: 第 {first_degradation} 輪")
            logger.info(f"  📉 退化模式: 持續性退化" if degraded_rounds > 1 else "  📉 退化模式: 單次退化")
        
        # 回應時間分析
        response_times = [r.response_time for r in self.round_analyses]
        logger.info(f"\n⏱️ 回應時間分析:")
        logger.info(f"  平均: {sum(response_times)/len(response_times):.2f}s")
        logger.info(f"  最快: {min(response_times):.2f}s")
        logger.info(f"  最慢: {max(response_times):.2f}s")
        
        # 內容分析摘要
        self._generate_content_analysis_summary()
        
        # 建議和結論
        self._generate_recommendations()
        
        logger.info(f"{'='*80}")
    
    def _generate_content_analysis_summary(self):
        """生成內容分析摘要"""
        
        logger.info(f"\n💬 內容分析摘要:")
        
        # 統計各項指標
        self_intro_count = sum(
            1 for r in self.round_analyses 
            if r.analysis_results.get('content_analysis', {}).get('contains_self_introduction', False)
        )
        
        generic_count = sum(
            1 for r in self.round_analyses
            if r.analysis_results.get('content_analysis', {}).get('contains_generic_phrases', False)
        )
        
        medical_terms_count = sum(
            1 for r in self.round_analyses
            if r.analysis_results.get('content_analysis', {}).get('contains_medical_terms', False)
        )
        
        logger.info(f"  🏥 醫療詞彙出現: {medical_terms_count}/{len(self.round_analyses)} 輪")
        logger.info(f"  👋 自我介紹模式: {self_intro_count}/{len(self.round_analyses)} 輪")
        logger.info(f"  🤖 通用回應模式: {generic_count}/{len(self.round_analyses)} 輪")
        
        # 回應數量統計
        response_counts = [
            r.analysis_results['basic_info']['response_count'] 
            for r in self.round_analyses
        ]
        avg_responses = sum(response_counts) / len(response_counts)
        logger.info(f"  📝 平均回應數量: {avg_responses:.1f}")
    
    def _generate_recommendations(self):
        """生成建議和結論"""
        
        logger.info(f"\n💡 分析建議:")
        
        degraded_rounds = sum(1 for r in self.round_analyses if r.degradation_detected)
        
        if degraded_rounds == 0:
            logger.info("  ✅ 未檢測到退化問題，對話品質保持穩定")
        else:
            first_degradation = next(
                (i+1 for i, r in enumerate(self.round_analyses) if r.degradation_detected),
                None
            )
            
            logger.info(f"  🚨 檢測到退化問題，首次出現在第 {first_degradation} 輪")
            
            if first_degradation and first_degradation >= 4:
                logger.info("  📋 建議重點關注第4-5輪的退化預防機制")
            
            # 檢查是否有自我介紹模式
            self_intro_detected = any(
                r.analysis_results.get('content_analysis', {}).get('contains_self_introduction', False)
                for r in self.round_analyses
            )
            
            if self_intro_detected:
                logger.info("  🔧 建議加強角色一致性檢查機制")
            
            # 檢查回應數量問題
            low_response_rounds = sum(
                1 for r in self.round_analyses 
                if r.analysis_results['basic_info']['response_count'] < 3
            )
            
            if low_response_rounds > 0:
                logger.info("  📝 建議優化回應生成數量控制")
        
        # 保存詳細報告到文件
        self._save_detailed_report()
    
    def _save_detailed_report(self):
        """保存詳細報告到文件"""
        
        report_filename = f"round_by_round_analysis_report_{int(time.time())}.json"
        
        report_data = {
            'session_id': self.session_id,
            'timestamp': datetime.now().isoformat(),
            'test_sequence': self.test_sequence,
            'character_config': self.character_config,
            'summary': {
                'total_rounds': len(self.round_analyses),
                'degraded_rounds': sum(1 for r in self.round_analyses if r.degradation_detected),
                'average_quality': sum(r.quality_score for r in self.round_analyses) / len(self.round_analyses) if self.round_analyses else 0,
                'first_degradation_round': next(
                    (i+1 for i, r in enumerate(self.round_analyses) if r.degradation_detected),
                    None
                )
            },
            'round_analyses': [
                {
                    'round_number': r.round_number,
                    'user_input': r.user_input,
                    'response_time': r.response_time,
                    'quality_score': r.quality_score,
                    'degradation_detected': r.degradation_detected,
                    'analysis_results': r.analysis_results,
                    'api_response': r.api_response,
                    'timestamp': r.timestamp
                }
                for r in self.round_analyses
            ]
        }
        
        try:
            with open(report_filename, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"📄 詳細報告已保存: {report_filename}")
            
        except Exception as e:
            logger.error(f"❌ 報告保存失敗: {str(e)}")


def main():
    """主函數"""
    print("🔍 DSPy 逐輪分析測試工具")
    print("=" * 50)
    
    analyzer = RoundByRoundAnalyzer()
    
    try:
        # 執行逐輪分析測試
        analyses = analyzer.run_round_by_round_test()
        
        print(f"\n✅ 分析完成！共分析 {len(analyses)} 輪對話")
        print("📄 詳細日誌請查看: round_by_round_analysis.log")
        
        return analyses
        
    except KeyboardInterrupt:
        print("\n⚠️ 測試被用戶中斷")
    except Exception as e:
        print(f"\n❌ 測試過程發生錯誤: {str(e)}")
        logger.error(f"測試失敗: {str(e)}", exc_info=True)
    
    return []


if __name__ == "__main__":
    main()