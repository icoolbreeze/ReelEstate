# ep07-xihu — 西湖文化广场 2室1厅 89㎡ 4800元/月 (示例数据)

Self-contained episode for the map-hub template. Layout:
- episode.json, pois.json, map/, script_v5.json (current; v4 = text, v5 = L15/L22 to VO), shots.json
- data/      Remotion episode JSON (timeline.json, footage.json, hub.json ...) — `stage.py` links it as src/episode
- public/    Remotion public dir (episode/ vo+mix, map/, photos_g/, rooms/, placeholder/, footage/ copies)
- footage/   Muse clips <ID>.mp4 (18) + footage/heygen/HG*.mp4 (currently PLACEHOLDERS from Muse P-clips)
- annotations/ tracked boxes + seeds/
- voice/     narration.json, clone110/ (CosyVoice, REJECTED by the user — redo with F5, see runbook)
- heygen/    heygen_audio.wav + segments.json (CosyVoice version — regenerate after the F5 voice)
- muse_prompts/ Muse batch prompt files + manifest
- avatar/, matte/, hook_matte/, f5_samples/ … PC-side experiments already here
