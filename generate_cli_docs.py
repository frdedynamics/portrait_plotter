import subprocess
import sys
from pathlib import Path


COMMANDS = [
    ("plotter_pipeline.py", "Full photo/webcam to G-code pipeline"),
    ("webcam_capture.py", "Capture one image from a webcam"),
    ("preprocess_portrait.py", "Preprocess a portrait photo"),
    ("bitmaptracer.py", "Trace a bitmap line drawing to SVG or G-code"),
    ("serial_gcode_sender.py", "Stream G-code to a serial printer"),
]


def get_help(script_name):
    result = subprocess.run(
        [sys.executable, script_name, "--help"],
        cwd=Path(__file__).parent,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def main():
    lines = [
        "# CLI Reference",
        "",
        "This file is generated from the current argparse help output.",
        "",
        "Regenerate it with:",
        "",
        "```powershell",
        "python generate_cli_docs.py",
        "```",
        "",
    ]

    for script_name, description in COMMANDS:
        lines.extend(
            [
                f"## `{script_name}`",
                "",
                description,
                "",
                "```text",
                get_help(script_name),
                "```",
                "",
            ]
        )

    output_path = Path(__file__).with_name("CLI.md")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
