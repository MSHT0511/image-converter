def _convert_single_file(args_tuple):
    """Wrapper function for parallel processing."""
    img_file, output_format, rel_output_dir, no_confirm = args_tuple
    try:
        success = process_file(img_file, output_format, rel_output_dir, no_confirm, verbose=False)
        return (success, str(img_file))
    except Exception as e:
        print(f"Error processing {img_file}: {e}", file=sys.stderr)
        return (False, str(img_file))


def _process_directory_parallel(input_dir, output_format, output_dir, no_confirm, recursive, workers, image_files):
    """Process directory with parallel execution."""
    actual_output_dir = output_dir if output_dir else input_dir / "converted"
    max_workers = workers or os.cpu_count()
    success_count = 0
    fail_count = 0
    tasks = []
    for img_file in image_files:
        if recursive:
            rel_path = img_file.parent.relative_to(input_dir)
            rel_output_dir = actual_output_dir / rel_path
        else:
            rel_output_dir = actual_output_dir
        tasks.append((img_file, output_format, rel_output_dir, no_confirm))
    try:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_convert_single_file, task): task for task in tasks}
            with tqdm(total=len(futures), desc="Converting images", unit="file") as pbar:
                for future in as_completed(futures):
                    try:
                        success, img_file = future.result()
                        if success:
                            success_count += 1
                        else:
                            fail_count += 1
                    except Exception as e:
                        print(f"Error in worker: {e}", file=sys.stderr)
                        fail_count += 1
                    pbar.update(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user. Cancelling remaining tasks...", file=sys.stderr)
        # tqdmバーを閉じる
        try:
            pbar.close()
        except Exception:
            pass
    return success_count, fail_count
#!/usr/bin/env python3
"""
Image Converter CLI Tool

Converts images between common formats including JPEG, PNG, BMP, GIF, TIFF, and WebP.
"""


import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 並列処理・進捗バー用
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
import multiprocessing


# Custom Exception Classes
class ImageConverterError(Exception):
    """Base exception for image converter errors."""
    pass


class SecurityError(ImageConverterError):
    """Exception raised for security-related issues."""
    pass


class ConversionError(ImageConverterError):
    """Exception raised when image conversion fails."""
    pass


class UnsupportedFormatError(ConversionError):
    """Exception raised for unsupported image formats."""
    pass

# AVIFサポート判定（遅延評価用）
_avif_support_cached: Optional[bool] = None


def _check_avif_support() -> bool:
    """Check if AVIF format is supported by Pillow."""
    global _avif_support_cached
    if _avif_support_cached is not None:
        return _avif_support_cached

    try:
        from PIL import Image, features
        # PIL.features.check()でAVIFエンコーダーの有無を確認
        # pillow-avif-pluginがインストールされていれば自動的に統合される
        _avif_support_cached = features.check('avif') or '.avif' in Image.registered_extensions()
    except Exception:
        _avif_support_cached = False

    return _avif_support_cached


# Pillowのインポート（ImportErrorは後でチェック）
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    Image = None  # type: ignore



# サポート形式を動的生成（遅延評価用）
_supported_formats_cached: Optional[Dict[str, str]] = None


def get_supported_formats() -> Dict[str, str]:
    """Get dictionary of supported file extensions and their PIL format names.

    Returns:
        Dict mapping file extensions (e.g., '.jpg') to PIL format names (e.g., 'JPEG')
    """
    global _supported_formats_cached
    if _supported_formats_cached is not None:
        return _supported_formats_cached

    fmts = {
        '.jpg': 'JPEG',
        '.jpeg': 'JPEG',
        '.png': 'PNG',
        '.bmp': 'BMP',
        '.gif': 'GIF',
        '.tiff': 'TIFF',
        '.tif': 'TIFF',
        '.webp': 'WEBP',
        '.ico': 'ICO',
    }
    if _check_avif_support():
        fmts['.avif'] = 'AVIF'

    _supported_formats_cached = fmts
    return fmts


def is_supported_format(file_path: Path) -> bool:
    """Check if the file extension is supported.

    Args:
        file_path: Path to the file to check

    Returns:
        True if the file extension is supported, False otherwise
    """
    return file_path.suffix.lower() in get_supported_formats()


def get_output_path(input_path: Path, output_format: str, output_dir: Optional[Path] = None) -> Path:
    """Generate the output file path.

    Args:
        input_path: Path to the input image file
        output_format: Target format (e.g., 'jpeg', 'png')
        output_dir: Optional output directory

    Returns:
        Path object for the output file

    Raises:
        OSError: If directory creation fails
    """
    try:
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            stem = input_path.stem
            return output_dir / f"{stem}.{output_format.lower()}"
        else:
            # If no output directory is specified, create a "converted" folder in the same directory
            default_output_dir = input_path.parent / "converted"
            default_output_dir.mkdir(parents=True, exist_ok=True)
            return default_output_dir / f"{input_path.stem}.{output_format.lower()}"
    except OSError as e:
        raise OSError(f"Failed to create output directory: {e}") from e


def validate_input_path(path: Path, max_size: int = 100_000_000) -> Path:
    """Validate input path for security and size constraints.

    Args:
        path: Path to validate
        max_size: Maximum file size in bytes (default: 100MB)

    Returns:
        Resolved absolute path

    Raises:
        SecurityError: If path validation fails
        FileNotFoundError: If file doesn't exist
    """
    try:
        # Resolve to absolute path and follow symlinks
        resolved_path = path.resolve(strict=True)
    except (OSError, RuntimeError) as e:
        raise SecurityError(f"Invalid path or broken symlink: {path}") from e

    if not resolved_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Check if it's a file (not a directory or special file)
    if resolved_path.is_file():
        # Check file size
        try:
            file_size = resolved_path.stat().st_size
            if file_size > max_size:
                raise SecurityError(
                    f"File too large: {file_size / 1_000_000:.1f}MB "
                    f"(max: {max_size / 1_000_000:.0f}MB)"
                )
        except OSError as e:
            raise SecurityError(f"Cannot access file: {e}") from e

    return resolved_path


def convert_image(input_path: Path, output_path: Path, output_format: str) -> bool:
    """Convert an image from one format to another.

    Args:
        input_path: Path to the input image file
        output_path: Path to the output image file
        output_format: Target format (e.g., 'JPEG', 'PNG', 'WEBP')

    Returns:
        True if conversion was successful, False otherwise

    Raises:
        ConversionError: If conversion fails with specific error details
    """
    try:
        with Image.open(input_path) as img:
            # アニメーションをサポートする形式
            animation_formats = ['WEBP', 'GIF']
            if _check_avif_support():
                animation_formats.append('AVIF')

            # アニメーション画像かチェック
            is_animated = getattr(img, 'is_animated', False) or (hasattr(img, 'n_frames') and img.n_frames > 1)

            # アニメーションを維持する場合
            if is_animated and output_format in animation_formats:
                save_kwargs = {
                    'format': output_format,
                    'save_all': True,
                    'duration': img.info.get('duration', 100),
                    'loop': img.info.get('loop', 0),
                }

                # WebPとAVIFの場合は最適化オプションを追加
                if output_format in ['WEBP', 'AVIF']:
                    save_kwargs['optimize'] = True
                    if output_format == 'WEBP':
                        save_kwargs['quality'] = 80

                img.save(output_path, **save_kwargs)
                return True

            # 透過性を保持しない形式のみ白背景合成
            if output_format in ['JPEG', 'BMP'] and img.mode in ['RGBA', 'LA', 'P']:
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode in ['RGBA', 'LA'] else None)
                img = rgb_img
            # ICO/AVIFは透過性保持（PillowのICO/AVIFはRGBA対応）
            # それ以外は既存通り
            img.save(output_path, format=output_format)
            return True
    except OSError as e:
        # File I/O errors, permission denied, disk full, etc.
        print(f"Error: File operation failed for {input_path}: {e}", file=sys.stderr)
        return False
    except MemoryError as e:
        # Out of memory (very large images)
        print(f"Error: Insufficient memory to process {input_path}: {e}", file=sys.stderr)
        return False
    except ValueError as e:
        # Invalid image data or format issues
        print(f"Error: Invalid image format in {input_path}: {e}", file=sys.stderr)
        return False
    except Exception as e:
        # Catch-all for unexpected errors
        print(f"Error: Unexpected error converting {input_path}: {type(e).__name__}: {e}", file=sys.stderr)
        return False


def process_file(input_path: Path, output_format: str, output_dir: Optional[Path] = None,
                no_confirm: bool = False, verbose: bool = True) -> bool:
    """
    Process a single image file.

    Args:
        input_path: Path to the input image file
        output_format: Target format (e.g., 'jpeg', 'png', 'webp')
        output_dir: Optional output directory
        no_confirm: Skip confirmation for overwriting existing files
        verbose: Print conversion messages (default: True)

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
        if verbose:
            print(f"Converted: {input_path} -> {output_path}")
        return True
    else:
        return False


def process_directory(input_dir: Path, output_format: str, output_dir: Optional[Path] = None,
                     no_confirm: bool = False, recursive: bool = True,
                     parallel: bool = False, workers: Optional[int] = None) -> Tuple[int, int]:
    """Process all images in a directory.

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
    image_files_set = set()
    pattern = '**/*' if recursive else '*'

    supported_formats = get_supported_formats()
    for ext in supported_formats.keys():
        image_files_set.update(input_dir.glob(f"{pattern}{ext}"))
        image_files_set.update(input_dir.glob(f"{pattern}{ext.upper()}"))

    image_files = sorted(image_files_set)  # Convert to sorted list for consistent ordering

    if not image_files:
        print(f"No supported image files found in {input_dir}")
        return 0, 0

    print(f"Found {len(image_files)} image(s) to convert")

    # 並列処理フラグで分岐
    if parallel:
        return _process_directory_parallel(input_dir, output_format, output_dir, no_confirm, recursive, workers, image_files)

    success_count = 0
    fail_count = 0
    actual_output_dir = output_dir if output_dir else input_dir / "converted"
    for img_file in tqdm(image_files, desc="Converting images", unit="file"):
        rel_output_dir = None
        if recursive:
            rel_path = img_file.parent.relative_to(input_dir)
            rel_output_dir = actual_output_dir / rel_path
        else:
            rel_output_dir = actual_output_dir
        if process_file(img_file, output_format, rel_output_dir, no_confirm, verbose=False):
            success_count += 1
        else:
            fail_count += 1
    return success_count, fail_count


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Optional list of arguments (defaults to sys.argv)

    Returns:
        Parsed arguments namespace
    """
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

    # サポート形式を動的にchoicesへ
    choices = ['jpeg', 'jpg', 'png', 'bmp', 'gif', 'tiff', 'tif', 'webp', 'ico']
    if _check_avif_support():
        choices.append('avif')
    parser.add_argument(
        'format',
        type=str,
        choices=choices,
        help='Output image format'
    )

    parser.add_argument(
        '-o', '--output-dir',
        type=str,
        help='Output directory (default: same as input)'
    )

    parser.add_argument(
        '--parallel', '-p',
        action='store_true',
        help='Enable parallel processing for batch conversions'
    )
    parser.add_argument(
        '--workers', '-w',
        type=int,
        default=None,
        help='Number of parallel workers (default: CPU count, only used with --parallel)'
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

    return parser.parse_args(args)


def main() -> int:
    """Main entry point for the CLI tool.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Check if Pillow is available
    if not PILLOW_AVAILABLE:
        print("Error: Pillow is not installed. Install it with: pip install Pillow", file=sys.stderr)
        return 1

    args = parse_args()

    input_path = Path(args.input)
    output_format = args.format.lower()
    output_dir = Path(args.output_dir) if args.output_dir else None

    # Validate input path exists
    if not input_path.exists():
        print(f"Error: Path not found: {input_path}", file=sys.stderr)
        return 1

    # Validate input path for security (only for files)
    if input_path.is_file():
        try:
            input_path = validate_input_path(input_path)
        except (SecurityError, FileNotFoundError) as e:
            print(f"Error: {e}", file=sys.stderr)
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
            recursive=not args.no_recursive,
            parallel=args.parallel,
            workers=args.workers
        )
        print(f"\nConversion complete: {success_count} succeeded, {fail_count} failed")
        return 0 if fail_count == 0 else 1
    else:
        print(f"Error: Invalid path: {input_path}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
