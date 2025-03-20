# 口腔癌病患對話系統 API 參考文檔

## API 概述

- **基礎 URL**: `http://[server-address]:8000`
- **API 版本**: v1
- **內容類型**: `application/json` (除非另有說明)
- **認證方式**: 無 (預留用於未來實現)

---

## API 視覺化

為了幫助您更好地理解 API 的工作流程和系統架構，我們提供了一系列視覺化圖表。
請查看 [API 視覺化文檔](./api_visualization_zh.md) 了解更多詳情。

---

## 端點列表

### GET /api/characters

獲取所有可用的病患角色。

#### 請求

```http
GET /api/characters HTTP/1.1
Host: [server-address]:8000
```

#### 回應

`200 OK`

```json
{
  "characters": {
    "1": {
      "name": "病患 1",
      "age": 55,
      "background": "口腔癌病患...",
      "persona": "...",
      "goal": "..."
    },
    "2": {
      "name": "病患 2",
      "age": 60,
      "background": "...",
      "persona": "...",
      "goal": "..."
    }
  }
}
```

---

### POST /api/dialogue/text

發送文本進行對話。

#### 請求

```http
POST /api/dialogue/text HTTP/1.1
Host: [server-address]:8000
Content-Type: application/json

{
  "text": "您今天感覺如何?",
  "character_id": "1",
  "session_id": null,
  "response_format": "text"
}
```

| 參數 | 類型 | 必需 | 描述 |
|------|------|------|------|
| `text` | string | 是 | 護理人員輸入的文本 |
| `character_id` | string | 是 | 病患角色ID |
| `session_id` | string | 否 | 現有會話ID；如為 null 將創建新會話 |
| `response_format` | string | 否 | 回覆格式，可選值："text"（默認）或 "audio" |

#### 使用情境

本端點支持以下兩種使用情境：

1. **文本輸入，文本回覆**（默認）：發送文本，獲取JSON格式的文本回應
2. **文本輸入，音頻回覆**：發送文本，獲取WAV格式的音頻回應

#### 回應

當 `response_format` 為 "text" 時（默認）：

`200 OK`
Content-Type: application/json

```json
{
  "status": "success",
  "responses": [
    "醫生早，右臉頰傷口那邊還是有點腫，而且黃色的分泌物還是有。",
    "醫生，早安。傷口紅腫的情況好像沒有改善，分泌物也一樣。",
    "早安，醫生。臉頰的傷口感覺不太舒服，紅腫跟分泌物都還在。"
  ],
  "state": "NORMAL",
  "dialogue_context": "醫師查房",
  "session_id": "d8334f87-7d85-4d84-8101-6461e230c501"
}
```

當 `response_format` 為 "audio" 時：

`200 OK`
Content-Type: audio/wav
X-Session-ID: [會話ID]

[二進制音頻數據]

#### 錯誤回應

`400 Bad Request`

```json
{
  "detail": "必須提供 text 參數"
}
```

`400 Bad Request`

```json
{
  "detail": "創建新會話需要提供 character_id"
}
```

---

### POST /api/dialogue/audio

通過音頻進行對話。

#### 請求

```http
POST /api/dialogue/audio HTTP/1.1
Host: [server-address]:8000
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW

------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="audio_file"; filename="recording.wav"
Content-Type: audio/wav

[二進制音頻數據]
------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="character_id"

1
------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="session_id"

d8334f87-7d85-4d84-8101-6461e230c501
------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="response_format"

text
------WebKitFormBoundary7MA4YWxkTrZu0gW--
```

| 參數 | 類型 | 必需 | 描述 |
|------|------|------|------|
| `audio_file` | file | 是 | 音頻文件 (WAV格式) |
| `character_id` | string | 是 | 病患角色ID |
| `session_id` | string | 否 | 現有會話ID；如為空將創建新會話 |
| `response_format` | string | 否 | 回覆格式，可選值："text"（默認）或 "audio" |

#### 使用情境

本端點支持以下兩種使用情境：

1. **音頻輸入，文本回覆**（默認）：上傳音頻，獲取JSON格式的文本回應
2. **音頻輸入，音頻回覆**：上傳音頻，獲取WAV格式的音頻回應

對於情境2（音頻輸入，音頻回覆），在請求中添加 `response_format=audio` 參數：

```http
POST /api/dialogue/audio HTTP/1.1
Host: [server-address]:8000
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW

------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="audio_file"; filename="recording.wav"
Content-Type: audio/wav

[二進制音頻數據]
------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="character_id"

1
------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="session_id"

d8334f87-7d85-4d84-8101-6461e230c501
------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="response_format"

audio
------WebKitFormBoundary7MA4YWxkTrZu0gW--
```

這將返回一個音頻文件（WAV格式）作為回應，而不是JSON。

#### 回應

當 `response_format` 為 "text" 時（默認）：

`200 OK`
Content-Type: application/json

```json
{
  "status": "success",
  "responses": [
    "醫生早，右臉頰傷口那邊還是有點腫，而且黃色的分泌物還是有。"
  ],
  "state": "NORMAL",
  "dialogue_context": "醫師查房",
  "session_id": "d8334f87-7d85-4d84-8101-6461e230c501"
}
```

當 `response_format` 為 "audio" 時：

`200 OK`
Content-Type: audio/wav
X-Session-ID: [會話ID]

[二進制音頻數據]

#### 錯誤回應

`400 Bad Request`

```json
{
  "detail": "音頻處理失敗: [錯誤詳情]"
}
```

---

### GET /api/health

檢查API服務健康狀態。

#### 請求

```http
GET /api/health HTTP/1.1
Host: [server-address]:8000
```

#### 回應

`200 OK`

```json
{
  "status": "ok",
  "active_sessions": 5
}
```

---

## 狀態碼

| 狀態碼 | 描述 |
|--------|------|
| 200 | 成功 |
| 400 | 請求參數錯誤 |
| 404 | 未找到請求的資源 |
| 500 | 服務器內部錯誤 |

---

## 對話狀態

對話回應中的 `state` 欄位可能有以下值：

| 狀態 | 描述 |
|------|------|
| `NORMAL` | 正常對話狀態 |
| `CONFUSED` | 病患感到困惑 |
| `ANXIOUS` | 病患感到焦慮 |
| `ANGRY` | 病患感到憤怒 |

---

## 輸入/輸出組合

下表總結了可用的輸入和輸出組合：

| 輸入類型 | 輸出類型 | API 端點 | 參數設置 |
|---------|---------|---------|---------|
| 文本 | 文本 (JSON) | `/api/dialogue/text` | `response_format="text"` (默認) |
| 文本 | 音頻 (WAV) | `/api/dialogue/text` | `response_format="audio"` |
| 音頻 | 文本 (JSON) | `/api/dialogue/audio` | `response_format="text"` (默認) |
| 音頻 | 音頻 (WAV) | `/api/dialogue/audio` | `response_format="audio"` |

---

## 客戶端代碼示例

### Python

```python
import requests
import json

# 文本對話 (獲取文本回覆)
def text_dialogue(text, character_id, session_id=None):
    url = "http://localhost:8000/api/dialogue/text"
    data = {
        "text": text,
        "character_id": character_id,
        "session_id": session_id,
        "response_format": "text"  # 明確指定文本回覆
    }
    response = requests.post(url, json=data)
    return response.json()

# 文本對話 (獲取音頻回覆)
def text_dialogue_with_audio(text, character_id, session_id=None):
    url = "http://localhost:8000/api/dialogue/text"
    data = {
        "text": text,
        "character_id": character_id,
        "session_id": session_id,
        "response_format": "audio"  # 請求音頻回覆
    }
    response = requests.post(url, json=data)
    
    # 檢查回應類型
    if response.headers.get('Content-Type') == 'audio/wav':
        # 從頭部獲取會話ID
        session_id = response.headers.get('X-Session-ID')
        
        # 保存音頻
        audio_filename = f"response_{hash(text)}.wav"
        with open(audio_filename, "wb") as f:
            f.write(response.content)
            
        return {
            "status": "success",
            "audio_file": audio_filename,
            "session_id": session_id
        }
    else:
        # 如果不是音頻回應，可能是錯誤
        return response.json()

# 音頻對話 (獲取文本回覆)
def audio_dialogue(audio_file_path, character_id, session_id=None, response_format="text"):
    url = "http://localhost:8000/api/dialogue/audio"
    
    with open(audio_file_path, "rb") as audio_file:
        files = {"audio_file": audio_file}
        data = {
            "character_id": character_id,
            "response_format": response_format
        }
        
        if session_id:
            data["session_id"] = session_id
            
        response = requests.post(url, files=files, data=data)
        
        # 如果請求音頻回覆
        if response_format == "audio" and response.headers.get('Content-Type') == 'audio/wav':
            # 從頭部獲取會話ID
            session_id = response.headers.get('X-Session-ID')
            
            # 保存音頻
            audio_filename = f"response_audio_{hash(audio_file_path)}.wav"
            with open(audio_filename, "wb") as f:
                f.write(response.content)
                
            return {
                "status": "success",
                "audio_file": audio_filename,
                "session_id": session_id
            }
        else:
            # 文本回覆或錯誤
            return response.json()

# 使用示例: 文本輸入，文本回覆
text_result = text_dialogue("您今天感覺如何?", "1")
session_id = text_result["session_id"]
print(f"病患回應: {text_result['responses'][0]}")

# 使用示例: 文本輸入，音頻回覆
audio_response = text_dialogue_with_audio("請說說您的傷口狀況", "1", session_id)
if "audio_file" in audio_response:
    print(f"音頻回覆已保存至: {audio_response['audio_file']}")
    session_id = audio_response["session_id"]

# 使用示例: 音頻輸入，文本回覆
audio_text_result = audio_dialogue("recording.wav", "1", session_id)
print(f"病患回應: {audio_text_result['responses'][0]}")

# 使用示例: 音頻輸入，音頻回覆
audio_audio_result = audio_dialogue("recording.wav", "1", session_id, response_format="audio")
if "audio_file" in audio_audio_result:
    print(f"音頻回覆已保存至: {audio_audio_result['audio_file']}")
    # 可以播放音頻或進行其他處理
```

### JavaScript

```javascript
// 文本對話 (文本回覆)
async function textDialogue(text, characterId, sessionId = null) {
  const response = await fetch("http://localhost:8000/api/dialogue/text", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      text: text,
      character_id: characterId,
      session_id: sessionId,
      response_format: "text"
    })
  });
  return await response.json();
}

// 文本對話 (音頻回覆)
async function textDialogueWithAudio(text, characterId, sessionId = null) {
  const response = await fetch("http://localhost:8000/api/dialogue/text", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      text: text,
      character_id: characterId,
      session_id: sessionId,
      response_format: "audio"
    })
  });
  
  // 檢查響應類型
  if (response.headers.get('Content-Type') === 'audio/wav') {
    // 獲取會話ID
    const sessionId = response.headers.get('X-Session-ID');
    
    // 創建音頻 URL 並播放
    const blob = await response.blob();
    const audioUrl = URL.createObjectURL(blob);
    
    // 播放音頻
    const audio = new Audio(audioUrl);
    audio.play();
    
    return {
      status: "success",
      audioUrl: audioUrl,
      sessionId: sessionId
    };
  } else {
    // 處理錯誤
    return await response.json();
  }
}

// 音頻對話 (文本或音頻回覆)
async function audioDialogue(audioFile, characterId, sessionId = null, responseFormat = "text") {
  const formData = new FormData();
  formData.append("audio_file", audioFile);
  formData.append("character_id", characterId);
  formData.append("response_format", responseFormat);
  
  if (sessionId) {
    formData.append("session_id", sessionId);
  }
  
  const response = await fetch("http://localhost:8000/api/dialogue/audio", {
    method: "POST",
    body: formData
  });
  
  // 如果請求音頻回覆
  if (responseFormat === "audio" && response.headers.get('Content-Type') === 'audio/wav') {
    // 獲取會話ID
    const sessionId = response.headers.get('X-Session-ID');
    
    // 創建音頻 URL 並播放
    const blob = await response.blob();
    const audioUrl = URL.createObjectURL(blob);
    
    // 播放音頻
    const audio = new Audio(audioUrl);
    audio.play();
    
    return {
      status: "success",
      audioUrl: audioUrl,
      sessionId: sessionId
    };
  } else {
    // 文本回覆或錯誤
    return await response.json();
  }
}

// 使用示例
async function dialogueExample() {
  // 文本輸入，文本回覆
  const textResult = await textDialogue("您今天感覺如何?", "1");
  console.log(`病患回應: ${textResult.responses[0]}`);
  
  // 使用返回的會話ID繼續對話
  const sessionId = textResult.session_id;
  
  // 文本輸入，音頻回覆
  const audioResponse = await textDialogueWithAudio("請說說您的傷口狀況", "1", sessionId);
  if (audioResponse.status === "success") {
    console.log(`正在播放音頻回覆，會話ID: ${audioResponse.sessionId}`);
  }
  
  // 音頻輸入，文本回覆
  const audioInput = document.getElementById('audioInput');
  if (audioInput && audioInput.files.length > 0) {
    const audioTextResult = await audioDialogue(audioInput.files[0], "1", sessionId);
    console.log(`病患回應: ${audioTextResult.responses[0]}`);
    
    // 音頻輸入，音頻回覆
    const audioAudioResult = await audioDialogue(audioInput.files[0], "1", sessionId, "audio");
    if (audioAudioResult.status === "success") {
      console.log(`正在播放音頻回覆，音頻URL: ${audioAudioResult.audioUrl}`);
    }
  }
}
```

---

## 會話生命週期

1. 新會話在首次請求時創建（不提供 `session_id` 或提供 `null`）
2. 使用返回的 `session_id` 進行後續請求以維持對話連續性
3. 會話在閒置 1 小時後自動終止

---

## 限制與建議

- 音頻文件必須是 WAV 格式，建議採樣率 16kHz 或以上
- 每段音頻不應超過 60 秒
- 同一用戶的連續請求應使用相同的 `session_id`
- 當 `state` 為 `CONFUSED` 時，建議簡化提問或換一種表達方式
- 獲取音頻回覆時，記得從 HTTP 頭部的 `X-Session-ID` 提取會話 ID 