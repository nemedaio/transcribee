"""transcribee CLI — paste a URL, get a transcript."""
import argparse
import json
import sys
import tempfile
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="transcribee",
        description="Free local video transcription. Paste a URL, get a transcript.",
    )
    parser.add_argument("url", help="Video URL to transcribe")
    parser.add_argument("-o", "--output", help="Save transcript to file instead of stdout")
    parser.add_argument(
        "-f", "--format", default="txt", choices=["txt", "srt", "vtt", "json"],
        help="Output format (default: txt)",
    )
    parser.add_argument("-m", "--model", default="large-v3-turbo", help="Whisper model name")
    parser.add_argument("--backend", default="faster-whisper", help="Transcription backend")
    parser.add_argument("--device", default="auto", help="Device (auto/cpu/cuda)")
    parser.add_argument("--keep", action="store_true", help="Keep downloaded media files")
    args = parser.parse_args(argv)

    _run(args)


def _run(args: argparse.Namespace) -> None:
    url = args.url.strip()
    if not url:
        _die("No URL provided")

    _info(f"Downloading: {url}")
    work_dir = Path(tempfile.mkdtemp(prefix="transcribee-"))
    media_path = _download(url, work_dir)

    _info("Extracting audio...")
    audio_path = _extract_audio(media_path)

    _info(f"Transcribing with {args.backend} ({args.model})...")
    result = _transcribe(audio_path, args)

    output = _format_output(result, args.format)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        _info(f"Saved to {args.output}")
    else:
        print(output)

    if not args.keep:
        import shutil
        shutil.rmtree(work_dir, ignore_errors=True)


def _download(url: str, work_dir: Path) -> str:
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        _die("yt-dlp is required: pip install yt-dlp")

    output_template = str(work_dir / "%(id)s.%(ext)s")
    options = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "outtmpl": output_template,
    }
    with YoutubeDL(options) as dl:
        info = dl.extract_info(url, download=True)
        if "entries" in info:
            entries = info.get("entries") or []
            if not entries:
                _die("No downloadable media found at that URL")
            info = entries[0]
        return dl.prepare_filename(info)


def _extract_audio(media_path: str) -> str:
    from subprocess import run, CalledProcessError

    source = Path(media_path)
    output = source.with_suffix(".wav")
    try:
        run(
            ["ffmpeg", "-y", "-i", str(source), "-vn", "-ar", "16000", "-ac", "1", str(output)],
            check=True, capture_output=True, text=True,
        )
    except FileNotFoundError:
        _die("ffmpeg is required but not found. Install it: https://ffmpeg.org/")
    except CalledProcessError as exc:
        _die(f"Audio extraction failed: {exc.stderr.strip()}")
    return str(output)


def _transcribe(audio_path: str, args: argparse.Namespace) -> dict:
    backend = args.backend

    if backend == "faster-whisper":
        return _transcribe_faster_whisper(audio_path, args)
    elif backend == "openai-whisper":
        return _transcribe_openai_whisper(audio_path, args)
    elif backend == "whisper-cpp":
        return _transcribe_whisper_cpp(audio_path, args)
    else:
        _die(f"Unknown backend: {backend}. Use: faster-whisper, openai-whisper, whisper-cpp")


def _transcribe_faster_whisper(audio_path: str, args: argparse.Namespace) -> dict:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        _die("faster-whisper is required: pip install transcribee[faster-whisper]")

    model = WhisperModel(args.model, device=args.device, compute_type="default")
    segments_iter, info = model.transcribe(audio_path)
    segments = [
        {"start": s.start, "end": s.end, "text": s.text.strip()}
        for s in segments_iter
    ]
    text = " ".join(s["text"] for s in segments if s["text"])
    return {"text": text, "language": getattr(info, "language", None), "segments": segments}


def _transcribe_openai_whisper(audio_path: str, args: argparse.Namespace) -> dict:
    try:
        import whisper
    except ImportError:
        _die("openai-whisper is required: pip install transcribee[openai-whisper]")

    model = whisper.load_model(args.model, device=args.device)
    result = model.transcribe(audio_path)
    segments = [
        {"start": s["start"], "end": s["end"], "text": s["text"].strip()}
        for s in result.get("segments", [])
    ]
    text = " ".join(s["text"] for s in segments if s["text"])
    return {"text": text, "language": result.get("language"), "segments": segments}


def _transcribe_whisper_cpp(audio_path: str, args: argparse.Namespace) -> dict:
    try:
        from pywhispercpp.model import Model
    except ImportError:
        _die("pywhispercpp is required: pip install transcribee[whisper-cpp]")

    model = Model(args.model)
    raw = model.transcribe(audio_path)
    segments = [
        {"start": s.t0 / 100.0, "end": s.t1 / 100.0, "text": s.text.strip()}
        for s in raw
    ]
    text = " ".join(s["text"] for s in segments if s["text"])
    return {"text": text, "language": None, "segments": segments}


def _format_output(result: dict, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(result, indent=2, ensure_ascii=False)
    if fmt == "txt":
        return result["text"]
    if fmt == "srt":
        return _render_srt(result["segments"])
    if fmt == "vtt":
        return _render_vtt(result["segments"])
    return result["text"]


def _render_srt(segments: list[dict]) -> str:
    blocks = []
    for i, s in enumerate(segments, 1):
        blocks.append(f"{i}\n{_ts(s['start'], ',')} --> {_ts(s['end'], ',')}\n{s['text']}")
    return "\n\n".join(blocks)


def _render_vtt(segments: list[dict]) -> str:
    lines = ["WEBVTT"]
    for s in segments:
        lines.append(f"\n{_ts(s['start'], '.')} --> {_ts(s['end'], '.')}\n{s['text']}")
    return "\n".join(lines)


def _ts(seconds: float, sep: str = ".") -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02}{sep}{ms:03}"


def _info(msg: str) -> None:
    print(f"  {msg}", file=sys.stderr)


def _die(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
