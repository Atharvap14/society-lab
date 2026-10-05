# Recorded product demo: AI Village to a source-grounded access test

Target: a 1080p, 90–150-second local MP4. Use actual product screenshots captured by the browser operator, plus the saved real-log figures. No invented chat, model output, voice or result. This is a local video artifact; no Framer hosting or public upload is assumed.

## Capture plan (120 seconds)

| Time | Actual frame to capture | Caption |
|---|---|---|
| 0–12 s | Actual AI Village project/source card | “We start with 2,000 real AI Village messages. The agents are coordinating a human-subjects study.” |
| 12–24 s | Saved real-log post heatmap | “Six agents posted in this retained window. These are chat counts, not productivity or continuous activity.” |
| 24–38 s | Actual incident view with the admitted mistyped URL | “A 404 can come from an incorrect reference. The original reports are preserved with message IDs.” |
| 38–52 s | Actual v4 permission/version incident | “Document identity, permissions and browser profiles are separate. A corruption claim is not a verified cause.” |
| 52–67 s | Actual agent question/plan, with its source links | “We turn that ambiguity into a testable question: can reference-bound verification avoid unnecessary copies?” |
| 67–84 s | Actual environment rules/tools, after review completes | “The new world represents URLs, sharing, signed-in and private profiles, document copies and independent work.” |
| 84–102 s | Actual execution/tool activity or replay receipt | “Agents act through the tools. Saved traces preserve what was actually attempted and what the controlled oracle returned.” |
| 102–120 s | Actual final results and scope panel | **Fill only after a verified run exists.** State the observed units/outcome and uncertainty, or honestly say the run is incomplete. Close with “This tests the controlled environment, not historical Google Drive causation.” |

The final frame must use the verified source-linked study or its actual incomplete status. If the new world has only passed fixture checks, say that explicitly and show the saved verification; do not title it an empirical LLM effect.

## External frame manifest

The compositor accepts a UTF-8 JSON **array**; each row has `image`, `duration` in seconds and `caption`. Optional `sha256` binds expected capture bytes. Optional `crop: [left, top, right, bottom]` removes only uniform capture-canvas padding: the compositor rejects any rectangle that removes a differing product pixel. Original PNG bytes and hashes remain preserved; crop coordinates and original dimensions are recorded. Relative image paths resolve from the manifest directory. Images must be PNG/JPEG inside the explicit allowed root, with no symlinks/junctions. Keep all captions below 400 characters and three visible lines.

The browser operator should create the manifest only after the corresponding actual captures exist. The script does not create synthetic UI frames or authenticate capture provenance. Title/outro content is presented as captions outside the original screenshot content. Input bytes, timeline, encoder, composed frames, output bytes and decoded duration are recorded in the verification sidecar. A 90-second cut can be used for the final delivery; it remains a composition of captured screens rather than a continuous screen recording.

```powershell
C:/Python312/python.exe -B -X utf8 scripts/build-demo-video.py `
  output/demo/village-access-recording/frames.json `
  --allowed-root output `
  --output output/demo/village-access-demo-01.mp4
```

Prerequisites are Pillow and `imageio-ffmpeg==0.6.0`; its official wheel supplies FFmpeg on Windows. [The upstream package documentation](https://github.com/imageio/imageio-ffmpeg) describes that binary distribution. There is no browser control, model call or database mutation in this authoring script. Existing video names are never overwritten; use a new immutable edition when captures change.

The script produces an MP4, plain SubRip caption transcript and `.verification.json`. It verifies 1920×1080 output, decoded frame count and timeline duration. All image and stdout/stderr hashes are computed from physical file bytes. A separately labeled short encoder smoke may use `--allow-short-smoke`; that is not the finished product demonstration.

## Completed 90-second edition

The delivered local artifact is `output/demo/village-access-demo-01.mp4`: 1920×1080, 24 fps, 2,160 decoded frames, 90.0 seconds, with no audio. Its eight-frame manifest is `output/demo/village-access-recording/frames-final-01.json`; the `.srt`, `.verification.json` and `.release-check.json` sidecars accompany the MP4. The captured source, incident, plan, world, saved action replay, result and replay-check screens are combined with the unmodified native result figure. Uniform canvas padding is removed only when every nonbackground pixel remains inside the documented crop; original captures are retained unchanged.

The result shown is `village_access_experiment-db164367c12a` version 1, hash `47da22a9c02728683f9b0ab8753b3ae180dc4710b24e98b31c8be07faf7ff1c8`: four fresh teams in two matched pairs made 240 real LLM subject decisions. Neither condition produced a verified usable project (0/2 each). The estimated whole-team note difference is zero, with the saved 95% bounded-pair interval spanning −1 to +1. This small controlled-world test demonstrates neither benefit nor equivalence and does not identify historical Google Drive causes. The exact result-caption facts were checked by fresh deterministic replay, without additional model calls.

MP4 SHA256: `9082ab918fec857f0e8636daff7ffebad6e4c7c8224345578b68c955a487062e`. This is a captioned composition of actual recorded product screens, not a continuous screen recording, narrated video, public deployment or Framer publication.
