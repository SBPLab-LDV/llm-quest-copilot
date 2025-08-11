#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音頻處理工具模組，提供各種音頻處理功能來優化語音識別。
"""

import os
import logging
import numpy as np
import tempfile
import uuid
from scipy.io import wavfile
from typing import Tuple, Optional

# 設置日誌
logger = logging.getLogger(__name__)

def check_audio_format(file_path: str) -> bool:
    """檢查音頻文件是否為有效的 WAV 格式
    
    Args:
        file_path: 音頻文件路徑
    
    Returns:
        是否為有效的 WAV 格式
    """
    try:
        # 使用 scipy.io.wavfile 讀取音頻
        sample_rate, audio_data = wavfile.read(file_path)
        logger.debug(f"音頻檢查: 採樣率={sample_rate}Hz, 形狀={audio_data.shape}")
        return True
    except Exception as e:
        logger.error(f"音頻格式檢查失敗: {e}")
        return False

def preprocess_audio(input_file: str, output_file: Optional[str] = None) -> str:
    """預處理音頻文件以優化語音識別
    
    處理步驟:
    1. 標準化採樣率至 16kHz
    2. 轉換為單聲道
    3. 正規化音量
    4. 簡單降噪
    
    Args:
        input_file: 輸入音頻文件路徑
        output_file: 輸出音頻文件路徑 (如果未提供，將自動生成)
    
    Returns:
        處理後的音頻文件路徑
    """
    logger.info(f"開始預處理音頻文件: {input_file}")
    
    # 如果未提供輸出文件路徑，生成臨時文件
    if not output_file:
        output_file = f"processed_audio_{uuid.uuid4()}.wav"
    
    try:
        # 讀取原始音頻
        sample_rate, audio_data = wavfile.read(input_file)
        logger.debug(f"原始音頻: 採樣率={sample_rate}Hz, 形狀={audio_data.shape}")
        
        # 轉換為單聲道 (如果是多聲道)
        if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
            logger.debug(f"將多聲道音頻轉換為單聲道")
            audio_data = np.mean(audio_data, axis=1).astype(audio_data.dtype)
        
        # 標準化採樣率 (如果需要)
        target_sample_rate = 16000  # 16kHz 是語音識別的標準採樣率
        if sample_rate != target_sample_rate:
            logger.debug(f"轉換採樣率: {sample_rate}Hz -> {target_sample_rate}Hz")
            # 簡化的採樣率轉換 (實際實現可能需要更複雜的重採樣)
            audio_data = _resample(audio_data, sample_rate, target_sample_rate)
            sample_rate = target_sample_rate
        
        # 正規化音量
        logger.debug("正規化音頻音量")
        audio_data = _normalize_volume(audio_data)
        
        # 簡單降噪 (可選)
        # audio_data = _simple_noise_reduction(audio_data)
        
        # 保存處理後的音頻
        wavfile.write(output_file, sample_rate, audio_data)
        logger.info(f"音頻預處理完成，已保存至: {output_file}")
        
        return output_file
        
    except Exception as e:
        logger.error(f"音頻預處理失敗: {e}", exc_info=True)
        # 如果處理失敗，返回原始文件
        return input_file

def _normalize_volume(audio_data: np.ndarray) -> np.ndarray:
    """正規化音頻音量
    
    Args:
        audio_data: 音頻數據數組
    
    Returns:
        正規化後的音頻數據
    """
    # 獲取音頻類型的最大值
    max_possible = np.iinfo(audio_data.dtype).max
    
    # 計算目標峰值 (使用最大可能值的 70%)
    target_peak = 0.7 * max_possible
    
    # 找出當前峰值
    current_peak = np.max(np.abs(audio_data))
    
    # 避免除零錯誤
    if current_peak == 0:
        return audio_data
    
    # 計算縮放因子
    scale_factor = target_peak / current_peak
    
    # 應用縮放
    normalized_audio = (audio_data * scale_factor).astype(audio_data.dtype)
    
    return normalized_audio

def _resample(audio_data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """簡單的重採樣實現 (線性插值)
    
    注意: 對於生產環境，建議使用專門的音頻處理庫如 librosa 進行重採樣
    
    Args:
        audio_data: 原始音頻數據
        orig_sr: 原始採樣率
        target_sr: 目標採樣率
    
    Returns:
        重採樣後的音頻數據
    """
    # 計算時間軸
    orig_duration = len(audio_data) / orig_sr
    
    # 計算目標長度
    target_length = int(orig_duration * target_sr)
    
    # 創建新的時間點
    orig_times = np.arange(len(audio_data)) / orig_sr
    target_times = np.arange(target_length) / target_sr
    
    # 線性插值
    try:
        from scipy import interpolate
        interp_func = interpolate.interp1d(
            orig_times, 
            audio_data, 
            bounds_error=False, 
            fill_value=0
        )
        resampled = interp_func(target_times).astype(audio_data.dtype)
        return resampled
    except ImportError:
        # 如果沒有 scipy，使用更簡單的方法
        ratio = len(audio_data) / target_length
        indices = np.round(np.arange(0, len(audio_data), ratio)).astype(int)
        indices = indices[:target_length]  # 確保不超出原數組長度
        resampled = audio_data[indices].astype(audio_data.dtype)
        return resampled 