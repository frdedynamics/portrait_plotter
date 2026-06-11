# Portrait Plotter

Pipeline for turning a portrait photo into plotter-ready G-code:

1. take a photo,
2. generate a black-line portrait drawing with the OpenAI API,
3. trace that bitmap line drawing with `bitmaptracer.py`,
4. write G-code to a file for the plotter controller.

Printer connection, Raspberry Pi UI, and job sending are intentionally outside this repository.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "sk-..."
```

On Linux/Raspberry Pi:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."
```

## Run The Full Pipeline

```powershell
python plotter_pipeline.py photo.jpg output.gcode `
  --style-reference style_reference.png `
  --line-drawing output_line.png `
  --width-mm 100 `
  --height-mm 125 `
  --lift-height 5 `
  --speed 1500
```

The generated line drawing is saved separately so it can be inspected before plotting.

## Trace An Existing Line Drawing

Use this when you already have a generated bitmap line drawing and only want G-code:

```powershell
python plotter_pipeline.py photo.jpg output.gcode `
  --skip-generation `
  --line-drawing output_line.png `
  --width-mm 100 `
  --height-mm 125
```

## Useful Tracing Knobs

- `--simplify`: higher values make fewer, straighter G-code moves.
- `--min-size`: removes small bitmap components before skeleton tracing.
- `--prune-spurs`: removes short dangling skeleton branches.
- `--min-path-length`: omits dot-like traced paths.
- `--threshold`: manually controls black/white thresholding; by default Otsu thresholding is used.

The defaults in `plotter_pipeline.py` are more aggressive than raw `bitmaptracer.py` because GPT-generated line drawings often contain small texture marks that become tiny plotter moves.

## API Key Safety

For local development, keep your OpenAI API key out of the repository.

Recommended local setup:

1. Copy `.env.example` to `.env`.
2. Put your real key in `.env`.
3. Load it into your shell before running the pipeline.

PowerShell:

```powershell
$env:OPENAI_API_KEY = "sk-..."
```

Linux/Raspberry Pi:

```bash
export OPENAI_API_KEY="sk-..."
```

`.env` and `.venv` are ignored by git in this repo. `.env.example` is safe to commit because it contains only a placeholder.

Use GitHub Secrets only for GitHub Actions or other GitHub-hosted automation. A GitHub Secret does not automatically help your Raspberry Pi or your local shell; for the Pi, store the key as an environment variable, a local `.env` file, or a systemd environment file that is not committed.

Before pushing, run:

```powershell
git status
git diff -- .gitignore README.md requirements.txt .env.example
```

Do not commit screenshots, logs, shell history, config files, or test scripts that contain a real `OPENAI_API_KEY`. If a key is ever committed, revoke it in the OpenAI dashboard and create a new one; deleting it from git later is not enough because it remains in history.
