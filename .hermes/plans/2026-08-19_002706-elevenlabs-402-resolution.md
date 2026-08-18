# ElevenLabs 402 TTS Resolution Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make the ElevenLabs TTS flow correctly handle account/voice entitlement limits and produce a successful phone/Web audio only when the selected voice is actually API-eligible.

**Architecture:** Keep the existing `TTSService` provider boundary and Backend-owned `AudioRepository`. Preserve ElevenLabs' upstream status/code instead of presenting every provider failure as a generic 502. The account/plan decision remains external: either upgrade the ElevenLabs plan for Library Voices or choose a voice/API entitlement that the current account can use; the code must not fabricate fallback audio.

**Tech Stack:** Flask, Python `urllib`, ElevenLabs REST API, existing TTS route/storage, pytest, Node frontend.

---

## Current evidence and root cause

Observed provider response:

```text
HTTP 402
code: paid_plan_required
message: Free users cannot use library voices via the API.
```

This proves:

- Backend reaches ElevenLabs.
- URL, API key authentication, and request transport are working far enough to receive a provider response.
- The current selected `TTS_VOICE` is an ElevenLabs Library Voice that the account plan cannot use through the API.
- This is not an MQTT, Firestore, Frontend, or WAV-storage failure.

Current source already has an ElevenLabs adapter in `backend/app/services/tts_service.py` and the route maps provider failures to HTTP 502. The next code improvement is error classification/UX; a successful live call still requires an eligible voice or a paid plan.

---

## Decision gate before implementation

Choose one provider-side path before the live smoke test:

1. **Upgrade ElevenLabs** so the selected Library Voice is API-eligible.
2. **Use an ElevenLabs voice/API entitlement available to the current account** and set `TTS_VOICE` to that exact Voice ID. Do not use the display name and do not assume every Library Voice is available on the free plan.

Do not change API keys repeatedly or add local synthetic audio as a silent fallback. If the user authorizes a synthetic/local fallback later, label it explicitly and preserve the ElevenLabs failure.

---

## Task 1: Add a failing regression test for provider status preservation

**Objective:** Ensure a provider 402 response is represented as a billing/entitlement error rather than a generic configuration error.

**Files:**
- Modify: `backend/tests/test_provider_services.py`
- Modify: `backend/tests/test_api.py` or the existing TTS route test section

**Step 1: Write failing tests**

Add tests that:

- Build an `HTTPError(402, ...)` containing `paid_plan_required`.
- Assert the TTS service preserves the upstream status/code in a safe exception or typed provider error.
- Assert the API route returns a stable error code such as `TTS_PLAN_REQUIRED` with HTTP 402.
- Assert the response does not contain the API key.

Expected test shape:

```python
def test_tts_plan_error_is_not_reported_as_generic_provider_failure(client):
    class PaidPlanTTSService:
        def synthesize(self, text, voice=None):
            raise TTSProviderError(
                status=402,
                code="paid_plan_required",
                message="Free users cannot use this voice through the API",
            )

    client.application.extensions["tts_service"] = PaidPlanTTSService()
    response = client.post("/api/v1/audio/tts", json={"text": "hello"})

    assert response.status_code == 402
    assert response.json["error"]["code"] == "TTS_PLAN_REQUIRED"
```

**Step 2: Run RED**

```powershell
cd C:\Users\vongb\Downloads\t\backend
uv run pytest -q tests/test_provider_services.py tests/test_api.py
```

Expected: FAIL because the current route maps provider exceptions to generic HTTP 502 and has no typed 402 mapping.

---

## Task 2: Introduce a typed ElevenLabs provider error

**Objective:** Preserve the upstream HTTP status, provider code, and bounded response detail without leaking credentials.

**Files:**
- Modify: `backend/app/services/tts_service.py`
- Modify: `backend/app/services/__init__.py` only if the new exception is exported

**Step 1: Implement minimal error type**

Add a typed exception containing:

- `status: int`
- `provider_code: str | None`
- `message: str`

When `urllib.error.HTTPError` is caught:

- Read at most 512 bytes from the response body.
- Parse JSON when possible and extract `detail.code`, `detail.message`, and `detail.status`.
- Fall back to the HTTP status and a bounded plain-text detail.
- Never include the API key, Authorization header, or full request headers.

Keep the existing ElevenLabs request contract:

```text
POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}
Header: xi-api-key: <secret>
Query: output_format=mp3_44100_128 or another account-supported format
Body: {"text": "...", "model_id": "..."}
```

**Step 2: Run targeted tests GREEN**

```powershell
uv run pytest -q tests/test_provider_services.py::test_tts_http_error_includes_provider_response_body
```

Expected: PASS, with no credential value in the exception text.

---

## Task 3: Map provider entitlement errors in the Flask route

**Objective:** Give the user an actionable API response instead of a misleading 502.

**Files:**
- Modify: `backend/app/routes/audio_routes.py`
- Test: `backend/tests/test_provider_services.py` or `backend/tests/test_api.py`

**Mapping:**

```text
402 + paid_plan_required → TTS_PLAN_REQUIRED, HTTP 402
401 + invalid_api_key     → TTS_AUTH_FAILED, HTTP 502 or 401 according to the API policy
404 + voice_not_found     → TTS_VOICE_NOT_FOUND, HTTP 400
422 + provider validation → TTS_REQUEST_INVALID, HTTP 422
other provider failure    → TTS_PROVIDER_FAILED, HTTP 502
```

The response message should tell the Dashboard user to upgrade/choose an API-eligible voice, without exposing provider secrets.

**Verification:**

```powershell
uv run pytest -q tests/test_provider_services.py tests/test_api.py
```

Expected: all targeted tests PASS.

---

## Task 4: Validate the ElevenLabs account/voice choice outside the app

**Objective:** Separate account entitlement from application code.

Run in the same PowerShell process that will start the Backend. Do not paste the API key into chat or commit it.

Construct the URL without chat-format wrappers:

```powershell
$base = "https" + "://" + "api.elevenlabs.io"
$voicesUri = $base + "/v1/voices"
$headers = @{ "xi-api-key" = $env:TTS_API_KEY; "Accept" = "application/json" }
$voices = Invoke-RestMethod -Uri $voicesUri -Headers $headers -Method Get
$voices.voices | Select-Object name, voice_id
```

Select a `voice_id` that the current ElevenLabs account is allowed to use through the API. If every intended Library Voice is restricted, upgrade the plan rather than changing Backend code to bypass the restriction.

Then configure:

```powershell
$env:TTS_PROVIDER = "elevenlabs"
$env:TTS_API_URL = $base + "/v1/text-to-speech"
$env:TTS_MODEL = "eleven_multilingual_v2"
$env:TTS_VOICE = "<eligible_voice_id>"
$env:TTS_RESPONSE_FORMAT = "mp3"
```

**Expected provider smoke result:** the direct request returns HTTP 200 and audio content, not 402.

---

## Task 5: Restart the real Backend process and run the app smoke test

**Objective:** Ensure the process actually receives the new environment and source code.

**Files:**
- No source change; runtime verification only.

Stop the old Flask process, set the variables in the same PowerShell window, then run:

```powershell
cd C:\Users\vongb\Downloads\t\backend
uv run python run.py
```

Open the Dashboard and submit a short TTS request.

Acceptance:

- HTTP `201` from `POST /api/v1/audio/tts`.
- A new `tts_*.mp3` record appears in `backend/storage/audio` and `metadata.json`.
- The Dashboard can stream the generated MP3.
- If Cloud is enabled, metadata sync is attempted but local audio remains authoritative.

If the provider still returns 402, report `TTS_PLAN_REQUIRED` with the exact entitlement message; do not label the app as broken.

---

## Task 6: Full verification and documentation

**Files:**
- Modify: `backend/.env.example`
- Modify: `README.md`
- Modify: `docs/PROJECT_TASKS.md`
- Append: `LOG.md`

Document:

- ElevenLabs `TTS_PROVIDER=elevenlabs` configuration.
- `TTS_API_URL` must be the base URL without `@url:` or backticks.
- `TTS_VOICE` is a Voice ID, not a display name.
- Free-plan Library Voice restrictions are provider-side.
- API keys remain local secrets.

Run:

```powershell
cd C:\Users\vongb\Downloads\t
npm run check
hermes verify --json
```

Expected host result:

- PASS — provider contract tests.
- PASS — Backend/Frontend checks.
- NOT VERIFIED — real ElevenLabs delivery unless the direct provider smoke and Dashboard request return HTTP 200/201 with the user's credentials.

Do not commit API keys, Voice IDs that are intended to be private, service tokens, or generated audio artifacts unless explicitly requested.

---

## Risks and open questions

- **Plan entitlement:** the current provider response explicitly blocks Library Voices on the free plan; code cannot override billing restrictions.
- **Token lifetime:** the current adapter uses `TTS_API_KEY`; it does not manage key rotation. Rotate/revoke exposed keys.
- **Mobile notifications:** FCM/Cloud are separate from ElevenLabs TTS; a successful TTS call does not prove Firestore or phone notifications.
- **Provider rate limits:** add bounded retry only for documented transient errors; do not retry 402/401/404 automatically.
- **Audio ownership:** ElevenLabs bytes remain Backend-owned local files; Firestore receives metadata only.
