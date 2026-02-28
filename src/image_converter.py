#!/usr/bin/env python3
"""
Image Converter CLI Tool

Converts images between common formats including JPEG, PNG, BMP, GIF, TIFF, and WebP.
"""

import argparse
import functools
import logging
import os
import platform
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from tqdm import tqdm

# Initialize logger
logger = logging.getLogger(__name__)


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


@functools.lru_cache(maxsize=1)
def _check_avif_support() -> bool:
    """Check if AVIF format is supported by Pillow.

    Returns:
        True if AVIF is supported, False otherwise
    """
    try:
        from PIL import Image, features

        # PIL.features.check()でAVIFエンコーダーの有無を確認
        # pillow-avif-pluginがインストールされていれば自動的に統合される
        return features.check('avif') or '.avif' in Image.registered_extensions()
    except Exception:
        return False


# Pillowのインポート（ImportErrorは後でチェック）
try:
    from PIL import Image

    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    Image = None  # type: ignore


@functools.lru_cache(maxsize=1)
def get_supported_formats() -> dict[str, str]:
    """Get dictionary of supported file extensions and their PIL format names.

    Returns:
        Dict mapping file extensions (e.g., '.jpg') to PIL format names (e.g., 'JPEG')
    """
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

    return fmts


def is_supported_format(file_path: Path) -> bool:
    """Check if the file extension is supported.

    Args:
        file_path: Path to the file to check

    Returns:
        True if the file extension is supported, False otherwise
    """
    return file_path.suffix.lower() in get_supported_formats()


def _normalize_format(format_str: str) -> str:
    """Normalize format string to PIL format name.

    Args:
        format_str: Format string (e.g., 'jpg', 'jpeg', 'tif')

    Returns:
        Normalized PIL format name (e.g., 'JPEG', 'TIFF')
    """
    format_upper = format_str.upper()
    if format_upper == 'JPG':
        return 'JPEG'
    elif format_upper == 'TIF':
        return 'TIFF'
    return format_upper


def _resolve_output_dir(img_file: Path, input_dir: Path, output_dir: Path | None, recursive: bool) -> Path:
    """Resolve output directory for an image file.

    Args:
        img_file: Path to the image file being processed
        input_dir: Root input directory
        output_dir: Optional output directory
        recursive: Whether processing recursively

    Returns:
        Resolved output directory path
    """
    actual_output_dir = output_dir if output_dir else input_dir / 'converted'
    if recursive:
        rel_path = img_file.parent.relative_to(input_dir)
        return actual_output_dir / rel_path
    else:
        return actual_output_dir


def get_output_path(input_path: Path, output_format: str, output_dir: Path | None = None) -> Path:
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
            return output_dir / f'{stem}.{output_format.lower()}'
        else:
            # If no output directory is specified, create a "converted" folder in the same directory
            default_output_dir = input_path.parent / 'converted'
            default_output_dir.mkdir(parents=True, exist_ok=True)
            return default_output_dir / f'{input_path.stem}.{output_format.lower()}'
    except OSError as e:
        raise OSError(f'Failed to create output directory: {e}') from e


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
        raise SecurityError(f'Invalid path or broken symlink: {path}') from e

    if not resolved_path.exists():
        raise FileNotFoundError(f'File not found: {path}')

    # Check if it's a file (not a directory or special file)
    if resolved_path.is_file():
        # Check file size
        try:
            file_size = resolved_path.stat().st_size
            if file_size > max_size:
                raise SecurityError(
                    f'File too large: {file_size / 1_000_000:.1f}MB (max: {max_size / 1_000_000:.0f}MB)'
                )
        except OSError as e:
            raise SecurityError(f'Cannot access file: {e}') from e

    return resolved_path


def _is_animated_image(img) -> bool:
    """Check if an image is animated.

    Args:
        img: PIL Image object

    Returns:
        True if image is animated, False otherwise
    """
    return getattr(img, 'is_animated', False) or (hasattr(img, 'n_frames') and img.n_frames > 1)


def _get_animation_formats() -> list[str]:
    """Get list of formats that support animation.

    Returns:
        List of format names that support animation
    """
    formats = ['WEBP', 'GIF']
    if _check_avif_support():
        formats.append('AVIF')
    return formats


def _save_animated_image(img, output_path: Path, output_format: str, lossless: bool) -> None:
    """Save an animated image with appropriate settings.

    Args:
        img: PIL Image object (animated)
        output_path: Path to save the image
        output_format: Target format
        lossless: Use lossless compression
    """
    save_kwargs = {
        'format': output_format,
        'save_all': True,
        'duration': img.info.get('duration', 100),
        'loop': img.info.get('loop', 0),
    }

    # WebPとAVIFの場合は最適化オプションを追加
    if output_format in ['WEBP', 'AVIF']:
        save_kwargs['optimize'] = True
        if lossless:
            save_kwargs['lossless'] = True
        elif output_format == 'WEBP':
            save_kwargs['quality'] = 80

    img.save(output_path, **save_kwargs)


def _convert_transparent_to_rgb(img):
    """Convert an image with transparency to RGB with white background.

    Args:
        img: PIL Image object with transparency

    Returns:
        PIL Image object in RGB mode
    """
    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
    if img.mode == 'P':
        img = img.convert('RGBA')
    rgb_img.paste(img, mask=img.split()[-1] if img.mode in ['RGBA', 'LA'] else None)
    return rgb_img


def convert_image(input_path: Path, output_path: Path, output_format: str, lossless: bool = False) -> bool:
    """Convert an image from one format to another.

    Args:
        input_path: Path to the input image file
        output_path: Path to the output image file
        output_format: Target format (e.g., 'JPEG', 'PNG', 'WEBP')
        lossless: Use lossless compression for WebP (default: False)

    Returns:
        True if conversion was successful, False otherwise

    Raises:
        ConversionError: If conversion fails with specific error details
    """
    try:
        with Image.open(input_path) as img:
            # アニメーション画像かチェック
            if _is_animated_image(img) and output_format in _get_animation_formats():
                _save_animated_image(img, output_path, output_format, lossless)
                return True

            # 透過性を保持しない形式のみ白背景合成
            if output_format in ['JPEG', 'BMP'] and img.mode in ['RGBA', 'LA', 'P']:
                img = _convert_transparent_to_rgb(img)

            # WebP/AVIFのロスレス圧縮
            if output_format in ['WEBP', 'AVIF'] and lossless:
                img.save(output_path, format=output_format, lossless=True)
            else:
                img.save(output_path, format=output_format)
            return True
    except OSError as e:
        # File I/O errors, permission denied, disk full, etc.
        logger.error(f'File operation failed for {input_path}: {e}')
        logger.error(f'[開発者向け] 詳細なスタックトレース:\n{traceback.format_exc()}')
        return False
    except MemoryError as e:
        # Out of memory (very large images)
        logger.error(f'Insufficient memory to process {input_path}: {e}')
        logger.error(f'[開発者向け] 詳細なスタックトレース:\n{traceback.format_exc()}')
        return False
    except ValueError as e:
        # Invalid image data or format issues
        logger.error(f'Invalid image format in {input_path}: {e}')
        logger.error(f'[開発者向け] 詳細なスタックトレース:\n{traceback.format_exc()}')
        return False
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f'Unexpected error converting {input_path}: {type(e).__name__}: {e}')
        logger.error(f'[開発者向け] 詳細なスタックトレース:\n{traceback.format_exc()}')
        return False


def process_file(
    input_path: Path,
    output_format: str,
    output_dir: Path | None = None,
    no_confirm: bool = False,
    verbose: bool = True,
    lossless: bool = False,
    skip_existing: bool = False,
) -> tuple[bool, bool]:
    """
    Process a single image file.

    Args:
        input_path: Path to the input image file
        output_format: Target format (e.g., 'jpeg', 'png', 'webp')
        output_dir: Optional output directory
        no_confirm: Skip confirmation for overwriting existing files
        verbose: Print conversion messages (default: True)
        lossless: Use lossless compression for WebP (default: False)
        skip_existing: Skip if output file already exists (default: False)

    Returns:
        Tuple of (success: bool, skipped: bool)
        - (True, False): Successfully converted
        - (False, False): Failed to convert
        - (False, True): Skipped (file already exists)
    """
    if not input_path.is_file():
        logger.error(f'File not found: {input_path}')
        return False, False

    if not is_supported_format(input_path):
        logger.error(f'Unsupported file format: {input_path.suffix}')
        return False, False

    # Get the PIL format name
    format_upper = _normalize_format(output_format)

    output_path = get_output_path(input_path, output_format, output_dir)

    # Check if output file already exists
    if output_path.exists():
        if skip_existing:
            if verbose:
                print(f'Skipped (already exists): {input_path}')
            return False, True  # Skipped
        if not no_confirm:
            response = input(f'File {output_path} already exists. Overwrite? (y/n): ')
            if response.lower() != 'y':
                print(f'Skipped: {input_path}')
                return False, True  # Skipped

    # Convert the image
    if convert_image(input_path, output_path, format_upper, lossless):
        if verbose:
            print(f'Converted: {input_path} -> {output_path}')
        return True, False
    else:
        return False, False


def process_directory(
    input_dir: Path,
    output_format: str,
    output_dir: Path | None = None,
    no_confirm: bool = False,
    recursive: bool = True,
    parallel: bool = False,
    workers: int | None = None,
    lossless: bool = False,
) -> tuple[int, int, int]:
    """Process all images in a directory.

    Args:
        input_dir: Path to the input directory
        output_format: Target format (e.g., 'jpeg', 'png', 'webp')
        output_dir: Optional output directory
        no_confirm: Skip confirmation for overwriting existing files
        recursive: Process subdirectories recursively
        lossless: Use lossless compression for WebP (default: False)

    Returns:
        Tuple of (successful_count, failed_count, skipped_count)
    """
    if not input_dir.is_dir():
        logger.error(f'Directory not found: {input_dir}')
        return 0, 0, 0

    # Find all supported image files
    print('Scanning for image files...', flush=True)
    image_files_set = set()
    pattern = '**/*' if recursive else '*'

    supported_formats = get_supported_formats()
    for ext in supported_formats.keys():
        image_files_set.update(input_dir.glob(f'{pattern}{ext}'))
        image_files_set.update(input_dir.glob(f'{pattern}{ext.upper()}'))

    # Exclude files in the output directory to avoid processing already converted files
    actual_output_dir = output_dir if output_dir else input_dir / 'converted'
    try:
        actual_output_dir_resolved = actual_output_dir.resolve()
        image_files = [f for f in sorted(image_files_set) if not f.resolve().is_relative_to(actual_output_dir_resolved)]
    except (ValueError, OSError):
        # If output dir doesn't exist yet or can't be resolved, use all files
        image_files = sorted(image_files_set)

    if not image_files:
        print(f'No supported image files found in {input_dir}')
        return 0, 0, 0

    print(f'Found {len(image_files)} image(s) to convert')

    # 並列処理フラグで分岐
    if parallel:
        return _process_directory_parallel(
            input_dir, output_format, output_dir, no_confirm, recursive, workers, image_files, lossless=lossless
        )

    success_count = 0
    fail_count = 0
    skip_count = 0
    actual_output_dir = output_dir if output_dir else input_dir / 'converted'
    for img_file in tqdm(image_files, desc='Converting images', unit='file'):
        rel_output_dir = _resolve_output_dir(img_file, input_dir, output_dir, recursive)
        success, skipped = process_file(
            img_file, output_format, rel_output_dir, no_confirm, verbose=False, lossless=lossless, skip_existing=False
        )
        if success:
            success_count += 1
        elif skipped:
            skip_count += 1
        else:
            fail_count += 1
    return success_count, fail_count, skip_count


def _check_existing_files(
    image_files: list[Path], output_format: str, input_dir: Path, output_dir: Path | None, recursive: bool
) -> list[Path]:
    """Check which output files already exist.

    Args:
        image_files: List of input image files
        output_format: Target output format
        input_dir: Root input directory
        output_dir: Optional output directory
        recursive: Whether processing recursively

    Returns:
        List of input files whose output files already exist
    """
    existing = []
    for img_file in image_files:
        rel_output_dir = _resolve_output_dir(img_file, input_dir, output_dir, recursive)
        output_path = get_output_path(img_file, output_format, rel_output_dir)
        if output_path.exists():
            existing.append(img_file)
    return existing


def _prompt_overwrite_policy(existing_files: list[Path]) -> str:
    """Prompt user for overwrite policy when existing files are found.

    Args:
        existing_files: List of files that already have outputs

    Returns:
        Policy string: 'all' (overwrite all), 'skip' (skip existing), or 'cancel'
    """
    print(f'\n⚠ Found {len(existing_files)} file(s) that already exist in the output directory.')
    if len(existing_files) <= 5:
        print('Existing files:')
        for f in existing_files:
            print(f'  - {f}')
    else:
        print('First 5 existing files:')
        for f in existing_files[:5]:
            print(f'  - {f}')
        print(f'  ... and {len(existing_files) - 5} more')

    print('\nChoose an action:')
    print('  [a] Overwrite all existing files')
    print('  [s] Skip existing files')
    print('  [c] Cancel operation')

    while True:
        response = input('Your choice (a/s/c): ').strip().lower()
        if response in ['a', 'all']:
            return 'all'
        elif response in ['s', 'skip']:
            return 'skip'
        elif response in ['c', 'cancel']:
            return 'cancel'
        else:
            print("Invalid choice. Please enter 'a', 's', or 'c'.")


def _convert_single_file(args_tuple: tuple) -> tuple[bool, str, bool, str | None]:
    """Convert a single file (wrapper for parallel processing).

    Args:
        args_tuple: Tuple of (img_file, output_format, rel_output_dir, no_confirm, lossless, skip_existing)

    Returns:
        Tuple of (success: bool, file_path: str, skipped: bool, error_message: str | None)
    """
    img_file, output_format, rel_output_dir, no_confirm, lossless, skip_existing = args_tuple
    try:
        success, skipped = process_file(
            img_file,
            output_format,
            rel_output_dir,
            no_confirm,
            verbose=False,
            lossless=lossless,
            skip_existing=skip_existing,
        )
        if not success and not skipped:
            # エラーが発生した場合、エラーメッセージを返す
            error_msg = f'Failed to convert {img_file}'
            return (False, str(img_file), False, error_msg)
        return (success, str(img_file), skipped, None)
    except Exception as e:
        # スタックトレース付きエラーメッセージ
        tb = traceback.format_exc()
        error_msg = f'Error processing {img_file}: {e}\n[開発者向け] 詳細なスタックトレース:\n{tb}'
        return (False, str(img_file), False, error_msg)


def _process_directory_parallel(
    input_dir: Path,
    output_format: str,
    output_dir: Path | None,
    no_confirm: bool,
    recursive: bool,
    workers: int | None,
    image_files: list[Path],
    lossless: bool = False,
) -> tuple[int, int, int]:
    """Process directory with parallel execution.

    Args:
        input_dir: Path to the input directory
        output_format: Target format
        output_dir: Optional output directory
        no_confirm: Skip confirmation for overwriting
        recursive: Process subdirectories recursively
        workers: Number of parallel workers (None for CPU count)
        image_files: List of image files to process
        lossless: Use lossless compression

    Returns:
        Tuple of (successful_count, failed_count, skipped_count)
    """
    max_workers = workers or os.cpu_count() or 1
    success_count = 0
    fail_count = 0
    skip_count = 0

    # Check for existing files before parallel processing
    if not no_confirm:
        print('Checking for existing files...', flush=True)
        existing_files = _check_existing_files(image_files, output_format, input_dir, output_dir, recursive)
        if existing_files:
            policy = _prompt_overwrite_policy(existing_files)
            if policy == 'cancel':
                print('Operation cancelled by user.')
                return 0, 0, 0
            elif policy == 'skip':
                # Remove existing files from the processing list
                existing_set = set(existing_files)
                image_files = [f for f in image_files if f not in existing_set]
                skip_count = len(existing_files)
            elif policy == 'all':
                # Proceed with overwriting, set no_confirm to True for workers
                no_confirm = True

    tasks = []
    for img_file in image_files:
        rel_output_dir = _resolve_output_dir(img_file, input_dir, output_dir, recursive)
        tasks.append((img_file, output_format, rel_output_dir, no_confirm, lossless, False))

    pbar = None
    executor = None
    futures = {}

    try:
        executor = ProcessPoolExecutor(max_workers=max_workers)
        futures = {executor.submit(_convert_single_file, task): task for task in tasks}
        pbar = tqdm(total=len(futures), desc='Converting images', unit='file')

        for future in as_completed(futures):
            try:
                success, img_file, skipped, error_msg = future.result()
                if success:
                    success_count += 1
                elif skipped:
                    skip_count += 1
                else:
                    fail_count += 1
                    # エラーメッセージがあればログに記録
                    if error_msg:
                        logger.error(error_msg)
            except Exception as e:
                logger.error(f'Error in worker: {e}')
                fail_count += 1
            pbar.update(1)
    except KeyboardInterrupt:
        logger.warning('Canceling...')

        # Cancel all pending futures
        for future in futures:
            future.cancel()

        # Shutdown executor immediately without waiting
        if executor:
            executor.shutdown(wait=False, cancel_futures=True)

        # Clean up progress bar
        if pbar:
            pbar.close()

        print('\nCanceled.')
        return success_count, fail_count, skip_count
    finally:
        # Clean up progress bar
        if pbar:
            pbar.close()

        # Ensure executor is properly closed
        if executor:
            executor.shutdown(wait=False, cancel_futures=True)

    return success_count, fail_count, skip_count


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Optional list of arguments (defaults to sys.argv)

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description='Convert images between common formats (JPEG, PNG, BMP, GIF, TIFF, WebP)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s image.png jpeg                    # Convert image.png to JPEG
  %(prog)s photo.jpg webp --output-dir out/  # Convert and save to out/ directory
  %(prog)s images/ png --no-confirm          # Convert all images in directory without confirmation
  %(prog)s pics/ jpeg -o converted/          # Convert all images and save to converted/
        """,
    )

    parser.add_argument('input', type=str, help='Input image file or directory')

    # サポート形式を動的にchoicesへ
    choices = ['jpeg', 'jpg', 'png', 'bmp', 'gif', 'tiff', 'tif', 'webp', 'ico']
    if _check_avif_support():
        choices.append('avif')
    parser.add_argument('format', type=str, choices=choices, help='Output image format')

    parser.add_argument('-o', '--output-dir', type=str, help='Output directory (default: same as input)')

    parser.add_argument(
        '--parallel', '-p', action='store_true', help='Enable parallel processing for batch conversions'
    )
    parser.add_argument(
        '--workers',
        '-w',
        type=int,
        default=None,
        help='Number of parallel workers (default: CPU count, only used with --parallel)',
    )

    parser.add_argument('--no-confirm', action='store_true', help='Skip confirmation when overwriting existing files')

    parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='Do not process subdirectories recursively (only for directory input)',
    )

    parser.add_argument('--lossless', action='store_true', help='Use lossless compression for WebP/AVIF formats')

    return parser.parse_args(args)


def setup_error_log() -> Path:
    """Setup error log directory and return log file path.

    Creates 'log/' directory if it doesn't exist and generates
    a timestamped log file path.

    Returns:
        Path to the error log file (e.g., log/error_20260228_143025.log)

    Raises:
        OSError: If 'log' exists as a file instead of a directory
    """
    log_dir = Path('log')

    # Check if 'log' exists as a file
    if log_dir.exists() and not log_dir.is_dir():
        raise OSError(f"Cannot create log directory: '{log_dir}' exists as a file")

    log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f'error_{timestamp}.log'

    return log_file


def add_error_file_handler(log_file: Path) -> logging.FileHandler:
    """Add a file handler to the logger for error logging.

    Args:
        log_file: Path to the log file

    Returns:
        The created FileHandler instance
    """
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.ERROR)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return file_handler


def write_log_context(log_file: Path, args: argparse.Namespace | None = None) -> None:
    """Write execution context information to the log file.

    Args:
        log_file: Path to the log file
        args: Parsed command-line arguments (optional)
    """
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write('=' * 60 + '\n')
            f.write('Execution Context\n')
            f.write('=' * 60 + '\n')
            f.write(f'Command: {" ".join(sys.argv)}\n')
            f.write(f'OS: {platform.system()} {platform.release()}\n')
            f.write(f'Python: {sys.version.split()[0]}\n')
            f.write(f'Working Directory: {os.getcwd()}\n')

            # Pillow version
            try:
                from PIL import __version__ as pil_version

                f.write(f'Pillow: {pil_version}\n')
            except ImportError:
                f.write('Pillow: Not available\n')

            # Available formats
            try:
                formats = get_supported_formats()
                format_list = ', '.join(sorted(set(formats.values())))
                f.write(f'Supported Formats: {format_list}\n')
            except Exception:
                pass

            # Command-line arguments details
            if args:
                f.write('\nExecution Settings:\n')
                f.write(f'  Input: {args.input}\n')
                f.write(f'  Output Format: {args.format}\n')
                if hasattr(args, 'output_dir') and args.output_dir:
                    f.write(f'  Output Directory: {args.output_dir}\n')
                if hasattr(args, 'parallel') and args.parallel:
                    f.write('  Parallel Processing: Yes')
                    if hasattr(args, 'workers') and args.workers:
                        f.write(f' (workers: {args.workers})')
                    f.write('\n')
                if hasattr(args, 'lossless') and args.lossless:
                    f.write('  Lossless: Yes\n')
                if hasattr(args, 'no_recursive') and args.no_recursive:
                    f.write('  Recursive: No\n')

            f.write(f'Timestamp: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
            f.write('=' * 60 + '\n\n')
    except Exception:
        # エラーログへの書き込み失敗は無視（メインエラーを優先）
        pass


def main() -> int:
    """Main entry point for the CLI tool.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Configure logging
    logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s', stream=sys.stderr)

    # Setup error log file handler at the start
    log_file_path = setup_error_log()
    file_handler = add_error_file_handler(log_file_path)
    error_occurred = False

    try:
        # Check if Pillow is available
        if not PILLOW_AVAILABLE:
            logger.error('Pillow is not installed. Install it with: pip install Pillow')
            error_occurred = True
            return 1

        args = parse_args()

        # Write context information to log file
        write_log_context(log_file_path, args)

        input_path = Path(args.input)
        output_format = args.format.lower()
        output_dir = Path(args.output_dir) if args.output_dir else None

        # Validate input path exists
        if not input_path.exists():
            logger.error(f'Path not found: {input_path}')
            error_occurred = True
            return 1

        # Validate input path for security (only for files)
        if input_path.is_file():
            try:
                input_path = validate_input_path(input_path)
            except (SecurityError, FileNotFoundError) as e:
                logger.error(str(e))
                error_occurred = True
                return 1

        # Process file or directory
        if input_path.is_file():
            success, skipped = process_file(
                input_path, output_format, output_dir, args.no_confirm, lossless=args.lossless
            )
            if not success:
                error_occurred = True
            return 0 if success else 1
        elif input_path.is_dir():
            success_count, fail_count, skip_count = process_directory(
                input_path,
                output_format,
                output_dir,
                args.no_confirm,
                recursive=not args.no_recursive,
                parallel=args.parallel,
                workers=args.workers,
                lossless=args.lossless,
            )
            if fail_count > 0:
                error_occurred = True

            print(f'\nConversion complete: {success_count} succeeded, {fail_count} failed, {skip_count} skipped')
            return 0 if fail_count == 0 else 1
        else:
            logger.error(f'Invalid path: {input_path}')
            error_occurred = True
            return 1

    finally:
        # Cleanup file handler
        if file_handler:
            logger.removeHandler(file_handler)
            file_handler.close()

        # Show log file path if errors occurred, otherwise delete the empty log file
        if error_occurred and log_file_path.exists():
            print(f'\nエラーログを出力しました: {log_file_path.absolute()}')
        elif log_file_path.exists():
            # No errors occurred, remove the empty log file
            try:
                log_file_path.unlink()
            except Exception:
                pass  # Ignore cleanup errors


if __name__ == '__main__':
    sys.exit(main())
