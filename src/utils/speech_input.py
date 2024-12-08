import speech_recognition as sr
from google.cloud import speech_v1
import pyaudio
import wave
import os
import keyboard
import threading
import numpy as np
from datetime import datetime
from typing import Optional, Tuple

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
        
        # 只在需要保存錄音時創建目錄
        if self.save_recordings:
            self.recordings_dir = 'recordings'
            os.makedirs(self.recordings_dir, exist_ok=True)

    def debug_print(self, message: str):
        """除錯訊息輸出"""
        if self.debug_mode:
            print(f"[DEBUG] {message}")

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

    def record_audio(self, key: str = 'space') -> Optional[str]:
        """按住指定按鍵進行錄音，放開按鍵停止錄音"""
        try:
            # 檢查麥克風
            try:
                sr.Microphone()
            except Exception as e:
                print("\n無法找到麥克風設備，請確認麥克風已正確連接")
                return None

            # 設置錄音參數
            stream = self.audio.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk
            )
            
            self.frames = []
            self.recording = False
            
            # 等待按下按鍵
            keyboard.wait(key, trigger_on_release=False)
            print("\n開始錄音... (放開按鍵結束)")
            self.recording = True
            
            # 開始錄音
            while self.recording:
                if not keyboard.is_pressed(key):
                    self.recording = False
                    break
                try:
                    data = stream.read(self.chunk)
                    self.frames.append(data)
                except Exception as e:
                    self.debug_print(f"Error reading audio chunk: {str(e)}")
            
            print("錄音結束，正在處理...")
            
            # 關閉串流
            stream.stop_stream()
            stream.close()
            
            # 檢查是否有錄到音訊
            if not self.frames:
                print("未檢測到音訊輸入")
                return None
            
            # 將錄音數據轉換為音訊檔
            audio_data = b''.join(self.frames)
            
            # 驗證音訊數據
            if not self.validate_audio_data(audio_data):
                print("音訊數據無效，請重試")
                return None

            # 轉換音訊格式
            try:
                converted_audio = self.convert_audio_format(audio_data)
                self.debug_print("Audio format conversion successful")
            except Exception as e:
                print(f"音訊格式轉換失敗: {e}")
                return None

            # 只在需要時保存錄音
            if self.save_recordings:
                saved_file = self.save_recording(converted_audio)
                print(f"錄音已儲存至: {saved_file}")
                # 使用保存的檔案進行辨識
                with sr.AudioFile(saved_file) as source:
                    audio = self.recognizer.record(source)
            else:
                # 直接使用轉換後的音訊數據進行辨識
                audio = sr.AudioData(converted_audio, self.sample_rate, 2)
            
            self.debug_print("Successfully prepared audio for recognition")
            
            try:
                # 使用 Google Speech Recognition
                text = self.recognizer.recognize_google(audio, language='zh-TW')
                return text
            except sr.UnknownValueError:
                print("無法辨識語音內容，請說話更清晰")
                self.debug_print("Speech recognition failed to understand the audio")
                return None
            except sr.RequestError as e:
                print(f"無法連接到 Google Speech Recognition 服務: {e}")
                return None
                
        except Exception as e:
            print(f"錄音過程發生錯誤: {e}")
            self.debug_print(f"Detailed error: {str(e)}")
            return None
        
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