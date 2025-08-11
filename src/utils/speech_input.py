import speech_recognition as sr
from google.cloud import speech_v1
import pyaudio
import wave
import os
import numpy as np
from datetime import datetime
from typing import Optional, Tuple
import queue

class SpeechInput:
    def __init__(self, google_api_key: str, save_recordings: bool = False, debug_mode: bool = False):
        self.recognizer = sr.Recognizer()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = google_api_key
        self.recording = False
        self.audio = pyaudio.PyAudio()
        self.frames = []
        self.sample_rate = 16000
        self.chunk = 1024
        self.debug_mode = debug_mode
        self.save_recordings = save_recordings
        self.audio_queue = queue.Queue()
        
        # 只在需要保存錄音時創建目錄
        if self.save_recordings:
            self.recordings_dir = 'recordings'
            os.makedirs(self.recordings_dir, exist_ok=True)

    def debug_print(self, message: str):
        """除錯訊息輸出"""
        if self.debug_mode:
            print(f"[DEBUG] {message}")

    def start_recording(self):
        """開始錄音"""
        try:
            # 設置錄音參數
            self.stream = self.audio.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk,
                stream_callback=self._audio_callback
            )
            
            self.frames = []
            self.recording = True
            self.stream.start_stream()
            
        except Exception as e:
            self.debug_print(f"開始錄音時發生錯誤: {str(e)}")
            raise

    def stop_recording(self) -> Optional[str]:
        """停止錄音並進行語音識別"""
        try:
            if not self.recording:
                return None
                
            self.recording = False
            self.stream.stop_stream()
            self.stream.close()
            
            # 檢查是否有錄到音訊
            if not self.frames:
                self.debug_print("未檢測到音訊輸入")
                return None
            
            # 將錄音數據轉換為音訊檔
            audio_data = b''.join(self.frames)
            
            # 驗證音訊數據
            if not self.validate_audio_data(audio_data):
                self.debug_print("音訊數據無效")
                return None
            
            # 轉換音訊格式
            try:
                converted_audio = self.convert_audio_format(audio_data)
                self.debug_print("音訊格式轉換成功")
            except Exception as e:
                self.debug_print(f"音訊格式轉換失敗: {e}")
                return None
            
            # 保存錄音（如果需要）
            if self.save_recordings:
                saved_file = self.save_recording(converted_audio)
                self.debug_print(f"錄音已保存至: {saved_file}")
                # 使用保存的檔案進行辨識
                with sr.AudioFile(saved_file) as source:
                    audio = self.recognizer.record(source)
            else:
                # 直接使用轉換後的音訊數據進行辨識
                audio = sr.AudioData(converted_audio, self.sample_rate, 2)
            
            try:
                # 使用 Google Speech Recognition
                text = self.recognizer.recognize_google(audio, language='zh-TW')
                return text
            except sr.UnknownValueError:
                self.debug_print("無法辨識語音內容")
                return None
            except sr.RequestError as e:
                self.debug_print(f"無法連接到 Google Speech Recognition 服務: {e}")
                return None
                
        except Exception as e:
            self.debug_print(f"停止錄音時發生錯誤: {str(e)}")
            return None
        finally:
            self.frames = []

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """音訊回調函數"""
        if self.recording:
            self.frames.append(in_data)
        return (in_data, pyaudio.paContinue)

    def convert_audio_format(self, audio_data: bytes) -> bytes:
        """轉換音訊格式並進行檢查"""
        try:
            # 將 bytes 轉換為 numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.float32)
            self.debug_print(f"Original audio shape: {audio_array.shape}, dtype: {audio_array.dtype}")
            self.debug_print(f"Audio range: min={np.min(audio_array)}, max={np.max(audio_array)}")

            # 確保音訊值在 [-1, 1] 範圍內
            if np.max(np.abs(audio_array)) > 1.0:
                audio_array = np.clip(audio_array, -1.0, 1.0)
                self.debug_print("Audio values clipped to [-1, 1] range")

            # 轉換為 16-bit PCM
            audio_array_int = (audio_array * 32767).astype(np.int16)
            self.debug_print(f"Converted audio shape: {audio_array_int.shape}, dtype: {audio_array_int.dtype}")
            
            return audio_array_int.tobytes()
        except Exception as e:
            self.debug_print(f"Audio conversion error: {str(e)}")
            raise

    def validate_audio_data(self, audio_data: bytes) -> bool:
        """驗證音訊數據"""
        try:
            audio_array = np.frombuffer(audio_data, dtype=np.float32)
            
            # 檢查是否有有效數據
            if len(audio_array) == 0:
                self.debug_print("Empty audio data")
                return False
                
            # 檢查是否有非法值
            if np.any(np.isnan(audio_array)) or np.any(np.isinf(audio_array)):
                self.debug_print("Audio contains NaN or Inf values")
                return False
                
            # 檢查音訊振幅
            max_amplitude = np.max(np.abs(audio_array))
            self.debug_print(f"Maximum amplitude: {max_amplitude}")
            if max_amplitude < 0.001:  # 幾乎沒有聲音
                self.debug_print("Audio signal too weak")
                return False
                
            return True
        except Exception as e:
            self.debug_print(f"Audio validation error: {str(e)}")
            return False

    def save_recording(self, audio_data: bytes) -> str:
        """儲存錄音檔案"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.recordings_dir, f'recording_{timestamp}.wav')
        
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data)
            
        return filename

    def __del__(self):
        """清理音訊資源"""
        self.audio.terminate()