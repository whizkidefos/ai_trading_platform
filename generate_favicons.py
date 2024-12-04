from PIL import Image
import cairosvg
import os

def generate_favicons():
    # Create img directory if it doesn't exist
    img_dir = 'static/img'
    os.makedirs(img_dir, exist_ok=True)

    # Convert SVG to PNG
    svg_path = os.path.join(img_dir, 'favicon.svg')
    sizes = {
        'favicon-16x16.png': 16,
        'favicon-32x32.png': 32,
        'apple-touch-icon.png': 180,
        'android-chrome-192x192.png': 192,
        'android-chrome-512x512.png': 512
    }

    for filename, size in sizes.items():
        output_path = os.path.join(img_dir, filename)
        cairosvg.svg2png(
            url=svg_path,
            write_to=output_path,
            output_width=size,
            output_height=size
        )
        print(f"Generated {filename}")

if __name__ == '__main__':
    generate_favicons()
