#!/usr/bin/env python3
"""CreatorForge Gemini Flash TTS — standalone CLI + importable synthesize().

Canonical TTS proxy client. Both the CLI entry point (``creatorforge-tts``)
and ``CustomTTSProvider`` import ``synthesize()`` from this module.
"""

import argparse
import base64
import logging
import mimetypes
import os
import struct
import sys
from typing import Optional

import requests

from agent_core.audio.tts.base import strip_ssml

logger = logging.getLogger(__name__)

PROXY_URL = os.getenv("TTS_PROXY_URL", "http://127.0.0.1:8317/v1beta/models/gemini-3.1-flash-tts-preview:generateContent")
API_KEY = os.getenv("TTS_API_KEY", "your-api-key-3")


def parse_audio_mime_type(mime_type: str) -> dict:
    bits_per_sample = 16
    rate = 24000
    parts = mime_type.split(";")
    for param in parts:
        param = param.strip()
        if param.lower().startswith("rate="):
            try:
                rate = int(param.split("=", 1)[1])
            except (ValueError, IndexError):
                pass
        elif param.startswith("audio/L"):
            try:
                bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError):
                pass
    return {"bits_per_sample": bits_per_sample, "rate": rate}


def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    parameters = parse_audio_mime_type(mime_type)
    bits_per_sample = parameters["bits_per_sample"]
    sample_rate = parameters["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", chunk_size, b"WAVE", b"fmt ", 16, 1,
        num_channels, sample_rate, byte_rate, block_align,
        bits_per_sample, b"data", data_size,
    )
    return header + audio_data


def build_directed_prompt(
    script_text: str,
    profile: str,
    scene: str,
    style: str,
    pace: str,
    accent: str,
    sample_context: str,
) -> str:
    return (
        "1. Synthesize speech for the performance defined below. The profile, scene, "
        "performance notes, and context are direction only. Do NOT speak them.\n"
        "2. Speak ONLY the lines under #### TRANSCRIPT.\n\n"
        f"# AUDIO PROFILE\n{profile}\n\n"
        f"### SCENE\n{scene}\n\n"
        f"### PERFORMANCE\n"
        f"Style: {style}\n"
        f"Pace: {pace}\n"
        f"Accent: {accent}\n\n"
        f"### CONTEXT\n{sample_context}\n\n"
        f"#### TRANSCRIPT\n{script_text}"
    )


def synthesize(
    script_text: str,
    voice: str = "Zephyr",
    style: str = "Vocal Smile",
    pace: str = "Natural",
    accent: str = "American (Gen)",
    profile: str = "Warm and educational",
    scene: str = "A quiet recording booth.",
    context: str = "Neutral mood.",
    proxy_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> tuple[bytes, str, str]:
    """Call the TTS proxy API and return raw audio bytes.

    Args:
        script_text: Text to synthesize (SSML-stripped).
        voice: Prebuilt voice model name.
        style, pace, accent, profile, scene, context: Performance directives.
        proxy_url: Override ``TTS_PROXY_URL`` env var.
        api_key: Override ``TTS_API_KEY`` env var.

    Returns:
        ``(audio_bytes, mime_type, file_extension)``.

    Raises:
        RuntimeError: On connection failure, HTTP error, or missing audio payload.
    """
    url = proxy_url or PROXY_URL
    key = api_key or API_KEY

    directed_prompt = build_directed_prompt(
        script_text=script_text,
        profile=profile,
        scene=scene,
        style=style,
        pace=pace,
        accent=accent,
        sample_context=context,
    )

    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": directed_prompt}]},
        ],
        "generationConfig": {
            "temperature": 1.0,
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice},
                },
            },
        },
    }

    headers = {"Content-Type": "application/json"}
    if key:
        headers["x-goog-api-key"] = key

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"TTS connection failed: {e}") from e

    if response.status_code != 200:
        raise RuntimeError(f"TTS API error {response.status_code}: {response.text}")

    response_data = response.json()

    try:
        candidate = response_data["candidates"][0]
        part = candidate["content"]["parts"][0]
        inline_data = part.get("inlineData") or part.get("inline_data")
        if not inline_data:
            raise RuntimeError("Audio payload missing from API response")
        mime_type = inline_data.get("mimeType") or inline_data.get("mime_type")
        audio_b64 = inline_data["data"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected API response structure: {e}") from e

    raw_audio_bytes = base64.b64decode(audio_b64)

    file_extension = mimetypes.guess_extension(mime_type)
    if file_extension is None or "audio/L" in mime_type:
        file_extension = ".wav"
        final_audio_bytes = convert_to_wav(raw_audio_bytes, mime_type)
    else:
        final_audio_bytes = raw_audio_bytes

    return final_audio_bytes, mime_type, file_extension


def main() -> None:
    parser = argparse.ArgumentParser(description="CreatorForge Gemini Flash TTS CLI")
    parser.add_argument("--script_path", required=True, help="Input text/script file")
    parser.add_argument("--output_path", required=True, help="Output path (extension auto-appended)")
    parser.add_argument("--voice", default="Zephyr")
    parser.add_argument("--style", default="Vocal Smile")
    parser.add_argument("--pace", default="Natural")
    parser.add_argument("--accent", default="American (Gen)")
    parser.add_argument("--profile", default="Warm and educational")
    parser.add_argument("--scene", default="A quiet recording booth.")
    parser.add_argument("--context", default="Neutral mood.")

    args = parser.parse_args()

    if not os.path.exists(args.script_path):
        print(f"Error: Script file not found at {args.script_path}", file=sys.stderr)
        sys.exit(1)

    with open(args.script_path, "r", encoding="utf-8") as f:
        script_text = f.read().strip()

    if not script_text:
        print("Error: Input script file is empty.", file=sys.stderr)
        sys.exit(1)

    try:
        audio_bytes, _mime, ext = synthesize(
            script_text=script_text,
            voice=args.voice,
            style=args.style,
            pace=args.pace,
            accent=args.accent,
            profile=args.profile,
            scene=args.scene,
            context=args.context,
        )
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    output_path = f"{args.output_path}{ext}"
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(audio_bytes)
    print(f"Success: Audio saved to {output_path}")


if __name__ == "__main__":
    main()
