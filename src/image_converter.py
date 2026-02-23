#!/usr/bin/env python3
"""
Image Converter CLI Tool

Converts images between common formats including JPEG, PNG, BMP, GIF, TIFF, and WebP.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is not installed. Install it with: pip install Pillow")
    sys.exit(1)


# Supported image formats
SUPPORTED_FORMATS = {
    '.jpg': 'JPEG',
    '.jpeg': 'JPEG',
    '.png': 'PNG',
    '.bmp': 'BMP',
    '.gif': 'GIF',
    '.tiff': 'TIFF',
    '.tif': 'TIFF',
    '.webp': 'WEBP',
}


def is_supported_format(file_path: Path) -> bool:
    """Check if the file extension is supported."""
    return file_path.suffix.lower() in SUPPORTED_FORMATS


def get_output_path(input_path: Path, output_format: str, output_dir: Optional[Path] = None) -> Path:
    """Generate the output file path."""
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = input_path.stem
        return output_dir / f"{stem}.{output_format.lower()}"
    else:
        return input_path.parent / f"{input_path.stem}.{output_format.lower()}"


def convert_image(input_path: Path, output_path: Path, output_format: str) -> bool:
    """
    Convert an image from one format to another.
    
    Args:
        input_path: Path to the input image file
        output_path: Path to the output image file
        output_format: Target format (e.g., 'JPEG', 'PNG', 'WEBP')
    
    Returns:
        True if conversion was successful, False otherwise
    """
    try:
        with Image.open(input_path) as img:
            # Convert RGBA to RGB for formats that don't support transparency
            if output_format in ['JPEG', 'BMP'] and img.mode in ['RGBA', 'LA', 'P']:
                # Create a white background
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode in ['RGBA', 'LA'] else None)
                img = rgb_img
            
            # Save the image in the target format
            img.save(output_path, format=output_format)
            return True
    except Exception as e:
        print(f"Error converting {input_path}: {e}", file=sys.stderr)
        return False


def process_file(input_path: Path, output_format: str, output_dir: Optional[Path] = None, 
                no_confirm: bool = False) -> bool:
    """
    Process a single image file.
    
    Args:
        input_path: Path to the input image file
        output_format: Target format (e.g., 'jpeg', 'png', 'webp')
        output_dir: Optional output directory
        no_confirm: Skip confirmation for overwriting existing files
    
    Returns:
        True if processing was successful, False otherwise
    """
    if not input_path.is_file():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        return False
    
    if not is_supported_format(input_path):
        print(f"Error: Unsupported file format: {input_path.suffix}", file=sys.stderr)
        return False
    
    # Get the PIL format name
    format_upper = output_format.upper()
    if format_upper == 'JPG':
        format_upper = 'JPEG'
    elif format_upper == 'TIF':
        format_upper = 'TIFF'
    
    output_path = get_output_path(input_path, output_format, output_dir)
    
    # Check if output file already exists
    if output_path.exists() and not no_confirm:
        response = input(f"File {output_path} already exists. Overwrite? (y/n): ")
        if response.lower() != 'y':
            print(f"Skipped: {input_path}")
            return False
    
    # Convert the image
    if convert_image(input_path, output_path, format_upper):
        print(f"Converted: {input_path} -> {output_path}")
        return True
    else:
        return False


def process_directory(input_dir: Path, output_format: str, output_dir: Optional[Path] = None,
                     no_confirm: bool = False, recursive: bool = True) -> tuple[int, int]:
    """
    Process all images in a directory.
    
    Args:
        input_dir: Path to the input directory
        output_format: Target format (e.g., 'jpeg', 'png', 'webp')
        output_dir: Optional output directory
        no_confirm: Skip confirmation for overwriting existing files
        recursive: Process subdirectories recursively
    
    Returns:
        Tuple of (successful_count, failed_count)
    """
    if not input_dir.is_dir():
        print(f"Error: Directory not found: {input_dir}", file=sys.stderr)
        return 0, 0
    
    # Find all supported image files
    image_files: List[Path] = []
    pattern = '**/*' if recursive else '*'
    
    for ext in SUPPORTED_FORMATS.keys():
        image_files.extend(input_dir.glob(f"{pattern}{ext}"))
        image_files.extend(input_dir.glob(f"{pattern}{ext.upper()}"))
    
    if not image_files:
        print(f"No supported image files found in {input_dir}")
        return 0, 0
    
    print(f"Found {len(image_files)} image(s) to convert")
    
    success_count = 0
    fail_count = 0
    
    for img_file in image_files:
        # Calculate relative output directory if output_dir is specified
        rel_output_dir = None
        if output_dir:
            if recursive:
                rel_path = img_file.parent.relative_to(input_dir)
                rel_output_dir = output_dir / rel_path
            else:
                rel_output_dir = output_dir
        
        if process_file(img_file, output_format, rel_output_dir, no_confirm):
            success_count += 1
        else:
            fail_count += 1
    
    return success_count, fail_count


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert images between common formats (JPEG, PNG, BMP, GIF, TIFF, WebP)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s image.png jpeg                    # Convert image.png to JPEG
  %(prog)s photo.jpg webp --output-dir out/  # Convert and save to out/ directory
  %(prog)s images/ png --no-confirm          # Convert all images in directory without confirmation
  %(prog)s pics/ jpeg -o converted/          # Convert all images and save to converted/
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='Input image file or directory'
    )
    
    parser.add_argument(
        'format',
        type=str,
        choices=['jpeg', 'jpg', 'png', 'bmp', 'gif', 'tiff', 'tif', 'webp'],
        help='Output image format'
    )
    
    parser.add_argument(
        '-o', '--output-dir',
        type=str,
        help='Output directory (default: same as input)'
    )
    
    parser.add_argument(
        '--no-confirm',
        action='store_true',
        help='Skip confirmation when overwriting existing files'
    )
    
    parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='Do not process subdirectories recursively (only for directory input)'
    )
    
    return parser.parse_args()


def main():
    """Main entry point for the CLI tool."""
    args = parse_args()
    
    input_path = Path(args.input)
    output_format = args.format.lower()
    output_dir = Path(args.output_dir) if args.output_dir else None
    
    if not input_path.exists():
        print(f"Error: Path not found: {input_path}", file=sys.stderr)
        return 1
    
    # Process file or directory
    if input_path.is_file():
        success = process_file(input_path, output_format, output_dir, args.no_confirm)
        return 0 if success else 1
    elif input_path.is_dir():
        success_count, fail_count = process_directory(
            input_path, 
            output_format, 
            output_dir, 
            args.no_confirm,
            recursive=not args.no_recursive
        )
        print(f"\nConversion complete: {success_count} succeeded, {fail_count} failed")
        return 0 if fail_count == 0 else 1
    else:
        print(f"Error: Invalid path: {input_path}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
