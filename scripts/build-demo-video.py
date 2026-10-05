"""Compose a local 1080p MP4 from supplied real captures and captions.

No browser operation, image generation, model call, voice synthesis or hosting.
The producer records input-image bytes; capture provenance remains a separate
responsibility. Earlier output editions are never overwritten.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import uuid


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()


def _pairs(entries):
    result = {}
    for key, value in entries:
        if key in result: raise ValueError("Duplicate manifest JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Manifest numbers must be finite")


def load_manifest(path, allowed_root=None, *, allow_short_smoke=False):
    path = Path(path).resolve(strict=True)
    with path.open("rb") as handle: raw = handle.read(256 * 1024 + 1)
    if len(raw) > 256 * 1024: raise ValueError("Manifest exceeds 256KiB")
    frames = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_pairs, parse_constant=_reject_constant)
    if type(frames) is not list or not 1 <= len(frames) <= 120:
        raise ValueError("Manifest must contain one to120 frame rows")
    root = Path(allowed_root or path.parent).resolve(strict=True)
    result, total = [], 0.0
    for item in frames:
        if type(item) is not dict or not {"image", "duration", "caption"} <= set(item) or not set(item) <= {"image", "duration", "caption", "sha256", "crop"}:
            raise ValueError("Each frame requires image, duration and caption; optional sha256 and blank-padding crop")
        if type(item["image"]) is not str or not 1 <= len(item["image"]) <= 2000:
            raise ValueError("A bounded local image path is required")
        candidate = Path(item["image"])
        if not candidate.is_absolute(): candidate = path.parent / candidate
        # Resolving first would conceal symlinks/junctions; inspect the supplied
        # existing path chain, then enforce the final allowed root.
        for part in [candidate, *candidate.parents]:
            if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
                raise ValueError("Symlink/junction image paths are unsupported")
        image = candidate.resolve(strict=True)
        if not image.is_file() or image.suffix.lower() not in (".png", ".jpg", ".jpeg") or not image.is_relative_to(root):
            raise ValueError("Use a PNG/JPEG inside the allowed capture root")
        if image.stat().st_size > 32 * 1024**2: raise ValueError("Image exceeds32MiB")
        duration = item["duration"]
        if type(duration) not in (int, float) or not math.isfinite(duration) or not 1 <= duration <= 60:
            raise ValueError("Each duration must be finite seconds1..60")
        caption = item["caption"]
        if type(caption) is not str or not caption.strip() or len(caption) > 400:
            raise ValueError("Use a nonblank caption of at most400 characters")
        caption.encode("utf-8")
        digest = sha(image)
        if "sha256" in item and (type(item["sha256"]) is not str or item["sha256"] != digest):
            raise ValueError("Supplied capture image hash does not match")
        total += duration
        row = {"image": str(image), "duration": duration, "caption": caption, "sha256": digest}
        if "crop" in item:
            crop = item['crop']
            if type(crop) is not list or len(crop)!=4 or any(type(x) is not int or x<0 for x in crop) or not(crop[0]<crop[2] and crop[1]<crop[3]):
                raise ValueError('Crop requires four nonnegative integer pixel coordinates')
            row['crop'] = crop
        result.append(row)
    if total > 150 or (not allow_short_smoke and total < 90):
        raise ValueError("Final demo duration must be90..150 seconds; only explicit smoke may be shorter")
    return {"schema_version": "recorded-product-video-v1", "manifest_path": str(path), "manifest_sha256": hashlib.sha256(raw).hexdigest(),
            "allowed_root": str(root), "frames": result, "duration_seconds": total, "short_smoke": allow_short_smoke and total < 90,
            "production_duration_target_met": 90 <= total <= 150}


def _font(size, *, bold=False):
    from PIL import ImageFont
    candidates = [Path("C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
                  Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
    for candidate in candidates:
        if candidate.is_file(): return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default(size=size)


def _wrap_caption(draw, text, font, width):
    lines, current = [], ""
    for word in text.split():
        trial = (current + " " + word).strip()
        if draw.textlength(trial, font=font) <= width:
            current = trial; continue
        if current: lines.append(current); current = ""
        # Break a single long source token only in presentation; source caption
        # bytes are preserved in the output timeline manifest.
        while draw.textlength(word, font=font) > width:
            cut = 1
            while cut < len(word) and draw.textlength(word[:cut + 1], font=font) <= width: cut += 1
            lines.append(word[:cut]); word = word[cut:]
        current = word
    if current: lines.append(current)
    if len(lines) > 3: raise ValueError("Caption exceeds three visible lines; shorten it")
    return lines


def compose_frame(frame, index, count, destination):
    from PIL import Image, ImageDraw, ImageOps, ImageChops
    image_path = Path(frame["image"])
    if sha(image_path) != frame["sha256"]: raise ValueError("Capture bytes changed before composition")
    with Image.open(image_path) as image:
        if image.width * image.height > 20_000_000: raise ValueError("Capture exceeds20million pixels")
        image.load(); image = ImageOps.exif_transpose(image).convert("RGB")
        original_size = [image.width, image.height]
        crop = frame.get('crop')
        if crop is not None:
            if crop[2]>image.width or crop[3]>image.height: raise ValueError('Crop extends beyond original capture')
            # The only authorized crop removes uniform capture-canvas padding.
            # Every differing pixel must remain; source PNG bytes are untouched.
            background = image.getpixel((image.width-1,image.height-1))
            bounds = ImageChops.difference(image,Image.new('RGB',image.size,background)).getbbox()
            if bounds and not(crop[0]<=bounds[0] and crop[1]<=bounds[1] and crop[2]>=bounds[2] and crop[3]>=bounds[3]):
                raise ValueError('Crop would remove nonblank product/source pixels')
            image = image.crop(tuple(crop))
        cropped_size = [image.width,image.height]
        image.thumbnail((1856, 864), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (1920, 1080), "#fcfbf7")
        canvas.paste(image, ((1920 - image.width) // 2, 44 + (864 - image.height) // 2))
    draw = ImageDraw.Draw(canvas)
    draw.line((32, 924, 1888, 924), fill="#d6ded9", width=2)
    draw.text((34, 12), "SOCIETY LAB  /  recorded product demonstration", font=_font(23, bold=True), fill="#20494e")
    font = _font(31)
    lines = _wrap_caption(draw, frame["caption"], font, 1760)
    for i, line in enumerate(lines): draw.text((48, 944 + i * 37), line, font=font, fill="#16353b")
    draw.text((1828, 1043), f"{index + 1}/{count}", font=_font(20), fill="#577077")
    canvas.save(destination, format="PNG")
    return {"composed_image": str(destination), "composed_sha256": sha(destination), "original_size": original_size,
            "crop_rectangle":crop,"cropped_size":cropped_size,
            "display_size": [image.width, image.height], "screenshot_transform": "uniform blank-canvas padding crop then letterbox; all differing pixels retained" if crop else "whole-image letterbox; no synthetic UI or image crop"}


def _srt_stamp(seconds):
    milliseconds = round(seconds * 1000); hours, rem = divmod(milliseconds, 3600000); minutes, rem = divmod(rem, 60000); secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def build_video(manifest, output, *, fps=24):
    import imageio_ffmpeg
    if type(fps) is not int or not 1 <= fps <= 60: raise ValueError("Use integer fps1..60")
    output = Path(output).absolute()
    if output.suffix.lower() != ".mp4": raise ValueError("Output must be anMP4 file")
    if output.exists(): raise ValueError("Earlier video editions are immutable; use a new filename")
    output.parent.mkdir(parents=True, exist_ok=True)
    work = output.parent / (output.stem + "-frames-" + uuid.uuid4().hex[:8]); work.mkdir(exist_ok=False)
    timeline, elapsed, concat = [], 0.0, ["ffconcat version 1.0"]
    for i, frame in enumerate(manifest["frames"]):
        filename = f"frame-{i:03d}.png"
        details = compose_frame(frame, i, len(manifest["frames"]), work / filename)
        timeline.append({**frame, **details, "start_seconds": elapsed, "end_seconds": elapsed + frame["duration"]})
        elapsed += frame["duration"]; concat.extend([f"file '{filename}'", f"duration {frame['duration']:.6f}"])
    concat.append(f"file 'frame-{len(timeline) - 1:03d}.png'")
    (work / "timeline.ffconcat").write_text("\n".join(concat) + "\n", encoding="utf-8")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    args = [ffmpeg, "-hide_banner", "-loglevel", "warning", "-nostdin", "-n", "-f", "concat", "-safe", "1", "-i", str(work / "timeline.ffconcat"),
            "-vf", f"fps={fps}", "-t", f"{elapsed:.6f}", "-r", str(fps), "-fps_mode", "cfr", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-threads", "2", "-movflags", "+faststart", "-an", str(output)]
    result = subprocess.run(args, capture_output=True, timeout=300)
    (work / "ffmpeg.stdout.bin").write_bytes(result.stdout); (work / "ffmpeg.stderr.bin").write_bytes(result.stderr)
    if result.returncode != 0: raise RuntimeError(f"FFmpeg failed with exit{result.returncode}; exact byte logs retained in{work}")
    frame_count, duration = imageio_ffmpeg.count_frames_and_secs(str(output))
    reader = imageio_ffmpeg.read_frames(str(output)); metadata = next(reader); reader.close()
    valid = (tuple(metadata["source_size"]) == (1920, 1080) and abs(duration - elapsed) <= 1 / fps + .01
             and abs(frame_count - round(elapsed * fps)) <= 1)
    if not valid: raise RuntimeError("Decoded output dimensions/duration/frame count do not match the timeline")
    text = "\n\n".join(f"{i + 1}\n{_srt_stamp(r['start_seconds'])} --> {_srt_stamp(r['end_seconds'])}\n{r['caption']}" for i, r in enumerate(timeline)) + "\n"
    subtitle_path = output.with_suffix(".srt"); subtitle_path.write_text(text, encoding="utf-8")
    proof = {**manifest, "created_utc": datetime.now(timezone.utc).isoformat(), "timeline": timeline,
        "video": {"path": str(output), "sha256": sha(output), "bytes": output.stat().st_size, "dimensions": [1920, 1080], "fps": fps,
                  "decoded_frames": frame_count, "decoded_duration_seconds": duration, "audio": "none"},
        "subtitles": {"path": str(subtitle_path), "sha256": sha(subtitle_path)},
        "encoder": {"package": "imageio-ffmpeg", "package_version": imageio_ffmpeg.__version__, "ffmpeg_version": imageio_ffmpeg.get_ffmpeg_version(), "binary_sha256": sha(ffmpeg),"preset":"veryfast","crf":20,"threads":2},
        "script_sha256": sha(__file__), "verified_dimensions_duration_and_frame_count": valid,
        "scope": "A composition of supplied recorded-product/actual-source images. Image hashes authenticate local input bytes, not UI execution, model success, scientific novelty or historical causality. No voice, Framer hosting or publication.",
        "model_calls": 0, "database_writes": 0}
    output.with_suffix(".verification.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--allowed-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--allow-short-smoke", action="store_true", help="Explicitly label a short encoder smoke; not a final90–150second demo")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest, args.allowed_root, allow_short_smoke=args.allow_short_smoke)
    proof = build_video(manifest, args.output, fps=args.fps)
    print(json.dumps({"video": proof["video"], "verification": str(args.output.with_suffix(".verification.json")), "duration_target_met": proof["production_duration_target_met"]}, indent=2))


if __name__ == "__main__": main()
