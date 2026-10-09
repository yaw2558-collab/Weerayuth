"""Build desktop icons from an Edge-rendered screenshot of logo.svg.

Step 1 (manual, needs Edge on Windows):
    msedge --headless --disable-gpu ^
      --screenshot=desktop\\assets\\logo-raw.png --window-size=1024,1024 ^
      "file:///C:/.../thai-customs/gateway/static/logo.svg"

Step 2 (this script, from thai-customs/):
    .\\.venv\\Scripts\\python desktop\\assets\\make-icons.py

Produces:
    desktop/assets/logo-1024.png  (1024x1024, transparent corners)
    desktop/assets/logo.ico       (16-256px, for the Windows installer)
The Mac .icns is generated on the CI Mac runner via iconutil (see macos/).
"""

from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
RAW = HERE / "logo-raw.png"
PNG = HERE / "logo-1024.png"
ICO = HERE / "logo.ico"

SIZE = 1024
# Brand colors from logo.svg
GREEN = (12, 74, 66)
ORANGE = (194, 65, 12)


def near(px, target, tol=40):
    return all(abs(a - b) <= tol for a, b in zip(px[:3], target))


def main() -> None:
    img = Image.open(RAW).convert("RGBA")
    assert img.size == (SIZE, SIZE), f"unexpected size {img.size}"

    # Screenshot has a white page background; make exterior transparent.
    # Corners connect to the outside only (interior white is enclosed
    # by the green rounded square), so a corner flood fill is safe.
    px = img.load()
    seen = set()
    stack = [(0, 0), (SIZE - 1, 0), (0, SIZE - 1), (SIZE - 1, SIZE - 1)]
    cleared = 0
    while stack:
        x, y = stack.pop()
        if (x, y) in seen or not (0 <= x < SIZE and 0 <= y < SIZE):
            continue
        seen.add((x, y))
        r, g, b, _ = px[x, y]
        if r > 250 and g > 250 and b > 250:
            px[x, y] = (255, 255, 255, 0)
            cleared += 1
            stack.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])

    img.save(PNG)
    img.save(ICO, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    # Pixel verification (independent of the transform above).
    out = Image.open(PNG).convert("RGBA")
    assert out.size == (SIZE, SIZE)
    assert out.getpixel((5, 5))[3] == 0, "corner should be transparent"
    assert near(out.getpixel((SIZE // 2, SIZE // 4 + 60)), GREEN), "top half should be brand green"
    # Orange check circle sits right-of-center, lower half (cx=56/80, cy=55/80).
    assert near(out.getpixel((int(SIZE * 0.66), int(SIZE * 0.62))), ORANGE), "check circle should be brand orange"
    # Interior white container must survive (not cleared).
    assert near(out.getpixel((int(SIZE * 0.30), int(SIZE * 0.33))), (255, 255, 255)), "interior white lost?"
    assert out.getpixel((int(SIZE * 0.30), int(SIZE * 0.33)))[3] == 255
    ico = Image.open(ICO)
    print(f"cleared exterior px: {cleared}")
    print(f"wrote {PNG.name} ({PNG.stat().st_size} bytes), {ICO.name} ({ICO.stat().st_size} bytes, {ico.size})")
    print("ICON CHECKS OK")


if __name__ == "__main__":
    main()
