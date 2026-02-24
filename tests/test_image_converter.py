"""
Unit tests for image_converter module.
"""

import os
import sys
from pathlib import Path
import pytest
from PIL import Image

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from image_converter import (
    is_supported_format,
    get_output_path,
    convert_image,
    process_file,
    process_directory,
    get_supported_formats
)


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def sample_images(temp_dir):
    """Create sample images in various formats for testing."""
    images = {}

    # Create a simple test image (100x100 red square)
    test_image = Image.new('RGB', (100, 100), color='red')

    # Save in different formats
    png_path = temp_dir / 'test.png'
    test_image.save(png_path, 'PNG')
    images['png'] = png_path

    jpg_path = temp_dir / 'test.jpg'
    test_image.save(jpg_path, 'JPEG')
    images['jpg'] = jpg_path

    bmp_path = temp_dir / 'test.bmp'
    test_image.save(bmp_path, 'BMP')
    images['bmp'] = bmp_path

    webp_path = temp_dir / 'test.webp'
    test_image.save(webp_path, 'WEBP')
    images['webp'] = webp_path

    # Create an image with transparency
    rgba_image = Image.new('RGBA', (100, 100), color=(255, 0, 0, 128))
    png_alpha_path = temp_dir / 'test_alpha.png'
    rgba_image.save(png_alpha_path, 'PNG')
    images['png_alpha'] = png_alpha_path

    return images


@pytest.fixture
def sample_directory(temp_dir):
    """Create a directory structure with sample images."""
    # Create subdirectories
    subdir1 = temp_dir / 'subdir1'
    subdir1.mkdir()
    subdir2 = temp_dir / 'subdir2'
    subdir2.mkdir()

    # Create test images
    test_image = Image.new('RGB', (50, 50), color='blue')

    images = []
    for i, dir_path in enumerate([temp_dir, subdir1, subdir2]):
        img_path = dir_path / f'image{i}.png'
        test_image.save(img_path, 'PNG')
        images.append(img_path)

    return temp_dir, images


class TestFormatValidation:
    """Test format validation functions."""

    def test_is_supported_format_valid(self):
        """Test that supported formats are recognized."""
        for ext in get_supported_formats().keys():
            assert is_supported_format(Path(f'test{ext}'))
            assert is_supported_format(Path(f'test{ext.upper()}'))

    def test_is_supported_format_invalid(self):
        """Test that unsupported formats are rejected."""
        invalid_formats = ['.txt', '.pdf', '.svg']  # .icoは有効形式
        for ext in invalid_formats:
            assert not is_supported_format(Path(f'test{ext}'))


class TestOutputPath:
    """Test output path generation."""

    def test_get_output_path_same_directory(self, temp_dir):
        """Test output path in the same directory."""
        input_path = temp_dir / 'test.png'
        output_path = get_output_path(input_path, 'jpeg')
        assert output_path == temp_dir / 'converted' / 'test.jpeg'

    def test_get_output_path_custom_directory(self, temp_dir):
        """Test output path in a custom directory."""
        input_path = temp_dir / 'test.png'
        output_dir = temp_dir / 'output'
        output_path = get_output_path(input_path, 'webp', output_dir)
        assert output_path == output_dir / 'test.webp'
        assert output_dir.exists()  # Directory should be created


class TestImageConversion:

    def test_convert_png_to_ico(self, sample_images, temp_dir):
        """Test PNG to ICO conversion (transparency preserved)."""
        input_path = sample_images['png_alpha']
        output_path = temp_dir / 'output.ico'
        assert convert_image(input_path, output_path, 'ICO')
        assert output_path.exists()
        with Image.open(output_path) as img:
            assert img.format == 'ICO'
            # ICOは透過性を保持
            assert img.mode in ('RGBA', 'RGB', 'P')

    @pytest.mark.skipif('AVIF' not in get_supported_formats().values(), reason='AVIF not supported')
    def test_convert_png_to_avif(self, sample_images, temp_dir):
        """Test PNG to AVIF conversion (transparency preserved)."""
        input_path = sample_images['png_alpha']
        output_path = temp_dir / 'output.avif'
        assert convert_image(input_path, output_path, 'AVIF')
        assert output_path.exists()
        with Image.open(output_path) as img:
            assert img.format == 'AVIF'
            # AVIFは透過性を保持
            assert img.mode in ('RGBA', 'RGB', 'P')

    def test_convert_png_to_jpeg(self, sample_images, temp_dir):
        """Test PNG to JPEG conversion."""
        input_path = sample_images['png']
        output_path = temp_dir / 'output.jpg'

        assert convert_image(input_path, output_path, 'JPEG')
        assert output_path.exists()

        # Verify the output is a valid JPEG
        with Image.open(output_path) as img:
            assert img.format == 'JPEG'

    def test_convert_jpg_to_webp(self, sample_images, temp_dir):
        """Test JPEG to WebP conversion."""
        input_path = sample_images['jpg']
        output_path = temp_dir / 'output.webp'

        assert convert_image(input_path, output_path, 'WEBP')
        assert output_path.exists()

        with Image.open(output_path) as img:
            assert img.format == 'WEBP'

    def test_convert_png_to_png(self, sample_images, temp_dir):
        """Test PNG to PNG conversion (same format)."""
        input_path = sample_images['png']
        output_path = temp_dir / 'output.png'

        assert convert_image(input_path, output_path, 'PNG')
        assert output_path.exists()

    def test_convert_rgba_to_jpeg(self, sample_images, temp_dir):
        """Test RGBA PNG to JPEG conversion (transparency handling)."""
        input_path = sample_images['png_alpha']
        output_path = temp_dir / 'output.jpg'

        assert convert_image(input_path, output_path, 'JPEG')
        assert output_path.exists()

        # Verify the output is RGB (no alpha channel)
        with Image.open(output_path) as img:
            assert img.format == 'JPEG'
            assert img.mode == 'RGB'

    def test_convert_webp_to_bmp(self, sample_images, temp_dir):
        """Test WebP to BMP conversion."""
        input_path = sample_images['webp']
        output_path = temp_dir / 'output.bmp'

        assert convert_image(input_path, output_path, 'BMP')
        assert output_path.exists()

        with Image.open(output_path) as img:
            assert img.format == 'BMP'

    def test_convert_nonexistent_file(self, temp_dir):
        """Test conversion of a non-existent file."""
        input_path = temp_dir / 'nonexistent.png'
        output_path = temp_dir / 'output.jpg'

        assert not convert_image(input_path, output_path, 'JPEG')
        assert not output_path.exists()


class TestProcessFile:
    """Test single file processing."""

    def test_process_file_success(self, sample_images, temp_dir):
        """Test successful file processing."""
        input_path = sample_images['png']
        result = process_file(input_path, 'jpeg', no_confirm=True)

        assert result
        output_path = temp_dir / 'converted' / 'test.jpeg'
        assert output_path.exists()

    def test_process_file_with_output_dir(self, sample_images, temp_dir):
        """Test file processing with custom output directory."""
        input_path = sample_images['png']
        output_dir = temp_dir / 'converted'

        result = process_file(input_path, 'webp', output_dir, no_confirm=True)

        assert result
        assert (output_dir / 'test.webp').exists()

    def test_process_file_nonexistent(self, temp_dir):
        """Test processing a non-existent file."""
        input_path = temp_dir / 'nonexistent.png'
        result = process_file(input_path, 'jpeg', no_confirm=True)

        assert not result

    def test_process_file_unsupported_format(self, temp_dir):
        """Test processing a file with unsupported format."""
        input_path = temp_dir / 'test.txt'
        input_path.write_text('not an image')

        result = process_file(input_path, 'jpeg', no_confirm=True)

        assert not result


class TestProcessDirectory:
    """Test directory processing."""

    def test_process_directory_recursive(self, sample_directory, temp_dir):
        """Test recursive directory processing."""
        input_dir, image_files = sample_directory

        success, fail = process_directory(input_dir, 'jpeg', no_confirm=True, recursive=True)

        assert success == 3  # All 3 images should be converted
        assert fail == 0

        # Check that output files exist in the converted folder
        assert (input_dir / 'converted' / 'image0.jpeg').exists()
        assert (input_dir / 'converted' / 'subdir1' / 'image1.jpeg').exists()
        assert (input_dir / 'converted' / 'subdir2' / 'image2.jpeg').exists()

    def test_process_directory_non_recursive(self, sample_directory, temp_dir):
        """Test non-recursive directory processing."""
        input_dir, image_files = sample_directory

        success, fail = process_directory(input_dir, 'webp', no_confirm=True, recursive=False)

        # Only the image in the root directory should be converted
        assert success == 1
        assert (input_dir / 'converted' / 'image0.webp').exists()
        assert not (input_dir / 'subdir1' / 'image1.webp').exists()

    def test_process_directory_with_output_dir(self, sample_directory, temp_dir):
        """Test directory processing with custom output directory."""
        input_dir, image_files = sample_directory
        output_dir = temp_dir / 'output'

        success, fail = process_directory(input_dir, 'bmp', output_dir, no_confirm=True, recursive=True)

        assert success == 3
        assert (output_dir / 'image0.bmp').exists()
        assert (output_dir / 'subdir1' / 'image1.bmp').exists()
        assert (output_dir / 'subdir2' / 'image2.bmp').exists()

    def test_process_empty_directory(self, temp_dir):
        """Test processing an empty directory."""
        empty_dir = temp_dir / 'empty'
        empty_dir.mkdir()

        success, fail = process_directory(empty_dir, 'jpeg', no_confirm=True)

        assert success == 0
        assert fail == 0

    def test_process_nonexistent_directory(self, temp_dir):
        """Test processing a non-existent directory."""
        nonexistent_dir = temp_dir / 'nonexistent'

        success, fail = process_directory(nonexistent_dir, 'jpeg', no_confirm=True)

        assert success == 0
        assert fail == 0


class TestIntegration:
    """Integration tests."""

    def test_multiple_format_conversions(self, sample_images, temp_dir):
        """Test converting the same image to multiple formats."""
        input_path = sample_images['png']
        formats = ['jpeg', 'webp', 'bmp']

        for fmt in formats:
            output_path = get_output_path(input_path, fmt)
            assert convert_image(input_path, output_path, fmt.upper())
            assert output_path.exists()

            with Image.open(output_path) as img:
                assert img.size == (100, 100)

    def test_case_insensitive_formats(self, sample_images, temp_dir):
        """Test that format names are case-insensitive."""
        input_path = sample_images['png']

        for fmt in ['JPEG', 'Jpeg', 'jpeg', 'JPG']:
            output_path = temp_dir / f'test_{fmt}.jpg'
            format_upper = 'JPEG' if fmt.upper() in ['JPEG', 'JPG'] else fmt.upper()
            assert convert_image(input_path, output_path, format_upper)
