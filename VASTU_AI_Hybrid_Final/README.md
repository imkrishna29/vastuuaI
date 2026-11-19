# VASTU AI Hybrid — one-terminal Windows + Render

## Run from zero (Windows)
1. Extract ZIP and open `VASTU_AI_Hybrid_Final` folder in VS Code.
2. Revoke the API key you shared in chat. Generate a fresh Gemini API key in Google AI Studio.
3. Copy `.env.example` to `.env` and replace `PASTE_YOUR_NEW_PRIVATE_KEY_HERE` with your new secret key. NEVER share or commit `.env`.
4. Open VS Code Terminal from this folder and run `cmd /c START_WINDOWS.bat`. This creates a virtual environment and installs dependencies (internet required).
5. Open http://127.0.0.1:8000 . The server and frontend run together; no npm or second terminal.
6. Try Generate; export PDF; upload a blueprint and choose where north points. AI results are preliminary; review detected rooms, use editable manual assessment.
7. Stop server with Ctrl+C.

## Render
Push source to GitHub **without `.env`**. Render > New > Blueprint > connect repository containing `render.yaml`. Set `GEMINI_API_KEY` in Render Environment dashboard as a secret; set `GEMINI_MODEL` optionally. The app uses gunicorn and Render PORT. Free-tier service can sleep; Gemini free tier has quotas.

## Honest scope
This is a runnable prototype with a Gemini-assisted first-page image/PDF review, **not** reliable automatic architectural reconstruction. North direction must be provided for tentative scores. AI can misidentify rooms; manual review is essential. Corrected plans from uploaded plans are **not** automatically generated. Generated floor plans have a basic central corridor but are not validated for construction, building codes, accessibility, doors, windows, stairs, setbacks or structural integrity. Vastu is traditional belief without established scientific validation.
