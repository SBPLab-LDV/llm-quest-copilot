import requests
import json
import os

# 王大華的角色配置
character_config = {
    "name": "王大華",
    "persona": "口腔癌病患",
    "backstory": "此為系統創建的預設角色，正在接受口腔癌治療。",
    "goal": "與醫護人員清楚溝通並了解治療計畫",
    "details": {
        "fixed_settings": {
            "流水編號": "1",
            "姓名": "王大華",
            "性別": "男",
            "目前診斷": "齒齦癌",
            "診斷分期": "pT2N0M0, stage II"
        },
        "floating_settings": {
            "年齡": "69",
            "目前接受治療場所": "病房",
            "目前治療階段": "手術後恢復期-普通病室",
            "目前治療狀態(包含手術、化學治療、放射線治療、同時接受化學和放射線治療、免疫治療之欄位)": "術後照護，傷口護理",
            "腫瘤復發": "無",
            "身高": "173",
            "體重": "76.8",
            "BMI": "25.7",
            "慢性病(可複選)": "高血壓、糖尿病",
            "用藥史": "Doxaben、Metformin、cefazolin",
            "身體功能分數(KPS)": "90",
            "現行職業類型": "受聘僱",
            "現行職業狀態狀況與確診前相比是否改變": "退休",
            "關鍵字": ""
        }
    }
}

def test_audio_input(file_path):
    url = "http://localhost:8000/api/dialogue/audio_input"
    
    if not os.path.exists(file_path):
        print(f"錯誤: 找不到檔案 {file_path}")
        return

    print(f"正在發送音頻檔案: {file_path}")
    
    # 準備 multipart/form-data
    files = {
        'audio_file': (os.path.basename(file_path), open(file_path, 'rb'), 'audio/m4a')
    }
    
    data = {
        'character_id': 'wang_da_hua_test',
        'character_config_json': json.dumps(character_config)
    }

    try:
        response = requests.post(url, files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print("\n--- 測試成功 ---")
            print(f"狀態: {result.get('status')}")
            
            # 顯示轉錄結果 (如果有)
            if 'original_transcription' in result:
                print(f"語音轉錄原文: {result['original_transcription']}")
            
            # 顯示回應選項
            print("\n[AI 回應選項]:")
            for i, resp in enumerate(result.get('responses', []), 1):
                print(f"{i}. {resp}")
                
            print(f"\n完整回應: {json.dumps(result, ensure_ascii=False, indent=2)}")
        else:
            print(f"\n--- 測試失敗 ---")
            print(f"狀態碼: {response.status_code}")
            print(f"錯誤訊息: {response.text}")
            
    except Exception as e:
        print(f"發生例外狀況: {e}")
    finally:
        files['audio_file'][1].close()

if __name__ == "__main__":
    # 假設腳本在 workspace root 執行，且 Recording.m4a 也在 root
    test_audio_input("Recording.m4a")
