# Oral Cancer Patient Dialogue System — API Reference

> **Version**: 0.4.0
> **Base URL**: `http://<host>:8000` (container internal) / `http://<host>:18000` (external mapped port)
> **Content-Type**: `application/json` for text endpoints; `multipart/form-data` for audio endpoints
> **Authentication**: None required (intended for internal / research use)

---

## Table of Contents

- [Quick Start](#quick-start)
- [Endpoints](#endpoints)
  - [Dialogue (Core)](#dialogue-core)
    - [POST /api/dialogue/text](#post-apidialoguetext)
    - [POST /api/dialogue/audio_input](#post-apidialogueaudio_input)
    - [POST /api/dialogue/audio](#post-apidialogueaudio)
    - [POST /api/dialogue/select_response](#post-apidialogueselect_response)
  - [Characters](#characters)
    - [GET /api/characters](#get-apicharacters)
  - [Health & Monitoring](#health--monitoring)
    - [GET /api/health/status](#get-apihealthstatus)
    - [POST /api/health/thresholds](#post-apihealththresholds)
    - [GET /api/monitor/stats](#get-apimonitorstats)
    - [GET /api/monitor/errors](#get-apimonitorerrors)
    - [POST /api/monitor/reset](#post-apimonitorreset)
  - [Debug](#debug)
    - [GET /api/dev/session/{session_id}/history](#get-apidevsessionsession_idhistory)
    - [POST /api/dev/config/set_max_history](#post-apidevconfigset_max_history)
    - [POST /api/debug/start-log](#post-apidebugstart-log)
- [Concepts](#concepts)
  - [Audio Processing Flows](#audio-processing-flows)
  - [Dialogue States](#dialogue-states)
  - [Session Lifecycle](#session-lifecycle)
  - [Supported Audio Formats](#supported-audio-formats)
  - [Response Schema Reference (DialogueResponse)](#response-schema-reference-dialogueresponse)
- [Client Code Examples](#client-code-examples)
  - [curl](#curl)
  - [Python (requests)](#python-requests)
  - [JavaScript (fetch)](#javascript-fetch)
- [Appendix](#appendix)
  - [Status Codes](#status-codes)
  - [Deprecated Endpoints](#deprecated-endpoints)
  - [Changelog](#changelog)

---

## Quick Start

### Text dialogue — simplest call

```bash
curl -X POST http://localhost:18000/api/dialogue/text \
  -H "Content-Type: application/json" \
  -d '{
    "text": "我想了解手術後的注意事項",
    "character_id": "1"
  }'
```

### Audio dialogue (one-step) — recommended for voice input

```bash
curl -X POST http://localhost:18000/api/dialogue/audio_input \
  -F "audio_file=@recording.wav" \
  -F "character_id=1"
```

---

## Endpoints

### Dialogue (Core)

#### POST /api/dialogue/text

Process a text dialogue turn. Creates a new session if `session_id` is not provided.

**Request** (`application/json`)

| Parameter | Type | Required | Description |
|---|---|---|---|
| `text` | string | Yes | Patient's text input |
| `character_id` | string | Yes | Patient character ID (e.g. `"1"`) |
| `session_id` | string | No | Existing session ID. If provided but not found, returns `404`. |
| `character_config` | object \| string | No | Override character definition at runtime. JSON string is also accepted and auto-parsed. See [Character Config](#character-config-object). |

**Response** `200 OK` — [`DialogueResponse`](#response-schema-reference-dialogueresponse)

```json
{
  "status": "success",
  "responses": [
    "手術後傷口要怎麼照顧，可以跟我說一下嗎？",
    "我記得護理師有講過一些注意事項，但有點忘了。",
    "傷口那邊不太舒服，是不是有什麼要特別注意的？",
    "出院之後在家要注意什麼，我想先了解清楚。"
  ],
  "state": "NORMAL",
  "dialogue_context": "術後照護諮詢",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "inferred_speaker_role": null,
  "speech_recognition_options": null,
  "original_transcription": null,
  "raw_transcript": null,
  "keyword_completion": null,
  "implementation_version": "optimized",
  "performance_metrics": {
    "response_time": 2.345,
    "timestamp": "2026-03-04T10:30:00",
    "success": true
  },
  "processing_info": null,
  "logs": {
    "chat_gui": "logs/api/20260304_103000_Patient_1_sess_a1b2c3d4_chat_gui.log",
    "dspy_debug": "logs/api/20260304_103000_Patient_1_sess_a1b2c3d4_dspy_debug.log"
  }
}
```

**Error Responses**

| Code | Condition |
|---|---|
| `400` | Missing `text` or `character_id`; or invalid JSON body |
| `404` | `session_id` provided but not found |
| `500` | Dialogue processing or session creation error |

**curl Example**

```bash
# New session
curl -X POST http://localhost:18000/api/dialogue/text \
  -H "Content-Type: application/json" \
  -d '{"text": "你好，我是病患", "character_id": "1"}'

# Continue existing session
curl -X POST http://localhost:18000/api/dialogue/text \
  -H "Content-Type: application/json" \
  -d '{
    "text": "手術後可以吃什麼？",
    "character_id": "1",
    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }'
```

---

#### POST /api/dialogue/audio_input

**Recommended audio path.** Combined audio transcription and dialogue response in a single call. The server transcribes the audio via Gemini, then immediately processes the transcribed text through the dialogue system and returns the dialogue response.

**Request** (`multipart/form-data`)

| Parameter | Type | Required | Description |
|---|---|---|---|
| `audio_file` | file | Yes | Audio file. See [Supported Audio Formats](#supported-audio-formats). |
| `character_id` | string | Yes | Patient character ID |
| `session_id` | string | No | Existing session ID |
| `character_config_json` | string | No | JSON string of character config override |

**Response** `200 OK` — [`DialogueResponse`](#response-schema-reference-dialogueresponse)

The response includes the dialogue system's reply plus transcription metadata. Since `option_count=0` is used internally, `speech_recognition_options` will be `null` (options generation is skipped for performance):

```json
{
  "status": "success",
  "responses": [
    "我想知道大概多久可以正常吃東西。",
    "恢復的時間會很長嗎？我有點擔心。",
    "每個人恢復的速度應該不一樣吧？",
    "如果恢復得不好，會有什麼狀況？"
  ],
  "state": "NORMAL",
  "dialogue_context": "術後恢復諮詢",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "inferred_speaker_role": null,
  "speech_recognition_options": null,
  "original_transcription": "手術後要多久才能恢復",
  "raw_transcript": null,
  "keyword_completion": null,
  "implementation_version": "optimized",
  "performance_metrics": {
    "response_time": 5.678,
    "timestamp": "2026-03-04T10:31:00",
    "success": true,
    "timing_breakdown": {
      "total_request_s": 8.1234,
      "audio_save_s": 0.0123,
      "transcription_s": 3.4567,
      "dialogue_s": 4.5678,
      "formatting_s": 0.0012
    }
  },
  "processing_info": null,
  "logs": {
    "chat_gui": "logs/api/..._chat_gui.log",
    "dspy_debug": "logs/api/..._dspy_debug.log"
  }
}
```

**Error Responses**

| Code | Condition |
|---|---|
| `400` | Audio file save failure or transcription returned empty |
| `500` | Session error, transcription error, or dialogue processing error |

**curl Example**

```bash
curl -X POST http://localhost:18000/api/dialogue/audio_input \
  -F "audio_file=@patient_question.m4a" \
  -F "character_id=1" \
  -F "session_id=a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

---

#### POST /api/dialogue/audio

Two-step audio flow — **step 1 of 2**. Transcribes audio and returns speech recognition options for the user to choose from. The dialogue system is **not** invoked at this stage. After the user selects an option, call [`/api/dialogue/select_response`](#post-apidialogueselect_response) to continue.

**Request** (`multipart/form-data`)

| Parameter | Type | Required | Description |
|---|---|---|---|
| `audio_file` | file | Yes | Audio file. See [Supported Audio Formats](#supported-audio-formats). |
| `character_id` | string | Yes | Patient character ID |
| `session_id` | string | No | Existing session ID |
| `response_format` | string | No | Reserved. Currently only `"text"` (default) is effective. |
| `character_config_json` | string | No | JSON string of character config override |

**Response** `200 OK` — [`DialogueResponse`](#response-schema-reference-dialogueresponse)

The response state is `WAITING_SELECTION` and includes transcription candidates:

```json
{
  "status": "success",
  "responses": ["請從以下選項中選擇您想表達的內容:"],
  "state": "WAITING_SELECTION",
  "dialogue_context": "語音選項選擇",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "inferred_speaker_role": null,
  "speech_recognition_options": [
    "我口很乾，想喝點水潤喉",
    "口很乾想喝水，可以請您評估我現在能不能喝？",
    "我嘴巴乾乾的想喝水，喝水會不會嗆到？",
    "口乾想喝水，如果不能喝，有其他方式可以舒緩嗎？"
  ],
  "original_transcription": "口很乾，想喝水",
  "raw_transcript": "口...乾...想...水",
  "keyword_completion": [
    {"heard": "口", "completed": "口", "confidence": "high"},
    {"heard": "乾", "completed": "乾", "confidence": "high"},
    {"heard": "想", "completed": "想", "confidence": "high"},
    {"heard": "水", "completed": "喝水", "confidence": "medium"}
  ],
  "implementation_version": "optimized",
  "performance_metrics": {
    "timing_breakdown": {
      "total_request_s": 5.1234,
      "speech_to_text_s": 5.0012,
      "response_prep_s": 0.0034
    }
  },
  "processing_info": null,
  "logs": { "chat_gui": "...", "dspy_debug": "..." }
}
```

**Error Responses**

| Code | Condition |
|---|---|
| `400` | Invalid audio format or audio processing failure |
| `500` | Session creation or transcription error |

**curl Example**

```bash
curl -X POST http://localhost:18000/api/dialogue/audio \
  -F "audio_file=@recording.wav" \
  -F "character_id=1"
```

---

#### POST /api/dialogue/select_response

Two-step audio flow — **step 2 of 2**. After [`/api/dialogue/audio`](#post-apidialogueaudio) returns `WAITING_SELECTION`, call this endpoint with the user's chosen transcription option.

If the selection is recognized as a post-speech-recognition choice, it is recorded without invoking the dialogue model. Otherwise, the selected text is forwarded to the dialogue model for a full dialogue turn.

**Request** (`application/json`)

| Parameter | Type | Required | Description |
|---|---|---|---|
| `session_id` | string | Yes | Session ID from the preceding `/audio` call |
| `selected_response` | string | Yes | The transcription option the user selected |

**Response** `200 OK`

When recognized as a speech-recognition selection (most common case):

```json
{
  "status": "success",
  "message": "語音識別選擇已記錄",
  "responses": ["已記錄您的選擇"],
  "state": "NORMAL",
  "dialogue_context": "語音識別選擇完成"
}
```

When treated as a new dialogue turn (fallback):

```json
{
  "status": "success",
  "message": "回應選擇已記錄",
  "responses": ["護理師的回覆..."],
  "state": "NORMAL",
  "dialogue_context": "一般對話"
}
```

**Error Responses**

| Code | Condition |
|---|---|
| `404` | Session not found |
| `500` | Dialogue processing error |

**curl Example**

```bash
curl -X POST http://localhost:18000/api/dialogue/select_response \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "selected_response": "我想了解手術的流程"
  }'
```

---

### Characters

#### GET /api/characters

Retrieve the list of available patient characters defined in `config/characters.yaml`.

**Request**: No parameters.

**Response** `200 OK`

```json
{
  "status": "success",
  "characters": {
    "1": {
      "name": "王大華",
      "persona": "口腔癌病患",
      "backstory": "此為系統創建的預設角色，正在接受口腔癌治療。"
    },
    "2": {
      "name": "王建中",
      "persona": "口腔癌病患",
      "backstory": "此為系統創建的預設角色，正在接受口腔癌治療。"
    }
  }
}
```

**Error Responses**

| Code | Condition |
|---|---|
| `500` | Failed to read character configuration |

> **Note**: If `characters.yaml` is missing, the endpoint returns a default character with status `200` instead of an error: `{"1": {"name": "Patient 1", "persona": "一般病患", "backstory": "系統默認角色"}}`.

> **Note**: The `backstory` field is truncated to 100 characters in the response. If the original value exceeds 100 characters, it will be cut off with `"..."` appended.

**curl Example**

```bash
curl http://localhost:18000/api/characters
```

---

### Health & Monitoring

#### GET /api/health/status

Get system health status including error rates, response times, and issue detection.

**Request**: No parameters.

**Response** `200 OK`

```json
{
  "status": "success",
  "health_statuses": {
    "optimized": {
      "is_healthy": true,
      "error_rate": 0.0,
      "avg_response_time": 3.456,
      "recent_errors": 0,
      "issues": [],
      "last_check": "2026-03-04T10:30:00"
    }
  },
  "monitor_status": {
    "fallback_supported": false,
    "last_check_time": "2026-03-04T10:30:00",
    "thresholds": {
      "max_error_rate": 0.2,
      "max_response_time": 10.0,
      "max_recent_errors": 5,
      "check_interval": 60
    },
    "recent_health_checks": 15
  }
}
```

> **Note**: `error_rate` is expressed as a percentage (e.g. `5.0` means 5%). This differs from the `max_error_rate` threshold, which is a fraction (e.g. `0.20` means 20%).

**curl Example**

```bash
curl http://localhost:18000/api/health/status
```

---

#### POST /api/health/thresholds

Update health check thresholds at runtime.

**Request** (`application/json`)

| Parameter | Type | Required | Description |
|---|---|---|---|
| `thresholds` | object | Yes | Key-value pairs of thresholds to update |

Available threshold keys:

| Key | Type | Default | Description |
|---|---|---|---|
| `max_error_rate` | float | `0.20` | Maximum acceptable error rate (0.0–1.0) |
| `max_response_time` | float | `10.0` | Maximum acceptable avg response time (seconds) |
| `max_recent_errors` | int | `5` | Maximum recent errors before flagging unhealthy |
| `check_interval` | int | `60` | Health check interval (seconds) |

**Response** `200 OK`

```json
{
  "status": "success",
  "message": "健康檢查閾值已更新",
  "updated_thresholds": {
    "max_error_rate": 0.10,
    "max_response_time": 5.0
  }
}
```

**Error Responses**

| Code | Condition |
|---|---|
| `500` | Threshold update failure |

**curl Example**

```bash
curl -X POST http://localhost:18000/api/health/thresholds \
  -H "Content-Type: application/json" \
  -d '{"thresholds": {"max_error_rate": 0.10, "max_response_time": 5.0}}'
```

---

#### GET /api/monitor/stats

Get aggregated performance statistics per implementation.

**Request**: No parameters.

**Response** `200 OK`

```json
{
  "status": "success",
  "stats": {
    "optimized": {
      "total_requests": 142,
      "successful_requests": 140,
      "failed_requests": 2,
      "avg_response_time": 3.456,
      "error_rate": 1.41,
      "last_updated": "2026-03-04T10:30:00"
    }
  }
}
```

> **Note**: `error_rate` is expressed as a percentage (e.g. `1.41` means 1.41%).

**curl Example**

```bash
curl http://localhost:18000/api/monitor/stats
```

---

#### GET /api/monitor/errors

Get error summary within a time range.

**Request** (query parameter)

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `hours` | int | No | `24` | Time range in hours to look back |

**Response** `200 OK`

```json
{
  "status": "success",
  "time_range_hours": 24,
  "errors": {
    "optimized": {
      "total": 2,
      "by_endpoint": {
        "text_dialogue": 1,
        "audio_dialogue": 1
      },
      "recent_errors": [
        {
          "timestamp": "2026-03-04T09:15:00",
          "endpoint": "text_dialogue",
          "error": "Dialogue processing failed: ...",
          "character_id": "1"
        }
      ]
    }
  }
}
```

**curl Example**

```bash
curl "http://localhost:18000/api/monitor/errors?hours=6"
```

---

#### POST /api/monitor/reset

Reset all performance statistics and request history.

**Request**: No body required.

**Response** `200 OK`

```json
{
  "status": "success",
  "message": "性能統計數據已重置"
}
```

**curl Example**

```bash
curl -X POST http://localhost:18000/api/monitor/reset
```

---

### Debug

These endpoints are intended for development and debugging. They may be protected by a `DEBUG_API_TOKEN` environment variable.

#### GET /api/dev/session/{session_id}/history

Retrieve the full conversation history for a session.

**Path Parameter**

| Parameter | Type | Description |
|---|---|---|
| `session_id` | string | The session ID to inspect |

**Query Parameter**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `token` | string | Conditional | Required if `DEBUG_API_TOKEN` env var is set |

**Response** `200 OK`

```json
{
  "status": "success",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "implementation_version": "optimized",
  "conversation_history": [
    "王先生: 我想了解手術的流程",
    "護理師: 手術流程包括以下幾個步驟..."
  ],
  "log_file": "logs/api/20260304_103000_Patient_1_sess_a1b2c3d4_chat_gui.log"
}
```

**Error Responses**

| Code | Condition |
|---|---|
| `403` | `DEBUG_API_TOKEN` is set and `token` parameter is missing or invalid |
| `404` | Session not found |
| `500` | Dialogue manager missing in session |

**curl Example**

```bash
curl "http://localhost:18000/api/dev/session/a1b2c3d4-e5f6-7890-abcd-ef1234567890/history?token=mytoken"
```

---

#### POST /api/dev/config/set_max_history

Dynamically set the `DSPY_MAX_HISTORY` environment variable, which controls the conversation history window size used by the dialogue module.

**Request** (`application/json`)

| Parameter | Type | Required | Description |
|---|---|---|---|
| `max_history` | int | Yes | History window size (1–20) |

**Response** `200 OK`

```json
{
  "status": "success",
  "DSPY_MAX_HISTORY": 5
}
```

**Error Responses**

| Code | Condition |
|---|---|
| `400` | `max_history` outside range 1–20 |
| `500` | Internal error |

**curl Example**

```bash
curl -X POST http://localhost:18000/api/dev/config/set_max_history \
  -H "Content-Type: application/json" \
  -d '{"max_history": 5}'
```

---

#### POST /api/debug/start-log

Start a new DSPy debug log file. Returns the path to the created log file.

**Query Parameter**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `tag` | string | No | Optional tag for the log file name |

**Response** `200 OK`

```json
{
  "status": "success",
  "log_path": "logs/debug/20260304_103500_mytag_dspy_internal_debug.log"
}
```

**Error Responses**

| Code | Condition |
|---|---|
| `500` | Failed to create log file |

**curl Example**

```bash
curl -X POST "http://localhost:18000/api/debug/start-log?tag=my_debug_session"
```

---

## Concepts

### Audio Processing Flows

The API provides two audio processing paths:

#### One-Step Flow (Recommended): `/audio_input`

```
Client                          Server
  │                               │
  │  POST /audio_input            │
  │  (audio + character_id)       │
  │──────────────────────────────>│
  │                               │── Gemini transcription
  │                               │── Dialogue processing
  │                               │
  │  DialogueResponse             │
  │  (responses + transcription)  │
  │<──────────────────────────────│
```

- Single request, single response
- Best for: production use, low-latency scenarios
- The server selects the best transcription automatically
- Options generation is **skipped** (`option_count=0`) for performance — `speech_recognition_options` will be `null`

#### Two-Step Flow: `/audio` + `/select_response`

```
Client                          Server
  │                               │
  │  POST /audio                  │
  │  (audio + character_id)       │
  │──────────────────────────────>│
  │                               │── Gemini transcription
  │  DialogueResponse             │
  │  (WAITING_SELECTION +         │
  │   speech_recognition_options) │
  │<──────────────────────────────│
  │                               │
  │  [User picks an option]       │
  │                               │
  │  POST /select_response        │
  │  (session_id + selected)      │
  │──────────────────────────────>│
  │                               │── Record selection
  │  { status: success }          │
  │<──────────────────────────────│
```

- Two requests for a complete interaction
- Best for: when the user should review/correct transcription before proceeding
- The dialogue model is **not** called during the `/audio` step

---

### Dialogue States

| State | Value | Description |
|---|---|---|
| **NORMAL** | `"NORMAL"` | Standard conversational state |
| **TRANSITIONING** | `"TRANSITIONING"` | Dialogue topic is shifting |
| **CONFUSED** | `"CONFUSED"` | Input was unclear or unexpected |
| **TERMINATED** | `"TERMINATED"` | Dialogue has ended |
| **WAITING_SELECTION** | `"WAITING_SELECTION"` | Runtime state (two-step audio flow only). Returned by `/audio`, cleared by `/select_response`. |

> **Note**: `WAITING_SELECTION` is a runtime state managed by the API server. It is not part of the `DialogueState` enum in the dialogue engine. The first four states (`NORMAL`, `TRANSITIONING`, `CONFUSED`, `TERMINATED`) are determined by the LLM dialogue model.

---

### Session Lifecycle

1. **Creation**: A new session is created automatically when a dialogue endpoint is called without a valid `session_id`. The server generates a UUID and returns it in the response.
2. **Continuation**: Pass the `session_id` from a previous response to continue the conversation. Each session maintains its own dialogue history, character binding, and state.
3. **Expiry**: Sessions inactive for more than **1 hour** are automatically cleaned up by a background task.
4. **Character binding**: The `character_id` (and optional `character_config`) is bound at session creation and cannot be changed within a session.

---

### Supported Audio Formats

| Extension | MIME Type |
|---|---|
| `.wav` | `audio/wav` |
| `.m4a` | `audio/mp4` |
| `.mp4` | `audio/mp4` |
| `.mp3` | `audio/mp3` |
| `.aac` | `audio/aac` |
| `.ogg` | `audio/ogg` |
| `.flac` | `audio/flac` |
| `.webm` | `audio/webm` |

WAV files receive additional preprocessing (resampling to 16kHz, mono conversion, volume normalization). Other formats are sent directly to the Gemini transcription API.

---

### Response Schema Reference (DialogueResponse)

All dialogue endpoints (`/text`, `/audio_input`, `/audio`) return this schema:

| Field | Type | Always Present | Description |
|---|---|---|---|
| `status` | string | Yes | `"success"` or `"error"` |
| `responses` | string[] | Yes | List of dialogue response texts (4 items) |
| `state` | string | Yes | Dialogue state. See [Dialogue States](#dialogue-states). |
| `dialogue_context` | string | Yes | Brief description of the current dialogue context |
| `session_id` | string | Yes | Session identifier (UUID) |
| `inferred_speaker_role` | string \| null | Yes | _Deprecated._ Currently returns `null` in practice. |
| `speech_recognition_options` | string[] \| null | No | Transcription candidates (audio endpoints only) |
| `original_transcription` | string \| null | No | Best transcription result (audio endpoints only) |
| `raw_transcript` | string \| null | No | Raw transcription before post-processing |
| `keyword_completion` | object[] \| null | No | Keyword completion annotations from transcription. Each object: `{ "heard": string, "completed": string, "confidence": "high"\|"medium"\|"low", "reason": string }` |
| `implementation_version` | string \| null | No | Implementation version identifier (e.g. `"optimized"`) |
| `performance_metrics` | object \| null | No | Timing and performance data. May include `timing_breakdown`. |
| `processing_info` | object \| null | No | Additional processing metadata |
| `logs` | object \| null | No | Log file paths: `{ "chat_gui": "...", "dspy_debug": "..." }` |

#### Character Config Object

When using `character_config` (in `/text`) or `character_config_json` (in audio endpoints), the object structure is:

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | No | Character display name |
| `persona` | string | No | Character persona description |
| `backstory` | string | No | Character backstory |
| `goal` | string | No | Character's goal |
| `details` | object | No | Additional details (`fixed_settings`, `floating_settings`) |

---

## Client Code Examples

### curl

```bash
# === Text Dialogue ===
# Start a new conversation
curl -s -X POST http://localhost:18000/api/dialogue/text \
  -H "Content-Type: application/json" \
  -d '{"text": "你好，我剛做完手術", "character_id": "1"}' | jq .

# Continue a conversation
SESSION_ID="paste-session-id-here"
curl -s -X POST http://localhost:18000/api/dialogue/text \
  -H "Content-Type: application/json" \
  -d "{\"text\": \"傷口還是會痛\", \"character_id\": \"1\", \"session_id\": \"$SESSION_ID\"}" | jq .

# === One-Step Audio ===
curl -s -X POST http://localhost:18000/api/dialogue/audio_input \
  -F "audio_file=@question.wav" \
  -F "character_id=1" | jq .

# === Two-Step Audio ===
# Step 1: Transcribe
RESULT=$(curl -s -X POST http://localhost:18000/api/dialogue/audio \
  -F "audio_file=@question.wav" \
  -F "character_id=1")
echo "$RESULT" | jq .speech_recognition_options

# Step 2: Select
SESSION_ID=$(echo "$RESULT" | jq -r .session_id)
SELECTED=$(echo "$RESULT" | jq -r '.speech_recognition_options[0]')
curl -s -X POST http://localhost:18000/api/dialogue/select_response \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION_ID\", \"selected_response\": \"$SELECTED\"}" | jq .

# === Utilities ===
curl -s http://localhost:18000/api/characters | jq .
curl -s http://localhost:18000/api/health/status | jq .
curl -s http://localhost:18000/api/monitor/stats | jq .
```

### Python (requests)

```python
import requests

BASE_URL = "http://localhost:18000"

# --- Text Dialogue ---
def text_dialogue(text: str, character_id: str, session_id: str = None) -> dict:
    payload = {"text": text, "character_id": character_id}
    if session_id:
        payload["session_id"] = session_id
    resp = requests.post(f"{BASE_URL}/api/dialogue/text", json=payload)
    resp.raise_for_status()
    return resp.json()

# --- One-Step Audio ---
def audio_input(audio_path: str, character_id: str, session_id: str = None) -> dict:
    with open(audio_path, "rb") as f:
        files = {"audio_file": f}
        data = {"character_id": character_id}
        if session_id:
            data["session_id"] = session_id
        resp = requests.post(f"{BASE_URL}/api/dialogue/audio_input", files=files, data=data)
    resp.raise_for_status()
    return resp.json()

# --- Two-Step Audio ---
def audio_two_step(audio_path: str, character_id: str):
    # Step 1: Transcribe
    with open(audio_path, "rb") as f:
        resp = requests.post(
            f"{BASE_URL}/api/dialogue/audio",
            files={"audio_file": f},
            data={"character_id": character_id},
        )
    resp.raise_for_status()
    result = resp.json()

    options = result.get("speech_recognition_options", [])
    session_id = result["session_id"]
    print(f"Options: {options}")

    # Step 2: Select (pick the first option for demo)
    if options:
        resp2 = requests.post(
            f"{BASE_URL}/api/dialogue/select_response",
            json={"session_id": session_id, "selected_response": options[0]},
        )
        resp2.raise_for_status()
        return resp2.json()
    return result


# Usage
result = text_dialogue("你好", "1")
print(result["responses"])
print(f"Session: {result['session_id']}")

# Continue
result2 = text_dialogue("手術後要注意什麼？", "1", session_id=result["session_id"])
print(result2["responses"])
```

### JavaScript (fetch)

```javascript
const BASE_URL = "http://localhost:18000";

// --- Text Dialogue ---
async function textDialogue(text, characterId, sessionId = null) {
  const payload = { text, character_id: characterId };
  if (sessionId) payload.session_id = sessionId;

  const resp = await fetch(`${BASE_URL}/api/dialogue/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
  return resp.json();
}

// --- One-Step Audio ---
async function audioInput(audioFile, characterId, sessionId = null) {
  const formData = new FormData();
  formData.append("audio_file", audioFile);
  formData.append("character_id", characterId);
  if (sessionId) formData.append("session_id", sessionId);

  const resp = await fetch(`${BASE_URL}/api/dialogue/audio_input`, {
    method: "POST",
    body: formData,
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
  return resp.json();
}

// --- Two-Step Audio ---
async function audioTwoStep(audioFile, characterId) {
  // Step 1: Transcribe
  const formData = new FormData();
  formData.append("audio_file", audioFile);
  formData.append("character_id", characterId);

  const resp = await fetch(`${BASE_URL}/api/dialogue/audio`, {
    method: "POST",
    body: formData,
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
  const result = await resp.json();

  const options = result.speech_recognition_options || [];
  console.log("Transcription options:", options);

  // Step 2: Select
  if (options.length > 0) {
    const resp2 = await fetch(`${BASE_URL}/api/dialogue/select_response`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: result.session_id,
        selected_response: options[0],
      }),
    });
    if (!resp2.ok) throw new Error(`HTTP ${resp2.status}: ${await resp2.text()}`);
    return resp2.json();
  }
  return result;
}

// Usage
(async () => {
  const result = await textDialogue("你好，我是病患", "1");
  console.log("Responses:", result.responses);
  console.log("Session:", result.session_id);

  const result2 = await textDialogue(
    "手術後可以吃什麼？",
    "1",
    result.session_id
  );
  console.log("Follow-up:", result2.responses);
})();
```

---

## Appendix

### Status Codes

| Code | Meaning |
|---|---|
| `200` | Success |
| `400` | Bad request — missing required parameters, invalid audio format |
| `403` | Forbidden — invalid debug token |
| `404` | Not found — session not found |
| `410` | Gone — deprecated endpoint removed |
| `500` | Internal server error — dialogue processing failure, session creation error |

### Deprecated Endpoints

| Endpoint | Status | Notes |
|---|---|---|
| `GET /api/health` | **Does not exist** | Use `GET /api/health/status` instead |
| `POST /api/health/fallback` | `410 Gone` | `"fallback removed (fail-fast; no legacy implementation)"` |
| `GET /api/monitor/comparison` | `410 Gone` | `"comparison report removed (original implementation removed)"` |
| `response_format: "audio"` | **Reserved** | The `response_format` parameter on `/audio` is accepted but only `"text"` is functional |
| `inferred_speaker_role` | **Deprecated field** | Currently returns `null` in practice. Retained for backwards compatibility. |

### Changelog

| Date | Version | Changes |
|---|---|---|
| 2026-03-04 | 0.4.0 | Rewrote documentation from PDF to Markdown. Documented all 15 endpoints including `audio_input`, `select_response`, debug, and monitoring endpoints. Corrected dialogue states, audio format support, and response schema. |
