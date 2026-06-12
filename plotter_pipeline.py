import argparse
import base64
import os
from contextlib import ExitStack
from pathlib import Path

from bitmaptracer import bitmap_to_gcode


DEFAULT_LINE_DRAWING_PROMPT = """
create a minimalistic line drawing form this photo, constant line width, no speckles. simple and minimalistic but person should still be recognizable through facial details.
the drawing should not look too perfect, it should have human artistic quality, use the reference image as an example.

Requirements:
- portrait should remain recognizable from the source photo
- black lines on a plain white or very light background
- no color, no shading, no grayscale fills, no hatching except sparse facial hair texture
- continuous confident contour lines suitable for a pen plotter
- preserve important facial features, hair/beard silhouette, and clothing outline
- avoid photorealism, gradients, shadows, text, borders, and paper texture
- leave enough white space between lines for skeleton tracing
"""


def generate_line_drawing(
    photo_path,
    output_path,
    style_reference_path=None,
    prompt=DEFAULT_LINE_DRAWING_PROMPT,
    model="gpt-image-2",
    size="1024x1536",
    quality="medium",
):
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: install the OpenAI Python SDK with "
            "`python -m pip install openai`."
        ) from exc

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    image_paths = [Path(photo_path)]
    if style_reference_path:
        image_paths.append(Path(style_reference_path))

    client = OpenAI()

    with ExitStack() as stack:
        image_files = [
            stack.enter_context(path.open("rb"))
            for path in image_paths
        ]
        result = client.images.edit(
            model=model,
            image=image_files,
            prompt=prompt.strip(),
            size=size,
            quality=quality,
        )

    image_base64 = result.data[0].b64_json
    output_path.write_bytes(base64.b64decode(image_base64))
    return output_path


def run_pipeline(args):
    line_drawing_path = Path(args.line_drawing)

    if args.skip_generation:
        if not line_drawing_path.exists():
            raise ValueError(f"Line drawing does not exist: {line_drawing_path}")
        print(f"Using existing line drawing: {line_drawing_path}")
    else:
        prompt = DEFAULT_LINE_DRAWING_PROMPT
        if args.prompt_file:
            prompt = Path(args.prompt_file).read_text(encoding="utf-8")
        elif args.prompt:
            prompt = args.prompt

        print(f"Generating line drawing: {line_drawing_path}")
        generate_line_drawing(
            photo_path=args.photo,
            style_reference_path=args.style_reference,
            output_path=line_drawing_path,
            prompt=prompt,
            model=args.model,
            size=args.image_size,
            quality=args.quality,
        )

    print(f"Tracing line drawing to G-code: {args.gcode}")
    bitmap_to_gcode(
        input_path=str(line_drawing_path),
        output_path=args.gcode,
        threshold=args.threshold,
        invert=args.invert,
        min_size=args.min_size,
        simplify=args.simplify,
        width_mm=args.width_mm,
        height_mm=args.height_mm,
        lift_height=args.lift_height,
        speed=args.speed,
        travel_speed=args.travel_speed,
        pen_down_height=args.pen_down_height,
        prune_spurs=args.prune_spurs,
        min_path_length=args.min_path_length,
        optimize_order=not args.no_optimize_order,
    )


def build_parser():
    parser = argparse.ArgumentParser(
        description="Generate a plotter-ready line drawing from a photo and trace it to G-code."
    )
    parser.add_argument("photo", help="Input photo to convert")
    parser.add_argument("gcode", help="Output G-code file")
    parser.add_argument("--style-reference", help="Optional style/context reference image")
    parser.add_argument("--line-drawing", default="line_drawing.png", help="Intermediate line drawing PNG")
    parser.add_argument("--skip-generation", action="store_true", help="Trace an existing --line-drawing without calling the API")
    parser.add_argument("--model", default="gpt-image-2", help="OpenAI image model")
    parser.add_argument("--image-size", default="1024x1536", help="Generated image size, e.g. 1024x1536")
    parser.add_argument("--quality", default="medium", choices=["low", "medium", "high", "auto"])
    parser.add_argument("--prompt", help="Override the default line drawing prompt")
    parser.add_argument("--prompt-file", help="Read the line drawing prompt from a text file")

    parser.add_argument("--width-mm", type=float, required=True, help="Output drawing width in millimeters")
    parser.add_argument("--height-mm", type=float, default=None, help="Output drawing height in millimeters")
    parser.add_argument("--lift-height", type=float, default=5.0, help="Z height for travel moves")
    parser.add_argument("--pen-down-height", type=float, default=0.0, help="Z height while drawing")
    parser.add_argument("--speed", type=float, default=1500.0, help="Drawing feed rate in mm/min")
    parser.add_argument("--travel-speed", type=float, default=None, help="Travel feed rate in mm/min; defaults to --speed")

    parser.add_argument("--threshold", type=int, default=None)
    parser.add_argument("--invert", action="store_true")
    parser.add_argument("--min-size", type=int, default=80)
    parser.add_argument("--simplify", type=float, default=2.5)
    parser.add_argument("--prune-spurs", type=int, default=16)
    parser.add_argument("--min-path-length", type=float, default=12.0)
    parser.add_argument("--no-optimize-order", action="store_true")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        run_pipeline(args)
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
