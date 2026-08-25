@echo off
REM Copy this file to config.cmd and edit it.
REM Keep config.cmd private because it contains your Hyper API key.

set "HYPER_API_KEY=sk-hyper-REPLACE_ME"

REM Optional model. If unavailable, HyperBit asks /v1/models and falls back.
set "HYPER_MODEL=deepseek-v4-flash"

REM TTS choices: sapi (offline Windows voice) or gtts (online Google voice)
set "HYPERBIT_TTS=sapi"

REM Faster-Whisper defaults:
set "HYPERBIT_STT_MODEL=base.en"
set "HYPERBIT_STT_DEVICE=cpu"
set "HYPERBIT_STT_COMPUTE=int8"
