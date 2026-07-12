#!/usr/bin/env python3
import os
import sys
import argparse
import base64
import struct
import requests
import mimetypes

# Config from environment (GEMINI_API_KEY is required, PROXY_URL has a sensible default)
PROXY_URL = os.environ.get("PROXY_URL", "http://127.0.0.1:8317/v1beta/models/gemini-3.1-flash-tts-preview:generateContent")
API_KEY = os.environ.get("GEMINI_API_KEY", "")

def parse_audio_mime_type(mime_type: str):
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
        bits_per_sample, b"data", data_size
    )
    return header + audio_data

def build_directed_prompt(script_text, profile, scene, style, pace, accent, sample_context):
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

def main():
    parser = argparse.ArgumentParser(description="CreatorForge Gemini 3.1 Flash TTS CLI Client")
    parser.add_argument("--script_path", required=True, help="Path to the input text/script file.")
    parser.add_argument("--output_path", required=True, help="Path where the synthesized audio should be saved (extension auto-appended).")
    parser.add_argument("--voice", default="Zephyr", help="Prebuilt voice model name.")
    parser.add_argument("--style", default="Vocal Smile", help="Audio performance style.")
    parser.add_argument("--pace", default="Natural", help="Speech pacing style.")
    parser.add_argument("--accent", default="American (Gen)", help="Spoken accent style.")
    parser.add_argument("--profile", default="Warm and educational", help="Narrator profile direction.")
    parser.add_argument("--scene", default="A quiet recording booth.", help="Physical environment simulation.")
    parser.add_argument("--context", default="Neutral mood.", help="Performance background context.")

    args = parser.parse_args()

    # 1. Read input script file safely
    if not os.path.exists(args.script_path):
        print(f"Error: Script file not found at {args.script_path}", file=sys.stderr)
        sys.exit(1)

    with open(args.script_path, "r", encoding="utf-8") as f:
        script_text = f.read().strip()

    if not script_text:
        print("Error: Input script file is empty.", file=sys.stderr)
        sys.exit(1)

    # 2. Build the structural layout prompt
    directed_prompt = build_directed_prompt(
        script_text=script_text,
        profile=args.profile,
        scene=args.scene,
        style=args.style,
        pace=args.pace,
        accent=args.accent,
        sample_context=args.context
    )

    # Validate API key before building payload
    if not API_KEY:
        print("Error: GEMINI_API_KEY environment variable not set. "
              "Set it via: export GEMINI_API_KEY='your-key-here'", file=sys.stderr)
        sys.exit(1)

    # 3. Payload Construction
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": directed_prompt}]}
        ],
        "generationConfig": {
            "temperature": 1.0,
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": args.voice}
                }
            }
        }
    }

    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["x-goog-api-key"] = API_KEY

    print(f"Requesting TTS synthesis via CLI Proxy for voice: {args.voice}...")
    try:
        response = requests.post(PROXY_URL, headers=headers, json=payload, timeout=60)
    except requests.exceptions.RequestException as e:
        print(f"Connection Error: {e}", file=sys.stderr)
        sys.exit(1)

    if response.status_code != 200:
        print(f"API Error: {response.status_code} - {response.text}", file=sys.stderr)
        sys.exit(1)

    response_data = response.json()

    # 4. Defensive Parsing of JSON Response Payload
    try:
        candidate = response_data['candidates'][0]
        part = candidate['content']['parts'][0]

        inline_data = part.get('inlineData') or part.get('inline_data')
        if not inline_data:
            print("Error: Audio payload missing from API response structures.", file=sys.stderr)
            sys.exit(1)

        mime_type = inline_data.get('mimeType') or inline_data.get('mime_type')
        audio_b64 = inline_data.get('data')

        raw_audio_bytes = base64.b64decode(audio_b64)

        # 5. Check if we need to wrap the raw linear PCM stream inside a WAV container
        file_extension = mimetypes.guess_extension(mime_type)
        if file_extension is None or "audio/L" in mime_type:
            file_extension = ".wav"
            final_audio_bytes = convert_to_wav(raw_audio_bytes, mime_type)
        else:
            final_audio_bytes = raw_audio_bytes

        # 6. Write binary file out to target location
        final_output_path = f"{args.output_path}{file_extension}"
        os.makedirs(os.path.dirname(os.path.abspath(final_output_path)), exist_ok=True)

        with open(final_output_path, "wb") as f_out:
            f_out.write(final_audio_bytes)

        print(f"Success: Dynamic audio asset generated at -> {final_output_path}")

    except (KeyError, IndexError) as e:
        print(f"Parser Error: Could not interpret API payload structure. missing: {e}", file=sys.stderr)
        print("Raw payload trace:", response_data, file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
