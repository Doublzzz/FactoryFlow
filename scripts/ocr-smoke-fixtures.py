"""Generate synthetic inputs for the owned browser smoke only."""

import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main():
    root = Path(sys.argv[1]).resolve()
    if root.parent != Path(tempfile.gettempdir()).resolve() or not root.name.startswith(
        "factoryflow-business-"
    ):
        raise ValueError("Use the dedicated synthetic smoke directory")
    image = Image.new("RGB", (1600, 800), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 40)
    rows = [
        "Order No: SYN-OCR-ABC",
        "Date: 2026-10-02",
        "Currency: CNY",
        "Synthetic material   1.125   KG",
        "Synthetic part   2   PCS",
    ]
    for index, line in enumerate(rows):
        draw.text((50, 50 + index * 120), line, fill="black", font=font)
    image.save(root / "synthetic.png")
    image.save(
        root / "synthetic-two-pages.pdf",
        format="PDF",
        save_all=True,
        append_images=[image],
        resolution=150,
    )
    print("Synthetic image and two-page PDF prepared.")


if __name__ == "__main__":
    main()
