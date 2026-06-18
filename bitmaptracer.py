# bitmap_to_centerline_svg.py
#
# Converts a black-line bitmap drawing into SVG paths or pen-plotter G-code.
# Good for pen plotters.
#
# Install:
#   pip install pillow numpy opencv-contrib-python scikit-image
#
# Usage:
#   python bitmaptracer.py input.png output.svg
#   python bitmaptracer.py input.png output.gcode --width-mm 100 --height-mm 125
#
# Optional:
#   python bitmaptracer.py input.png output.svg --threshold 180 --simplify 1.5

from PIL import Image
import numpy as np
import cv2
import argparse
from skimage.morphology import skeletonize, remove_small_objects

from signature import render_hvlrobotics_signature_mask


def rdp(points, epsilon):
    """
    Ramer-Douglas-Peucker polyline simplification.
    points: list of (x, y)
    """
    if len(points) < 3:
        return points

    start = np.array(points[0])
    end = np.array(points[-1])
    line = end - start

    if np.all(line == 0):
        distances = [np.linalg.norm(np.array(p) - start) for p in points]
    else:
        line_length = np.linalg.norm(line)
        distances = [
            abs(line[0] * (start[1] - p[1]) - line[1] * (start[0] - p[0])) / line_length
            for p in points
        ]

    max_index = int(np.argmax(distances))
    max_distance = distances[max_index]

    if max_distance > epsilon:
        left = rdp(points[:max_index + 1], epsilon)
        right = rdp(points[max_index:], epsilon)
        return left[:-1] + right
    else:
        return [points[0], points[-1]]


def neighbors8(p, skeleton):
    """
    Return all 8-connected skeleton neighbors of pixel p.
    p is (y, x).
    """
    y, x = p
    h, w = skeleton.shape
    result = []

    for dy in [-1, 0, 1]:
        for dx in [-1, 0, 1]:
            if dy == 0 and dx == 0:
                continue

            ny, nx = y + dy, x + dx

            if 0 <= ny < h and 0 <= nx < w and skeleton[ny, nx]:
                result.append((ny, nx))

    return result


def edge_key(a, b):
    return tuple(sorted([a, b]))


def path_length(points):
    if len(points) < 2:
        return 0.0

    total = 0.0
    for a, b in zip(points, points[1:]):
        total += float(np.linalg.norm(np.array(b) - np.array(a)))
    return total


def remove_small_components(mask, min_size):
    if min_size <= 1:
        return mask

    try:
        # scikit-image 0.26 renamed this threshold to max_size and removes
        # components with size <= max_size. The old min_size removed size < min_size.
        return remove_small_objects(mask, max_size=min_size - 1)
    except TypeError:
        return remove_small_objects(mask, min_size=min_size)


def best_continuation(previous, current, candidates):
    if len(candidates) == 1:
        return candidates[0]

    in_vec = np.array(current) - np.array(previous)
    best = candidates[0]
    best_score = None

    for candidate in candidates:
        out_vec = np.array(candidate) - np.array(current)
        score = float(np.dot(in_vec, out_vec) / (np.linalg.norm(in_vec) * np.linalg.norm(out_vec)))
        if best_score is None or score > best_score:
            best = candidate
            best_score = score

    return best


def prune_skeleton_spurs(skeleton, max_spur_length):
    if max_spur_length <= 0:
        return skeleton

    pruned = skeleton.copy()

    while True:
        pixels = set(zip(*np.where(pruned)))
        degree = {p: len(neighbors8(p, pruned)) for p in pixels}
        endpoints = [p for p, d in degree.items() if d == 1]
        removed_any = False

        for endpoint in endpoints:
            if not pruned[endpoint]:
                continue

            spur = [endpoint]
            previous = None
            current = endpoint

            while len(spur) <= max_spur_length:
                neighbors = [
                    n for n in neighbors8(current, pruned)
                    if n != previous
                ]

                if not neighbors:
                    break

                if len(neighbors) > 1:
                    break

                nxt = neighbors[0]
                spur.append(nxt)
                previous, current = current, nxt

                if len(neighbors8(current, pruned)) != 2:
                    break

            if len(spur) <= max_spur_length and len(neighbors8(spur[-1], pruned)) > 1:
                for pixel in spur[:-1]:
                    pruned[pixel] = False
                removed_any = True

        if not removed_any:
            return pruned


def trace_skeleton(skeleton):
    """
    Convert a 1-pixel skeleton into polylines.

    Returns:
        list of paths, where each path is [(x, y), (x, y), ...]
    """
    visited_edges = set()
    paths = []

    def follow_path(start, next_pixel):
        path = [start, next_pixel]

        visited_edges.add(edge_key(start, next_pixel))

        previous = start
        current = next_pixel

        while True:
            current_neighbors = neighbors8(current, skeleton)
            if len(current_neighbors) == 1 and current != start:
                break

            candidates = [
                n for n in current_neighbors
                if n != previous and edge_key(current, n) not in visited_edges
            ]

            if not candidates:
                break

            nxt = best_continuation(previous, current, candidates)
            visited_edges.add(edge_key(current, nxt))

            path.append(nxt)
            previous, current = current, nxt

        # Convert from image coords (y, x) to SVG coords (x, y)
        return [(x, y) for y, x in path]

    pixels = set(zip(*np.where(skeleton)))
    degree = {p: len(neighbors8(p, skeleton)) for p in pixels}
    endpoints = [p for p, d in degree.items() if d == 1]

    # Start with true endpoints and continue straight through junctions when possible.
    for endpoint in endpoints:
        for n in neighbors8(endpoint, skeleton):
            if edge_key(endpoint, n) not in visited_edges:
                paths.append(follow_path(endpoint, n))

    # Then handle closed loops and any remaining branches.
    for p in pixels:
        for n in neighbors8(p, skeleton):
            if edge_key(p, n) not in visited_edges:
                paths.append(follow_path(p, n))

    return paths


def hvlrobotics_signature_paths(width_mm, left_mm=4.0, bottom_mm=4.0):
    if width_mm <= 0:
        raise ValueError("Signature width must be positive.")
    if left_mm < 0 or bottom_mm < 0:
        raise ValueError("Signature margins cannot be negative.")

    skeleton = skeletonize(render_hvlrobotics_signature_mask())
    paths = [
        rdp(path, 0.8)
        for path in trace_skeleton(skeleton)
        if path_length(path) >= 3.0
    ]

    xs = [x for path in paths for x, _ in path]
    ys = [y for path in paths for _, y in path]
    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)
    scale = width_mm / max(max_x - min_x, 1)

    return [
        [
            (
                left_mm + ((x - min_x) * scale),
                bottom_mm + ((max_y - y) * scale),
            )
            for x, y in path
        ]
        for path in paths
    ]


GCODE_EXTENSIONS = {".gcode", ".gc", ".nc", ".tap"}


def trace_bitmap(
    input_path,
    threshold=None,
    invert=False,
    min_size=20,
    simplify=1.0,
    prune_spurs=8,
    min_path_length=4.0,
):
    with Image.open(input_path) as img:
        gray = np.ascontiguousarray(np.asarray(img.convert("L")), dtype=np.uint8)
    height, width = gray.shape

    # Optional blur helps remove tiny bitmap noise.
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    if threshold is None:
        # Otsu threshold.
        _, binary = cv2.threshold(
            blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
    else:
        _, binary = cv2.threshold(
            blurred, threshold, 255, cv2.THRESH_BINARY
        )

    # We want drawing lines to be True.
    # Usually black ink on white background means dark pixels are the line.
    if invert:
        line_pixels = binary > 0
    else:
        line_pixels = binary == 0

    # Remove small noise.
    line_pixels = remove_small_components(line_pixels.astype(bool), min_size)

    # Skeletonize to one-pixel centerlines.
    skeleton = skeletonize(line_pixels)
    skeleton = prune_skeleton_spurs(skeleton, prune_spurs)

    paths = trace_skeleton(skeleton)

    # Simplify paths so the pen plotter does not get thousands of tiny segments.
    simplified_paths = []
    for path in paths:
        if len(path) >= 2:
            simplified = rdp(path, simplify)
            if len(simplified) >= 2 and path_length(simplified) >= min_path_length:
                simplified_paths.append(simplified)

    return simplified_paths, width, height


def order_paths_nearest(paths):
    if not paths:
        return paths

    remaining = [list(path) for path in paths]
    ordered = [remaining.pop(0)]
    current = ordered[-1][-1]

    while remaining:
        best_index = 0
        best_reverse = False
        best_distance = None

        for index, path in enumerate(remaining):
            start_distance = np.linalg.norm(np.array(current) - np.array(path[0]))
            end_distance = np.linalg.norm(np.array(current) - np.array(path[-1]))

            if best_distance is None or start_distance < best_distance:
                best_index = index
                best_reverse = False
                best_distance = start_distance

            if end_distance < best_distance:
                best_index = index
                best_reverse = True
                best_distance = end_distance

        path = remaining.pop(best_index)
        if best_reverse:
            path.reverse()

        ordered.append(path)
        current = path[-1]

    return ordered


def write_svg(output_path, paths, width, height, stroke_width=1.0):
    # Write SVG manually.
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
        )

        f.write(
            f'<g fill="none" stroke="black" stroke-width="{stroke_width}" '
            f'stroke-linecap="round" stroke-linejoin="round">\n'
        )

        for path in paths:
            d = f"M {path[0][0]:.2f} {path[0][1]:.2f}"
            for x, y in path[1:]:
                d += f" L {x:.2f} {y:.2f}"

            f.write(f'  <path d="{d}" />\n')

        f.write("</g>\n")
        f.write("</svg>\n")

    print(f"Saved SVG: {output_path}")
    print(f"Number of plotted paths: {len(paths)}")


def write_gcode(
    output_path,
    paths,
    image_width_px,
    image_height_px,
    width_mm,
    height_mm,
    lift_height,
    speed,
    travel_speed=None,
    pen_down_height=0.0,
    optimize_order=True,
    present_x=0.0,
    present_y=220.0,
    signature=False,
    signature_width=28.0,
    signature_margin=4.0,
    signature_gap=2.0,
):
    if width_mm <= 0 or height_mm <= 0:
        raise ValueError("G-code width and height must be positive millimeter values.")

    if lift_height <= pen_down_height:
        raise ValueError("Lift height must be greater than pen-down height.")

    travel_speed = travel_speed or speed
    if optimize_order:
        paths = order_paths_nearest(paths)

    signature_paths = []
    portrait_bottom = 0.0
    if signature:
        if signature_gap < 0:
            raise ValueError("Signature gap cannot be negative.")
        signature_paths = hvlrobotics_signature_paths(
            width_mm=signature_width,
            left_mm=signature_margin,
            bottom_mm=signature_margin,
        )
        if optimize_order:
            signature_paths = order_paths_nearest(signature_paths)
        signature_x = [x for path in signature_paths for x, _ in path]
        signature_y = [y for path in signature_paths for _, y in path]
        if max(signature_x) > width_mm or max(signature_y) > height_mm:
            raise ValueError(
                "Signature does not fit within the drawing area. "
                "Reduce --signature-width or --signature-margin."
            )
        portrait_bottom = max(signature_y) + signature_gap
        if portrait_bottom >= height_mm:
            raise ValueError(
                "Signature reserve area leaves no room for the portrait. "
                "Reduce --signature-width, --signature-margin, or --signature-gap."
            )

    x_scale = width_mm / max(image_width_px - 1, 1)
    y_scale = height_mm / max(image_height_px - 1, 1)
    portrait_scale = min(1.0, (height_mm - portrait_bottom) / height_mm)
    portrait_x_offset = (width_mm - (width_mm * portrait_scale)) / 2.0

    def to_mm(point):
        x, y = point
        original_x = x * x_scale
        original_y = height_mm - (y * y_scale)
        return (
            portrait_x_offset + (original_x * portrait_scale),
            portrait_bottom + (original_y * portrait_scale),
        )

    def write_mm_path(file, path):
        start_x, start_y = path[0]
        file.write(f"G0 X{start_x:.3f} Y{start_y:.3f} F{travel_speed:.0f}\n")
        file.write(f"G1 Z{pen_down_height:.3f} F{travel_speed:.0f}\n")
        file.write(f"G1 F{speed:.0f}\n")
        for x, y in path[1:]:
            file.write(f"G1 X{x:.3f} Y{y:.3f}\n")
        file.write(f"G0 Z{lift_height:.3f}\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("; Generated by bitmaptracer.py\n")
        f.write("; Units: millimeters\n")
        f.write("G21\n")
        f.write("G90\n")
        f.write("G28\n")
        f.write(f"G0 Z{lift_height:.3f}\n")
        if signature:
            f.write(
                f"; Portrait scaled to {portrait_scale:.4f} "
                f"with Y >= {portrait_bottom:.3f} mm for signature clearance\n"
            )

        for path in paths:
            write_mm_path(f, [to_mm(point) for point in path])

        if signature:
            f.write("; HVLRobotics signature\n")
            for path in signature_paths:
                write_mm_path(f, path)

        f.write("; End: lift pen and present work\n")
        f.write(f"G0 Z{lift_height:.3f}\n")
        if present_x is not None and present_y is not None:
            f.write(f"G0 X{present_x:.3f} Y{present_y:.3f} F{travel_speed:.0f}\n")
        f.write("M2\n")

    print(f"Saved G-code: {output_path}")
    print(f"Number of plotted paths: {len(paths)}")
    if signature:
        print(f"Number of signature paths: {len(signature_paths)}")


def bitmap_to_svg(
    input_path,
    output_path,
    threshold=None,
    invert=False,
    min_size=20,
    simplify=1.0,
    stroke_width=1.0,
    prune_spurs=8,
    min_path_length=4.0,
):
    paths, width, height = trace_bitmap(
        input_path=input_path,
        threshold=threshold,
        invert=invert,
        min_size=min_size,
        simplify=simplify,
        prune_spurs=prune_spurs,
        min_path_length=min_path_length,
    )
    write_svg(output_path, paths, width, height, stroke_width=stroke_width)


def bitmap_to_gcode(
    input_path,
    output_path,
    threshold=None,
    invert=False,
    min_size=20,
    simplify=1.0,
    width_mm=None,
    height_mm=None,
    lift_height=5.0,
    speed=1500.0,
    travel_speed=None,
    pen_down_height=0.0,
    prune_spurs=8,
    min_path_length=4.0,
    optimize_order=True,
    present_x=0.0,
    present_y=220.0,
    signature=False,
    signature_width=28.0,
    signature_margin=4.0,
    signature_gap=2.0,
):
    paths, image_width_px, image_height_px = trace_bitmap(
        input_path=input_path,
        threshold=threshold,
        invert=invert,
        min_size=min_size,
        simplify=simplify,
        prune_spurs=prune_spurs,
        min_path_length=min_path_length,
    )

    if width_mm is None and height_mm is None:
        raise ValueError("G-code export needs --width-mm and/or --height-mm.")

    aspect = image_width_px / image_height_px
    if width_mm is None:
        width_mm = height_mm * aspect
    elif height_mm is None:
        height_mm = width_mm / aspect

    write_gcode(
        output_path=output_path,
        paths=paths,
        image_width_px=image_width_px,
        image_height_px=image_height_px,
        width_mm=width_mm,
        height_mm=height_mm,
        lift_height=lift_height,
        speed=speed,
        travel_speed=travel_speed,
        pen_down_height=pen_down_height,
        optimize_order=optimize_order,
        present_x=present_x,
        present_y=present_y,
        signature=signature,
        signature_width=signature_width,
        signature_margin=signature_margin,
        signature_gap=signature_gap,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input bitmap image, e.g. PNG/JPG")
    parser.add_argument("output", help="Output SVG or G-code file")
    parser.add_argument("--threshold", type=int, default=None)
    parser.add_argument("--invert", action="store_true")
    parser.add_argument("--min-size", type=int, default=20)
    parser.add_argument("--simplify", type=float, default=1.0)
    parser.add_argument("--prune-spurs", type=int, default=8, help="Remove dangling skeleton branches up to this many pixels")
    parser.add_argument("--min-path-length", type=float, default=4.0, help="Omit traced paths shorter than this many pixels")
    parser.add_argument("--stroke-width", type=float, default=1.0)
    parser.add_argument("--gcode", action="store_true", help="Export G-code even if output extension is not .gcode")
    parser.add_argument("--width-mm", type=float, default=None, help="Output drawing width in millimeters")
    parser.add_argument("--height-mm", type=float, default=None, help="Output drawing height in millimeters")
    parser.add_argument("--lift-height", type=float, default=5.0, help="Z height for travel moves")
    parser.add_argument("--pen-down-height", type=float, default=0.0, help="Z height while drawing")
    parser.add_argument("--speed", type=float, default=1500.0, help="Drawing feed rate in mm/min")
    parser.add_argument("--travel-speed", type=float, default=None, help="Travel feed rate in mm/min; defaults to --speed")
    parser.add_argument("--no-optimize-order", action="store_true", help="Keep traced path order instead of nearest-neighbor ordering")
    parser.add_argument("--present-x", type=float, default=0.0, help="Final X position after lifting pen")
    parser.add_argument("--present-y", type=float, default=220.0, help="Final Y position after lifting pen")
    parser.add_argument("--no-present", action="store_true", help="Do not move XY after the final pen lift")
    parser.add_argument("--signature", action="store_true", help="Add an HVLRobotics signature in the bottom-left corner")
    parser.add_argument("--signature-width", type=float, default=28.0, help="Signature width in millimeters")
    parser.add_argument("--signature-margin", type=float, default=4.0, help="Signature left and bottom margin in millimeters")
    parser.add_argument("--signature-gap", type=float, default=2.0, help="Clear space between signature and portrait in millimeters")

    args = parser.parse_args()
    output_lower = args.output.lower()
    export_gcode = args.gcode or any(output_lower.endswith(ext) for ext in GCODE_EXTENSIONS)

    try:
        if export_gcode:
            bitmap_to_gcode(
                input_path=args.input,
                output_path=args.output,
                threshold=args.threshold,
                invert=args.invert,
                min_size=args.min_size,
                simplify=args.simplify,
                prune_spurs=args.prune_spurs,
                min_path_length=args.min_path_length,
                width_mm=args.width_mm,
                height_mm=args.height_mm,
                lift_height=args.lift_height,
                speed=args.speed,
                travel_speed=args.travel_speed,
                pen_down_height=args.pen_down_height,
                optimize_order=not args.no_optimize_order,
                present_x=None if args.no_present else args.present_x,
                present_y=None if args.no_present else args.present_y,
                signature=args.signature,
                signature_width=args.signature_width,
                signature_margin=args.signature_margin,
                signature_gap=args.signature_gap,
            )
        else:
            bitmap_to_svg(
                input_path=args.input,
                output_path=args.output,
                threshold=args.threshold,
                invert=args.invert,
                min_size=args.min_size,
                simplify=args.simplify,
                prune_spurs=args.prune_spurs,
                min_path_length=args.min_path_length,
                stroke_width=args.stroke_width,
            )
    except ValueError as exc:
        parser.error(str(exc))
