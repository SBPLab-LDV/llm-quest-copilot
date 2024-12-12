# 口腔癌病患對話系統 API 文檔
版本：v0.0.1

## API 概述
此 API 提供與口腔癌病患虛擬角色的對話功能，可獲取病患的回應選項及相關狀態信息。

## 基礎信息
- 基礎URL：`https://api.example.com/v1`
- 認證方式：Bearer Token
- 響應格式：JSON
- 字符編碼：UTF-8

## API 端點

### 1. 獲取可用病患列表
獲取系統中所有可用的虛擬病患信息。

#### 請求
```http
GET /characters
```

#### 響應示例
```json
{
    "status": "success",
    "data": {
        "characters": [
            {
                "id": "patient_001",
                "name": "王大明",
                "persona": "65歲男性，口腔癌患者",
                "backstory": "重度吸菸者，初次診斷為口腔癌第二期"
            }
        ]
    }
}
```

### 2. 獲取對話回應選項
根據用戶輸入獲取病患的回應選項。

#### 請求
```http
POST /dialogue/options
```

#### 請求參數
```json
{
    "character_id": "patient_001",
    "user_input": "您好，我是您的護理師",
    "dialogue_state": "INITIAL",  // 可選，如果是新對話可以不傳
    "conversation_history": []    // 可選，歷史對話記錄
}
```

#### 響應示例 1（疼痛管理情境）
```json
{
    "status": "success",
    "data": {
        "current_state": "PAIN_DISTRESSED",
        "options": [
            {
                "id": 1,
                "text": "最痛的是右邊舌頭這裡，尤其是吞嚥的時候特別痛...",
                "type": "pain_description"
            },
            {
                "id": 2,
                "text": "止痛藥我都有按時吃，可是好像沒什麼效果...",
                "type": "medication_response"
            },
            {
                "id": 3,
                "text": "我現在只能吃流質食物，固體食物完全沒辦法吃...",
                "type": "eating_difficulty"
            },
            {
                "id": 4,
                "text": "痛到沒辦法睡覺，整個人都很疲憊...",
                "type": "impact_daily_life"
            },
            {
                "id": 5,
                "text": "我很害怕這個疼痛會一直持續下去...",
                "type": "emotional_expression"
            },
            {
                "id": 0,
                "text": "...",
                "type": "skip"
            }
        ]
    }
}
```

#### 響應示例 2（復發焦慮情境）
```json
{
    "status": "success",
    "data": {
        "current_state": "ANXIETY",
        "options": [
            {
                "id": 1,
                "text": "傷口這幾天變得比較紅腫，而且會有刺痛感...",
                "type": "symptom_description"
            },
            {
                "id": 2,
                "text": "我每天都有做清潔，但還是覺得好像越來越嚴重...",
                "type": "self_care_concern"
            },
            {
                "id": 3,
                "text": "上次治療的時候醫生說要注意這些症狀，所以我特別緊張...",
                "type": "previous_experience"
            },
            {
                "id": 4,
                "text": "我最近都不太敢吃東西，怕會刺激到傷口...",
                "type": "behavioral_change"
            },
            {
                "id": 5,
                "text": "每次照鏡子看到傷口，我就會想到會不會又復發了...",
                "type": "fear_expression"
            },
            {
                "id": 0,
                "text": "...",
                "type": "skip"
            }
        ]
    }
}
```

## 錯誤碼說明
| 錯誤碼 | 說明 |
|--------|------|
| 400 | 請求參數錯誤 |
| 401 | 未授權訪問 |
| 404 | 資源不存在 |
| 500 | 服務器內部錯誤 |

## 使用限制
- 請求頻率限制：60次/分鐘
- 最大請求大小：1MB
- Token有效期：24小時

## 更新日誌
### v0.0.1 (2024-12-12)
- 初始版本發布
- 支持基礎對話功能
- 提供病患列表查詢 