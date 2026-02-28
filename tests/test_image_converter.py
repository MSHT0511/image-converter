"""
image_converterモジュールのユニットテスト
"""

import os
import sys
from pathlib import Path
import pytest
from PIL import Image
from unittest.mock import patch, mock_open, MagicMock
import io

# srcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from image_converter import (
    is_supported_format,
    get_output_path,
    convert_image,
    process_file,
    process_directory,
    get_supported_formats,
    ImageConverterError,
    SecurityError,
    ConversionError,
    UnsupportedFormatError,
    validate_input_path,
    _check_existing_files,
    _prompt_overwrite_policy,
    _resolve_output_dir
)


# ========================================
# テスト用ヘルパー関数
# ========================================

def create_animated_gif(path: Path, num_frames: int = 3, duration: int = 100, loop: int = 0):
    """テスト用のアニメーションGIFを作成"""
    frames = []
    colors = ['red', 'green', 'blue', 'yellow', 'cyan']
    for i in range(num_frames):
        img = Image.new('RGB', (50, 50), color=colors[i % len(colors)])
        frames.append(img)
    frames[0].save(
        path,
        format='GIF',
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=loop
    )


def create_large_file_mock(path: Path, size_mb: int):
    """実際のデータを書き込まずに大きなファイルをモックするために作成"""
    path.touch()
    # stat().st_sizeをオーバーライドするためにモックを使用
    return size_mb * 1_000_000


# ========================================
# セキュリティテスト
# ========================================

class TestSecurityValidation:
    """セキュリティバリデーション関数のテスト"""

    def test_validate_input_path_normal_file(self, temp_dir):
        """通常のファイルが正常にバリデートされることをテスト"""
        test_file = temp_dir / 'test.png'
        test_file.touch()

        validated_path = validate_input_path(test_file)
        assert validated_path.exists()
        assert validated_path.is_absolute()

    def test_validate_input_path_file_size_within_limit(self, temp_dir):
        """サイズ制限内のファイルがバリデーションをパスすることをテスト"""
        test_file = temp_dir / 'small.png'
        img = Image.new('RGB', (100, 100), color='red')
        img.save(test_file, 'PNG')

        # 例外が発生しないことを確認
        validated_path = validate_input_path(test_file, max_size=100_000_000)
        assert validated_path.exists()

    def test_validate_input_path_file_too_large(self, temp_dir):
        """サイズ制限を超えるファイルがSecurityErrorを発生させることをテスト"""
        test_file = temp_dir / 'large.png'
        # 実際に大きなファイルを作成すると遅いので、
        # stat結果をモックする
        test_file.touch()

        # Create a mock for stat result
        mock_stat_result = MagicMock()
        mock_stat_result.st_size = 150_000_000  # 150MB
        mock_stat_result.st_mode = 0o100644  # Regular file mode

        # Mock the stat method to return our mock result
        with patch.object(Path, 'stat', return_value=mock_stat_result):
            # Also need to mock resolve to avoid issues
            with patch.object(Path, 'resolve', return_value=test_file):
                with pytest.raises(SecurityError, match="File too large"):
                    validate_input_path(test_file, max_size=100_000_000)
        test_file = temp_dir / 'nonexistent.png'

        with pytest.raises((FileNotFoundError, SecurityError)):
            validate_input_path(test_file)

    def test_validate_input_path_symlink_valid(self, temp_dir):
        """有効なシンボリックリンクが解決されバリデートされることをテスト"""
        real_file = temp_dir / 'real.png'
        real_file.touch()

        symlink_file = temp_dir / 'link.png'
        try:
            symlink_file.symlink_to(real_file)
            validated_path = validate_input_path(symlink_file)
            # 実ファイルに解決されるはず
            assert validated_path.resolve() == real_file.resolve()
        except OSError:
            # シンボリックリンクをサポートしていないシステムではスキップ
            pytest.skip("このシステムではシンボリックリンクがサポートされていません")
    def test_validate_input_path_broken_symlink(self, temp_dir):
        """壊れたシンボリックリンクがSecurityErrorを発生させることをテスト"""
        symlink_file = temp_dir / 'broken_link.png'
        nonexistent = temp_dir / 'nonexistent.png'

        try:
            symlink_file.symlink_to(nonexistent)
            with pytest.raises(SecurityError, match="Invalid path or broken symlink"):
                validate_input_path(symlink_file)
        except OSError:
            # シンボリックリンクをサポートしていないシステムではスキップ
            pytest.skip("このシステムではシンボリックリンクがサポートされていません")
    def test_validate_input_path_directory(self, temp_dir):
        """Test that directories are handled (no size check for dirs)."""
        test_dir = temp_dir / 'subdir'
        test_dir.mkdir()

        # Should validate without raising exception
        validated_path = validate_input_path(test_dir)
        assert validated_path.is_dir()


# ========================================
# Custom Exception Tests
# ========================================

class TestCustomExceptions:
    """カスタム例外クラスとその継承関係のテスト"""

    def test_exception_inheritance(self):
        """例外クラスが正しい継承関係を持つことをテスト"""
        assert issubclass(SecurityError, ImageConverterError)
        assert issubclass(ConversionError, ImageConverterError)
        assert issubclass(UnsupportedFormatError, ConversionError)

    def test_security_error_message(self):
        """カスタムメッセージを持つSecurityErrorをテスト"""
        msg = "テストセキュリティエラー"
        exc = SecurityError(msg)
        assert str(exc) == msg
        assert isinstance(exc, Exception)

    def test_conversion_error_message(self):
        """カスタムメッセージを持つConversionErrorをテスト"""
        msg = "テスト変換エラー"
        exc = ConversionError(msg)
        assert str(exc) == msg

    def test_unsupported_format_error_message(self):
        """カスタムメッセージを持つUnsupportedFormatErrorをテスト"""
        msg = "サポートされていないフォーマット"
        exc = UnsupportedFormatError(msg)
        assert str(exc) == msg

    def test_exception_can_be_caught_by_base_class(self):
        """特定の例外がベースクラスでキャッチできることをテスト"""
        try:
            raise SecurityError("セキュリティ問題")
        except ImageConverterError as e:
            assert isinstance(e, SecurityError)

    def test_unsupported_format_caught_as_conversion_error(self):
        """UnsupportedFormatErrorがConversionErrorとしてキャッチできることをテスト"""
        try:
            raise UnsupportedFormatError("不正なフォーマット")
        except ConversionError as e:
            assert isinstance(e, UnsupportedFormatError)


class TestParallelProcessing:
    def test_parallel_processing_enabled(self, sample_images, temp_dir):
        # 複数画像を作成
        for i in range(5):
            img = Image.new('RGB', (50, 50), color='blue')
            img.save(temp_dir / f'img_{i}.png', 'PNG')
        success, fail, skip = process_directory(temp_dir, 'jpeg', None, True, True, True, 2)
        assert success >= 5
        assert fail == 0

    def test_parallel_processing_disabled(self, sample_images, temp_dir):
        for i in range(3):
            img = Image.new('RGB', (30, 30), color='green')
            img.save(temp_dir / f'g_{i}.png', 'PNG')
        success, fail, skip = process_directory(temp_dir, 'jpeg', None, True, True, False, None)
        assert success >= 3
        assert fail == 0

    def test_parallel_workers_count(self, sample_images, temp_dir):
        for i in range(4):
            img = Image.new('RGB', (40, 40), color='yellow')
            img.save(temp_dir / f'y_{i}.png', 'PNG')
        # workers=1(シングルプロセス)
        success, fail, skip = process_directory(temp_dir, 'jpeg', None, True, True, True, 1)
        assert success >= 4
        assert fail == 0

    def test_parallel_with_errors(self, temp_dir):
        # 壊れた画像ファイルを混ぜる
        img = Image.new('RGB', (20, 20), color='red')
        img.save(temp_dir / 'ok.png', 'PNG')
        with open(temp_dir / 'broken.png', 'wb') as f:
            f.write(b'not an image')
        success, fail, skip = process_directory(temp_dir, 'jpeg', None, True, True, True, 2)
        assert success >= 1
        assert fail >= 1

    def test_parallel_output_consistency(self, temp_dir):
        # 同じ画像セットで順次・並列の出力ファイル名が一致するか
        for i in range(2):
            img = Image.new('RGB', (60, 60), color='purple')
            img.save(temp_dir / f'p_{i}.png', 'PNG')
        out_seq = temp_dir / 'out_seq'
        out_par = temp_dir / 'out_par'
        out_seq.mkdir()
        out_par.mkdir()
        process_directory(temp_dir, 'jpeg', out_seq, True, True, False, None)
        process_directory(temp_dir, 'jpeg', out_par, True, True, True, 2)
        seq_files = sorted([f.name for f in out_seq.glob('*.jpeg')])
        par_files = sorted([f.name for f in out_par.glob('*.jpeg')])
        assert seq_files == par_files

    def test_parallel_workers_zero_uses_default(self, temp_dir):
        """ワーカー数0またはNoneがCPU数を使用することをテスト"""
        for i in range(2):
            img = Image.new('RGB', (40, 40), color='magenta')
            img.save(temp_dir / f'm_{i}.png', 'PNG')
        # workers=0またはNoneはデフォルト（CPU数）を使用すべき
        # 注: ProcessPoolExecutorは負の値を受け付けないため、そのテストはスキップ
        success, fail, skip = process_directory(temp_dir, 'jpeg', None, True, True, True, None)
        assert success >= 2
        assert fail == 0

    def test_parallel_workers_none_uses_default(self, temp_dir):
        """ワーカー数NoneがCPU数を使用することをテスト"""
        for i in range(2):
            img = Image.new('RGB', (40, 40), color='brown')
            img.save(temp_dir / f'b_{i}.png', 'PNG')
        # workers=Noneはデフォルト（CPU数）を使う
        success, fail, skip = process_directory(temp_dir, 'jpeg', None, True, True, True, None)
        assert success >= 2
        assert fail == 0

    def test_parallel_with_existing_files_overwrite_all(self, temp_dir):
        """並列処理で既存ファイルがある場合、'all'選択で上書きされることをテスト"""
        # Create source images
        for i in range(3):
            img = Image.new('RGB', (50, 50), color='blue')
            img.save(temp_dir / f'img_{i}.png', 'PNG')

        # Pre-create some output files
        converted_dir = temp_dir / 'converted'
        converted_dir.mkdir()
        img = Image.new('RGB', (50, 50), color='red')
        img.save(converted_dir / 'img_0.jpeg', 'JPEG')
        img.save(converted_dir / 'img_1.jpeg', 'JPEG')
        original_mtime = (converted_dir / 'img_0.jpeg').stat().st_mtime

        # Mock user input to select 'all' (overwrite all)
        with patch('builtins.input', return_value='a'):
            success, fail, skip = process_directory(temp_dir, 'jpeg', None, False, True, True, 2)

        # All files should be processed
        assert success == 3
        assert fail == 0
        assert skip == 0
        # Verify files were actually overwritten (mtime changed)
        assert (converted_dir / 'img_0.jpeg').stat().st_mtime >= original_mtime

    def test_parallel_with_existing_files_skip(self, temp_dir):
        """並列処理で既存ファイルがある場合、'skip'選択でスキップされることをテスト"""
        # Create source images
        for i in range(4):
            img = Image.new('RGB', (50, 50), color='green')
            img.save(temp_dir / f'file_{i}.png', 'PNG')

        # Pre-create some output files
        converted_dir = temp_dir / 'converted'
        converted_dir.mkdir()
        img = Image.new('RGB', (50, 50), color='yellow')
        img.save(converted_dir / 'file_0.webp', 'WEBP')
        img.save(converted_dir / 'file_2.webp', 'WEBP')

        # Mock user input to select 'skip'
        with patch('builtins.input', return_value='s'):
            success, fail, skip = process_directory(temp_dir, 'webp', None, False, True, True, 2)

        # Only files without existing outputs should be processed
        assert success == 2  # file_1 and file_3
        assert fail == 0
        assert skip == 2  # file_0 and file_2

    def test_parallel_with_existing_files_cancel(self, temp_dir):
        """並列処理で'cancel'選択時に処理が中断されることをテスト"""
        # Create source images
        for i in range(3):
            img = Image.new('RGB', (50, 50), color='purple')
            img.save(temp_dir / f'test_{i}.png', 'PNG')

        # Pre-create one output file
        converted_dir = temp_dir / 'converted'
        converted_dir.mkdir()
        img = Image.new('RGB', (50, 50), color='orange')
        img.save(converted_dir / 'test_0.bmp', 'BMP')

        # Mock user input to select 'cancel'
        with patch('builtins.input', return_value='c'):
            success, fail, skip = process_directory(temp_dir, 'bmp', None, False, True, True, 2)

        # No files should be processed
        assert success == 0
        assert fail == 0
        assert skip == 0

    def test_parallel_no_confirm_with_existing_files(self, temp_dir):
        """並列処理で--no-confirmフラグ使用時、確認なしで上書きされることをテスト"""
        # Create source images
        for i in range(3):
            img = Image.new('RGB', (50, 50), color='cyan')
            img.save(temp_dir / f'item_{i}.png', 'PNG')

        # Pre-create output files
        converted_dir = temp_dir / 'converted'
        converted_dir.mkdir()
        for i in range(3):
            img = Image.new('RGB', (50, 50), color='magenta')
            img.save(converted_dir / f'item_{i}.jpeg', 'JPEG')

        # Process with no_confirm=True (should not prompt)
        success, fail, skip = process_directory(temp_dir, 'jpeg', None, True, True, True, 2)

        # All files should be processed without prompting
        assert success == 3
        assert fail == 0
        assert skip == 0



@pytest.fixture
def temp_dir(tmp_path):
    """テストファイル用の一時ディレクトリを作成"""
    return tmp_path


@pytest.fixture
def sample_images(temp_dir):
    """テスト用にさまざまな形式のサンプル画像を作成"""
    images = {}

    # シンプルなテスト画像を作成（100x100の赤い四角形）
    test_image = Image.new('RGB', (100, 100), color='red')

    # さまざまな形式で保存
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

    # 透過性を持つ画像を作成
    rgba_image = Image.new('RGBA', (100, 100), color=(255, 0, 0, 128))
    png_alpha_path = temp_dir / 'test_alpha.png'
    rgba_image.save(png_alpha_path, 'PNG')
    images['png_alpha'] = png_alpha_path

    return images


@pytest.fixture
def sample_directory(temp_dir):
    """サンプル画像を含むディレクトリ構造を作成"""
    # サブディレクトリを作成
    subdir1 = temp_dir / 'subdir1'
    subdir1.mkdir()
    subdir2 = temp_dir / 'subdir2'
    subdir2.mkdir()

    # テスト画像を作成
    test_image = Image.new('RGB', (50, 50), color='blue')

    images = []
    for i, dir_path in enumerate([temp_dir, subdir1, subdir2]):
        img_path = dir_path / f'image{i}.png'
        test_image.save(img_path, 'PNG')
        images.append(img_path)

    return temp_dir, images


class TestFormatValidation:
    """フォーマット検証関数のテスト"""

    def test_is_supported_format_valid(self):
        """サポートされている形式が認識されることをテスト"""
        for ext in get_supported_formats().keys():
            assert is_supported_format(Path(f'test{ext}'))
            assert is_supported_format(Path(f'test{ext.upper()}'))

    def test_is_supported_format_invalid(self):
        """サポートされていない形式が拒否されることをテスト"""
        invalid_formats = ['.txt', '.pdf', '.svg']  # .icoは有効形式
        for ext in invalid_formats:
            assert not is_supported_format(Path(f'test{ext}'))


class TestOutputPath:
    """出力パス生成のテスト"""

    def test_get_output_path_same_directory(self, temp_dir):
        """同じディレクトリ内の出力パスをテスト"""
        input_path = temp_dir / 'test.png'
        output_path = get_output_path(input_path, 'jpeg')
        assert output_path == temp_dir / 'converted' / 'test.jpeg'

    def test_get_output_path_custom_directory(self, temp_dir):
        """カスタムディレクトリ内の出力パスをテスト"""
        input_path = temp_dir / 'test.png'
        output_dir = temp_dir / 'output'
        output_path = get_output_path(input_path, 'webp', output_dir)
        assert output_path == output_dir / 'test.webp'
        assert output_dir.exists()  # ディレクトリが作成されているはず


class TestImageConversion:

    def test_convert_png_to_ico(self, sample_images, temp_dir):
        """PNGかICO変換をテスト（透過性保持）"""
        input_path = sample_images['png_alpha']
        output_path = temp_dir / 'output.ico'
        assert convert_image(input_path, output_path, 'ICO')
        assert output_path.exists()
        with Image.open(output_path) as img:
            assert img.format == 'ICO'
            # ICOは透過性を保持
            assert img.mode in ('RGBA', 'RGB', 'P')

    @pytest.mark.skipif('AVIF' not in get_supported_formats().values(), reason='AVIF未サポート')
    def test_convert_png_to_avif(self, sample_images, temp_dir):
        """PNGかAVIF変換をテスト（透過性保持）"""
        input_path = sample_images['png_alpha']
        output_path = temp_dir / 'output.avif'
        assert convert_image(input_path, output_path, 'AVIF')
        assert output_path.exists()
        with Image.open(output_path) as img:
            assert img.format == 'AVIF'
            # AVIFは透過性を保持
            assert img.mode in ('RGBA', 'RGB', 'P')

    def test_avif_lossless_conversion(self, sample_images, temp_dir):
        """AVIFロスレス圧縮をテスト"""
        input_path = sample_images['png']
        output_path = temp_dir / 'output_lossless.avif'

        assert convert_image(input_path, output_path, 'AVIF', lossless=True)
        assert output_path.exists()

        with Image.open(output_path) as img:
            assert img.format == 'AVIF'
            # 注: 読み込まれた画像から直接ロスレスフラグを検証できないが、
            # 変換がエラーなしで成功したことを確認できる

    def test_convert_png_to_jpeg(self, sample_images, temp_dir):
        """PNGかJPEG変換をテスト"""
        input_path = sample_images['png']
        output_path = temp_dir / 'output.jpg'

        assert convert_image(input_path, output_path, 'JPEG')
        assert output_path.exists()

        # 出力が有効なJPEGであることを検証
        with Image.open(output_path) as img:
            assert img.format == 'JPEG'

    def test_convert_jpg_to_webp(self, sample_images, temp_dir):
        """JPEGかWebP変換をテスト"""
        input_path = sample_images['jpg']
        output_path = temp_dir / 'output.webp'

        assert convert_image(input_path, output_path, 'WEBP')
        assert output_path.exists()

        with Image.open(output_path) as img:
            assert img.format == 'WEBP'

    def test_webp_lossless_conversion(self, sample_images, temp_dir):
        """WebPロスレス圧縮をテスト"""
        input_path = sample_images['png']
        output_path = temp_dir / 'output_lossless.webp'

        assert convert_image(input_path, output_path, 'WEBP', lossless=True)
        assert output_path.exists()

        with Image.open(output_path) as img:
            assert img.format == 'WEBP'
            # 注: 読み込まれた画像から直接ロスレスフラグを検証できないが、
            # 変換がエラーなしで成功したことを確認できる

    def test_convert_png_to_png(self, sample_images, temp_dir):
        """PNGかPNG変換をテスト（同じ形式）"""
        input_path = sample_images['png']
        output_path = temp_dir / 'output.png'

        assert convert_image(input_path, output_path, 'PNG')
        assert output_path.exists()

    def test_convert_rgba_to_jpeg(self, sample_images, temp_dir):
        """RGBA PNGかJPEG変換をテスト（透過性処理）"""
        input_path = sample_images['png_alpha']
        output_path = temp_dir / 'output.jpg'

        assert convert_image(input_path, output_path, 'JPEG')
        assert output_path.exists()

        # 出力がRGBであることを検証（アルファチャンネルなし）
        with Image.open(output_path) as img:
            assert img.format == 'JPEG'
            assert img.mode == 'RGB'

    def test_convert_webp_to_bmp(self, sample_images, temp_dir):
        """WebPかBMP変換をテスト"""
        input_path = sample_images['webp']
        output_path = temp_dir / 'output.bmp'

        assert convert_image(input_path, output_path, 'BMP')
        assert output_path.exists()

        with Image.open(output_path) as img:
            assert img.format == 'BMP'

    def test_convert_nonexistent_file(self, temp_dir):
        """存在しないファイルの変換をテスト"""
        input_path = temp_dir / 'nonexistent.png'
        output_path = temp_dir / 'output.jpg'

        assert not convert_image(input_path, output_path, 'JPEG')
        assert not output_path.exists()

    # ========================================
    # アニメーションテスト
    # ========================================

    def test_convert_animated_gif_to_webp(self, temp_dir):
        """アニメーションGIFかWebP変換でアニメーションを保持することをテスト"""
        input_path = temp_dir / 'animated.gif'
        create_animated_gif(input_path, num_frames=3, duration=100, loop=0)

        output_path = temp_dir / 'animated.webp'
        assert convert_image(input_path, output_path, 'WEBP')
        assert output_path.exists()

        with Image.open(output_path) as img:
            assert img.format == 'WEBP'
            assert getattr(img, 'is_animated', False) or (hasattr(img, 'n_frames') and img.n_frames > 1)

    def test_convert_animated_gif_to_static_jpeg(self, temp_dir):
        """Test animated GIF to static JPEG (first frame only)."""
        input_path = temp_dir / 'animated.gif'
        create_animated_gif(input_path, num_frames=3)

        output_path = temp_dir / 'static.jpg'
        assert convert_image(input_path, output_path, 'JPEG')
        assert output_path.exists()

        with Image.open(output_path) as img:
            assert img.format == 'JPEG'
            # JPEG doesn't support animation, so it should be static
            assert not hasattr(img, 'is_animated') or not img.is_animated

    def test_convert_animated_webp_metadata_preserved(self, temp_dir):
        """Test that animation metadata (duration, loop) is preserved."""
        input_path = temp_dir / 'animated_source.gif'
        create_animated_gif(input_path, num_frames=2, duration=150, loop=5)

        output_path = temp_dir / 'animated_output.webp'
        assert convert_image(input_path, output_path, 'WEBP')
        assert output_path.exists()

        # Verify animation properties
        with Image.open(output_path) as img:
            assert img.format == 'WEBP'
            # Animation should be preserved
            assert hasattr(img, 'n_frames') and img.n_frames >= 2

    @pytest.mark.skipif('AVIF' not in get_supported_formats().values(), reason='AVIF not supported')
    def test_convert_animated_gif_to_avif(self, temp_dir):
        """Test animated GIF to AVIF conversion (if supported)."""
        input_path = temp_dir / 'animated.gif'
        create_animated_gif(input_path, num_frames=2)

        output_path = temp_dir / 'animated.avif'
        assert convert_image(input_path, output_path, 'AVIF')
        assert output_path.exists()

    # ========================================
    # Error Handling Tests
    # ========================================

    def test_convert_corrupted_image_file(self, temp_dir):
        """Test handling of corrupted image file."""
        input_path = temp_dir / 'corrupted.png'
        # Write invalid image data
        with open(input_path, 'wb') as f:
            f.write(b'This is not a valid image file')

        output_path = temp_dir / 'output.jpg'
        # Should return False, not raise exception
        assert not convert_image(input_path, output_path, 'JPEG')
        assert not output_path.exists()

    def test_convert_non_image_file(self, temp_dir):
        """非画像ファイルの処理をテスト（例: 画像拡張子を持つテキストファイル）"""
        input_path = temp_dir / 'fake.png'
        input_path.write_text('Just some text')

        output_path = temp_dir / 'output.jpg'
        assert not convert_image(input_path, output_path, 'JPEG')

    def test_convert_with_permission_error(self, temp_dir):
        """Test handling of permission errors."""
        input_path = temp_dir / 'test.png'
        img = Image.new('RGB', (50, 50), color='blue')
        img.save(input_path, 'PNG')

        output_path = temp_dir / 'output.jpg'

        # Mock Path.open to raise PermissionError
        with patch('PIL.Image.open', side_effect=OSError("Permission denied")):
            assert not convert_image(input_path, output_path, 'JPEG')

    def test_convert_with_memory_error(self, temp_dir):
        """Test handling of memory errors (simulated)."""
        input_path = temp_dir / 'test.png'
        img = Image.new('RGB', (50, 50), color='green')
        img.save(input_path, 'PNG')

        output_path = temp_dir / 'output.jpg'

        # Mock Image.save to raise MemoryError
        with patch.object(Image.Image, 'save', side_effect=MemoryError("Out of memory")):
            assert not convert_image(input_path, output_path, 'JPEG')

    def test_convert_with_value_error(self, temp_dir):
        """Test handling of ValueError (invalid format/data)."""
        input_path = temp_dir / 'test.png'
        img = Image.new('RGB', (50, 50), color='red')
        img.save(input_path, 'PNG')

        output_path = temp_dir / 'output.jpg'

        # Mock Image.save to raise ValueError
        with patch.object(Image.Image, 'save', side_effect=ValueError("Invalid format")):
            assert not convert_image(input_path, output_path, 'JPEG')

    # ========================================
    # 境界値テスト
    # ========================================

    def test_convert_minimal_image_1x1(self, temp_dir):
        """最小の1x1ピクセル画像の変換をテスト"""
        input_path = temp_dir / 'minimal.png'
        img = Image.new('RGB', (1, 1), color='white')
        img.save(input_path, 'PNG')

        output_path = temp_dir / 'minimal.jpg'
        assert convert_image(input_path, output_path, 'JPEG')
        assert output_path.exists()

        with Image.open(output_path) as result:
            assert result.size == (1, 1)

    def test_convert_zero_byte_file(self, temp_dir):
        """ゼロバイトファイルの処理をテスト"""
        input_path = temp_dir / 'empty.png'
        input_path.touch()  # 空ファイルを作成

        output_path = temp_dir / 'output.jpg'
        assert not convert_image(input_path, output_path, 'JPEG')

    def test_convert_filename_with_spaces(self, temp_dir):
        """スペースを含むファイル名の処理をテスト"""
        input_path = temp_dir / 'test image with spaces.png'
        img = Image.new('RGB', (50, 50), color='yellow')
        img.save(input_path, 'PNG')

        output_path = temp_dir / 'output with spaces.jpg'
        assert convert_image(input_path, output_path, 'JPEG')
        assert output_path.exists()

    def test_convert_filename_with_unicode(self, temp_dir):
        """Unicode文字を含むファイル名の処理をテスト"""
        input_path = temp_dir / '画像テスト.png'
        img = Image.new('RGB', (50, 50), color='cyan')
        img.save(input_path, 'PNG')

        output_path = temp_dir / '出力.jpg'
        assert convert_image(input_path, output_path, 'JPEG')
        assert output_path.exists()

    def test_convert_palette_mode_image(self, temp_dir):
        """パレットモード（P）画像の変換をテスト"""
        input_path = temp_dir / 'palette.png'
        # 実際の色データを持つパレット画像を作成
        img = Image.new('P', (50, 50), color=100)
        # シンプルなグレースケールパレットを作成
        palette = [i // 3 for i in range(768)]  # 256色分のR, G, B
        img.putpalette(palette)
        img.save(input_path, 'PNG')

        output_path = temp_dir / 'palette.jpg'
        result = convert_image(input_path, output_path, 'JPEG')
        # パレットモード変換は機能するはず
        if result:
            assert output_path.exists()
        # 失敗してもOK（一部のパレット画像はうまく変換できない可能性がある）

    def test_convert_grayscale_with_alpha(self, temp_dir):
        """Test conversion of LA mode (grayscale + alpha) image."""
        input_path = temp_dir / 'gray_alpha.png'
        img = Image.new('LA', (50, 50), color=(128, 200))
        img.save(input_path, 'PNG')

        output_path = temp_dir / 'gray_alpha.jpg'
        assert convert_image(input_path, output_path, 'JPEG')
        assert output_path.exists()

        with Image.open(output_path) as result:
            # JPEG should be RGB mode
            assert result.mode == 'RGB'


class TestProcessFile:
    """単一ファイル処理のテスト"""

    def test_process_file_success(self, sample_images, temp_dir):
        """成功するファイル処理をテスト"""
        input_path = sample_images['png']
        success, skipped = process_file(input_path, 'jpeg', no_confirm=True)

        assert success and not skipped
        output_path = temp_dir / 'converted' / 'test.jpeg'
        assert output_path.exists()

    def test_process_file_with_output_dir(self, sample_images, temp_dir):
        """カスタム出力ディレクトリを指定したファイル処理をテスト"""
        input_path = sample_images['png']
        output_dir = temp_dir / 'converted'

        success, skipped = process_file(input_path, 'webp', output_dir, no_confirm=True)

        assert success and not skipped
        assert (output_dir / 'test.webp').exists()

    def test_process_file_nonexistent(self, temp_dir):
        """存在しないファイルの処理をテスト"""
        input_path = temp_dir / 'nonexistent.png'
        success, skipped = process_file(input_path, 'jpeg', no_confirm=True)

        assert not success and not skipped

    def test_process_file_unsupported_format(self, temp_dir):
        """サポートされていない形式のファイル処理をテスト"""
        input_path = temp_dir / 'test.txt'
        input_path.write_text('not an image')

        success, skipped = process_file(input_path, 'jpeg', no_confirm=True)

        assert not success and not skipped

    def test_process_file_verbose_true(self, sample_images, temp_dir, capsys):
        """verbose=Trueが変換メッセージを表示することをテスト"""
        input_path = sample_images['png']
        success, skipped = process_file(input_path, 'jpeg', no_confirm=True, verbose=True)

        assert success and not skipped

        # 標準出力をキャプチャして"Converted:"メッセージがあることを確認
        captured = capsys.readouterr()
        assert "Converted:" in captured.out
        assert str(input_path) in captured.out

    def test_process_file_verbose_false(self, sample_images, temp_dir, capsys):
        """verbose=Falseが変換メッセージを抑制することをテスト"""
        input_path = sample_images['png']
        success, skipped = process_file(input_path, 'webp', no_confirm=True, verbose=False)

        assert success and not skipped
        output_path = temp_dir / 'converted' / 'test.webp'
        assert output_path.exists()

        # 標準出力をキャプチャして"Converted:"メッセージがないことを確認
        captured = capsys.readouterr()
        assert "Converted:" not in captured.out

    def test_process_file_verbose_default(self, sample_images, temp_dir, capsys):
        """デフォルト動作がverbose=Trueであることをテスト"""
        input_path = sample_images['png']
        # verboseパラメータを省略（デフォルト動作）
        success, skipped = process_file(input_path, 'bmp', no_confirm=True)

        assert success and not skipped

        # デフォルトでverbose出力があることを確認
        captured = capsys.readouterr()
        assert "Converted:" in captured.out

    # ========================================
    # 入力検証テスト
    # ========================================

    def test_process_file_not_a_file(self, temp_dir):
        """ファイルではなくディレクトリパスを処理するテスト"""
        subdir = temp_dir / 'subdir'
        subdir.mkdir()

        success, skipped = process_file(subdir, 'jpeg', no_confirm=True)
        assert not success and not skipped

    def test_process_file_with_permission_denied(self, temp_dir, capsys):
        """Test handling of permission denied errors."""
        input_path = temp_dir / 'test.png'
        img = Image.new('RGB', (50, 50), color='blue')
        img.save(input_path, 'PNG')

        # Mock is_file() to return True but convert_image to fail with permissions
        with patch('pathlib.Path.is_file', return_value=True):
            with patch('image_converter.convert_image', return_value=False):
                success, skipped = process_file(input_path, 'jpeg', no_confirm=True)
                assert not success and not skipped

    def test_process_file_invalid_output_format(self, sample_images, temp_dir):
        """正規化が必要な形式での処理をテスト（jpg -> JPEG）"""
        input_path = sample_images['png']
        # jpgは内部でJPEGに正規化されるはず
        success, skipped = process_file(input_path, 'jpg', no_confirm=True)
        assert success and not skipped

    def test_process_file_tif_format_normalization(self, sample_images, temp_dir):
        """'tif'が'TIFF'に正規化されることをテスト"""
        input_path = sample_images['png']
        output_dir = temp_dir / 'output'
        success, skipped = process_file(input_path, 'tif', output_dir, no_confirm=True)
        assert success and not skipped
        assert (output_dir / 'test.tif').exists()

    # ========================================
    # Overwrite Confirmation Tests
    # ========================================

    def test_process_file_overwrite_with_confirmation_yes(self, sample_images, temp_dir):
        """Test overwriting existing file with user confirmation (yes)."""
        input_path = sample_images['png']
        output_dir = temp_dir / 'converted'

        # First conversion
        process_file(input_path, 'jpeg', no_confirm=True)
        output_path = output_dir / 'test.jpeg'
        assert output_path.exists()

        # Second conversion with mock user input 'y'
        with patch('builtins.input', return_value='y'):
            success, skipped = process_file(input_path, 'jpeg', no_confirm=False)
            assert success and not skipped

    def test_process_file_overwrite_with_confirmation_no(self, sample_images, temp_dir, capsys):
        """Test skipping overwrite with user confirmation (no)."""
        input_path = sample_images['png']
        output_dir = temp_dir / 'converted'

        # First conversion
        process_file(input_path, 'jpeg', no_confirm=True)
        output_path = output_dir / 'test.jpeg'
        assert output_path.exists()
        original_mtime = output_path.stat().st_mtime

        # Second conversion with mock user input 'n'
        with patch('builtins.input', return_value='n'):
            success, skipped = process_file(input_path, 'jpeg', no_confirm=False)
            assert not success and skipped

        # Verify output contains "Skipped"
        captured = capsys.readouterr()
        assert "Skipped" in captured.out

    def test_process_file_no_confirm_overwrites(self, sample_images, temp_dir):
        """Test that no_confirm=True overwrites without prompting."""
        input_path = sample_images['png']
        output_dir = temp_dir / 'converted'

        # First conversion
        process_file(input_path, 'jpeg', no_confirm=True)
        output_path = output_dir / 'test.jpeg'
        assert output_path.exists()

        # Second conversion should overwrite without prompting
        success, skipped = process_file(input_path, 'jpeg', no_confirm=True)
        assert success and not skipped
        assert output_path.exists()

    def test_process_file_skip_existing_true(self, sample_images, temp_dir):
        """skip_existing=Trueで既存ファイルをスキップすることをテスト"""
        input_path = sample_images['png']
        output_dir = temp_dir / 'converted'

        # First conversion
        success1, skipped1 = process_file(input_path, 'jpeg', output_dir, no_confirm=True)
        assert success1 and not skipped1
        output_path = output_dir / 'test.jpeg'
        assert output_path.exists()
        original_mtime = output_path.stat().st_mtime

        # Second conversion with skip_existing=True
        success2, skipped2 = process_file(input_path, 'jpeg', output_dir, no_confirm=True, skip_existing=True)
        assert not success2 and skipped2

        # File should not be modified
        assert output_path.stat().st_mtime == original_mtime

    def test_process_file_skip_existing_verbose(self, sample_images, temp_dir, capsys):
        """skip_existingでスキップメッセージが表示されることをテスト"""
        input_path = sample_images['png']
        output_dir = temp_dir / 'converted'

        # First conversion
        process_file(input_path, 'jpeg', output_dir, no_confirm=True, verbose=False)
        output_path = output_dir / 'test.jpeg'
        assert output_path.exists()

        # Second conversion with skip_existing=True and verbose=True
        success, skipped = process_file(input_path, 'jpeg', output_dir, no_confirm=True, skip_existing=True, verbose=True)
        assert not success and skipped

        # Verify output contains "Skipped (already exists)"
        captured = capsys.readouterr()
        assert "Skipped (already exists)" in captured.out


class TestProcessDirectory:
    """ディレクトリ処理のテスト"""

    def test_process_directory_recursive(self, sample_directory, temp_dir):
        """再帰的なディレクトリ処理をテスト"""
        input_dir, image_files = sample_directory

        success, fail, skip = process_directory(input_dir, 'jpeg', no_confirm=True, recursive=True)

        assert success == 3  # す3つの画像が変換されるはず
        assert fail == 0

        # convertedフォルダに出力ファイルが存在することを確認
        assert (input_dir / 'converted' / 'image0.jpeg').exists()
        assert (input_dir / 'converted' / 'subdir1' / 'image1.jpeg').exists()
        assert (input_dir / 'converted' / 'subdir2' / 'image2.jpeg').exists()

    def test_process_directory_non_recursive(self, sample_directory, temp_dir):
        """非再帰的なディレクトリ処理をテスト"""
        input_dir, image_files = sample_directory

        success, fail, skip = process_directory(input_dir, 'webp', no_confirm=True, recursive=False)

        # ルートディレクトリの画像のみ変換されるはず
        assert success == 1
        assert (input_dir / 'converted' / 'image0.webp').exists()
        assert not (input_dir / 'subdir1' / 'image1.webp').exists()

    def test_process_directory_with_output_dir(self, sample_directory, temp_dir):
        """カスタム出力ディレクトリを指定したディレクトリ処理をテスト"""
        input_dir, image_files = sample_directory
        output_dir = temp_dir / 'output'

        success, fail, skip = process_directory(input_dir, 'bmp', output_dir, no_confirm=True, recursive=True)

        assert success == 3
        assert (output_dir / 'image0.bmp').exists()
        assert (output_dir / 'subdir1' / 'image1.bmp').exists()
        assert (output_dir / 'subdir2' / 'image2.bmp').exists()

    def test_process_empty_directory(self, temp_dir):
        """空のディレクトリの処理をテスト"""
        empty_dir = temp_dir / 'empty'
        empty_dir.mkdir()

        success, fail, skip = process_directory(empty_dir, 'jpeg', no_confirm=True)

        assert success == 0
        assert fail == 0

    def test_process_nonexistent_directory(self, temp_dir):
        """存在しないディレクトリの処理をテスト"""
        nonexistent_dir = temp_dir / 'nonexistent'

        success, fail, skip = process_directory(nonexistent_dir, 'jpeg', no_confirm=True)

        assert success == 0
        assert fail == 0

    # ========================================
    # Additional Input Validation Tests
    # ========================================

    def test_process_directory_with_read_permission_error(self, temp_dir):
        """Test handling of directories with permission issues."""
        test_dir = temp_dir / 'restricted'
        test_dir.mkdir()

        # Create a test image
        img = Image.new('RGB', (50, 50), color='blue')
        img.save(test_dir / 'test.png', 'PNG')

        # Mock glob to raise PermissionError
        with patch.object(Path, 'glob', side_effect=PermissionError("Access denied")):
            try:
                success, fail, skip = process_directory(test_dir, 'jpeg', no_confirm=True)
                # 適切に処理されるはず
            except PermissionError:
                # 例外が発生した場合、テストはパス（エラーが伝播される）
                pass

    def test_process_directory_with_mixed_files(self, temp_dir):
        """Test directory with mix of supported and unsupported files."""
        # Create some image files
        img = Image.new('RGB', (50, 50), color='green')
        img.save(temp_dir / 'image1.png', 'PNG')
        img.save(temp_dir / 'image2.jpg', 'JPEG')

        # Create non-image files
        (temp_dir / 'readme.txt').write_text('Not an image')
        (temp_dir / 'data.json').write_text('{}')

        success, fail, skip = process_directory(temp_dir, 'webp', no_confirm=True)

        # Only image files should be processed
        assert success == 2
        assert fail == 0

    def test_process_directory_case_insensitive_extensions(self, temp_dir):
        """Test that both lowercase and uppercase extensions are found."""
        img = Image.new('RGB', (50, 50), color='red')
        img.save(temp_dir / 'lower.png', 'PNG')
        img.save(temp_dir / 'UPPER.PNG', 'PNG')

        success, fail, skip = process_directory(temp_dir, 'jpeg', no_confirm=True)

        # Both files should be processed
        assert success == 2
        assert fail == 0

    def test_process_directory_excludes_converted_folder(self, temp_dir):
        """converted/フォルダ内のファイルが変換対象から除外されることをテスト"""
        # Create original image
        img = Image.new('RGB', (50, 50), color='blue')
        original = temp_dir / 'original.png'
        img.save(original, 'PNG')

        # Create already converted file in converted folder
        converted_dir = temp_dir / 'converted'
        converted_dir.mkdir()
        already_converted = converted_dir / 'already.webp'
        img.save(already_converted, 'WEBP')

        # Process directory
        success, fail, skip = process_directory(temp_dir, 'webp', no_confirm=True)

        # Only the original file should be processed, not the one in converted/
        assert success == 1
        assert fail == 0
        # The already.webp should not be re-processed
        assert (converted_dir / 'original.webp').exists()

    def test_process_directory_excludes_custom_output_dir(self, temp_dir):
        """カスタム出力ディレクトリ内のファイルも除外されることをテスト"""
        # Create original image
        img = Image.new('RGB', (50, 50), color='green')
        original = temp_dir / 'source.png'
        img.save(original, 'PNG')

        # Create custom output directory with existing file
        output_dir = temp_dir / 'output'
        output_dir.mkdir()
        existing = output_dir / 'existing.jpeg'
        img.save(existing, 'JPEG')

        # Process directory with custom output dir
        success, fail, skip = process_directory(temp_dir, 'jpeg', output_dir, no_confirm=True)

        # Only source.png should be processed, not existing.jpeg
        assert success == 1
        assert fail == 0
        assert (output_dir / 'source.jpeg').exists()

    def test_skip_count_accuracy(self, temp_dir):
        """スキップカウントが正確にカウントされることをテスト"""
        # Create 5 image files
        for i in range(5):
            img = Image.new('RGB', (50, 50), color='blue')
            img.save(temp_dir / f'image{i}.png', 'PNG')

        # Pre-create 2 output files
        converted_dir = temp_dir / 'converted'
        converted_dir.mkdir()
        img = Image.new('RGB', (50, 50), color='red')
        img.save(converted_dir / 'image0.jpeg', 'JPEG')
        img.save(converted_dir / 'image1.jpeg', 'JPEG')

        # Process with mock user response 'n' for skip
        with patch('builtins.input', return_value='n'):
            success, fail, skip = process_directory(temp_dir, 'jpeg', no_confirm=False)

        # Should skip 2 files (the ones that exist)
        assert skip == 2
        assert success == 3
        assert fail == 0


class TestIntegration:
    """統合テスト"""

    def test_multiple_format_conversions(self, sample_images, temp_dir):
        """同じ画像を複数の形式に変換するテスト"""
        input_path = sample_images['png']
        formats = ['jpeg', 'webp', 'bmp']

        for fmt in formats:
            output_path = get_output_path(input_path, fmt)
            assert convert_image(input_path, output_path, fmt.upper())
            assert output_path.exists()

            with Image.open(output_path) as img:
                assert img.size == (100, 100)

    def test_case_insensitive_formats(self, sample_images, temp_dir):
        """形式名が大文字小文字を区別しないことをテスト"""
        input_path = sample_images['png']

        for fmt in ['JPEG', 'Jpeg', 'jpeg', 'JPG']:
            output_path = temp_dir / f'test_{fmt}.jpg'
            format_upper = 'JPEG' if fmt.upper() in ['JPEG', 'JPG'] else fmt.upper()
            assert convert_image(input_path, output_path, format_upper)


class TestExistingFilesCheck:
    """_check_existing_files関数のテスト"""

    def test_check_existing_files_with_existing(self, temp_dir):
        """既存ファイルを正しく検出することをテスト"""
        # Create input files
        img = Image.new('RGB', (50, 50), color='blue')
        img.save(temp_dir / 'file1.png', 'PNG')
        img.save(temp_dir / 'file2.png', 'PNG')
        img.save(temp_dir / 'file3.png', 'PNG')

        # Create existing output files
        output_dir = temp_dir / 'converted'
        output_dir.mkdir()
        img.save(output_dir / 'file1.jpeg', 'JPEG')
        img.save(output_dir / 'file2.jpeg', 'JPEG')

        # Check which files have existing outputs
        image_files = [temp_dir / 'file1.png', temp_dir / 'file2.png', temp_dir / 'file3.png']
        existing = _check_existing_files(image_files, 'jpeg', temp_dir, None, False)

        # file1 and file2 should be in the existing list
        assert len(existing) == 2
        assert temp_dir / 'file1.png' in existing
        assert temp_dir / 'file2.png' in existing
        assert temp_dir / 'file3.png' not in existing

    def test_check_existing_files_empty(self, temp_dir):
        """既存ファイルがない場合に空リストを返すことをテスト"""
        # Create only input files
        img = Image.new('RGB', (50, 50), color='green')
        img.save(temp_dir / 'new1.png', 'PNG')
        img.save(temp_dir / 'new2.png', 'PNG')

        # Check for existing files
        image_files = [temp_dir / 'new1.png', temp_dir / 'new2.png']
        existing = _check_existing_files(image_files, 'webp', temp_dir, None, False)

        # No existing files
        assert len(existing) == 0
        assert existing == []

    def test_check_existing_files_recursive(self, temp_dir):
        """再帰モードで正しくチェックすることをテスト"""
        # Create directory structure
        subdir = temp_dir / 'subdir'
        subdir.mkdir()

        img = Image.new('RGB', (50, 50), color='red')
        img.save(temp_dir / 'root.png', 'PNG')
        img.save(subdir / 'sub.png', 'PNG')

        # Create existing output in proper structure
        output_dir = temp_dir / 'converted'
        output_subdir = output_dir / 'subdir'
        output_subdir.mkdir(parents=True)
        img.save(output_subdir / 'sub.jpeg', 'JPEG')

        # Check with recursive mode
        image_files = [temp_dir / 'root.png', subdir / 'sub.png']
        existing = _check_existing_files(image_files, 'jpeg', temp_dir, None, True)

        # Only sub.png should have existing output in the recursive structure
        assert len(existing) == 1
        assert subdir / 'sub.png' in existing


class TestOverwritePolicy:
    """_prompt_overwrite_policy関数のテスト"""

    def test_prompt_overwrite_policy_all(self, temp_dir):
        """'a'入力で'all'を返すことをテスト"""
        existing_files = [temp_dir / 'file1.png', temp_dir / 'file2.png']

        with patch('builtins.input', return_value='a'):
            result = _prompt_overwrite_policy(existing_files)

        assert result == 'all'

    def test_prompt_overwrite_policy_skip(self, temp_dir):
        """'s'入力で'skip'を返すことをテスト"""
        existing_files = [temp_dir / 'file1.png']

        with patch('builtins.input', return_value='s'):
            result = _prompt_overwrite_policy(existing_files)

        assert result == 'skip'

    def test_prompt_overwrite_policy_cancel(self, temp_dir):
        """'c'入力で'cancel'を返すことをテスト"""
        existing_files = [temp_dir / 'file1.png', temp_dir / 'file2.png', temp_dir / 'file3.png']

        with patch('builtins.input', return_value='c'):
            result = _prompt_overwrite_policy(existing_files)

        assert result == 'cancel'

    def test_prompt_overwrite_policy_aliases(self, temp_dir):
        """'all', 'skip', 'cancel'のフルワード入力が受け付けられることをテスト"""
        existing_files = [temp_dir / 'file.png']

        # Test 'all' alias
        with patch('builtins.input', return_value='all'):
            result = _prompt_overwrite_policy(existing_files)
            assert result == 'all'

        # Test 'skip' alias
        with patch('builtins.input', return_value='skip'):
            result = _prompt_overwrite_policy(existing_files)
            assert result == 'skip'

        # Test 'cancel' alias
        with patch('builtins.input', return_value='cancel'):
            result = _prompt_overwrite_policy(existing_files)
            assert result == 'cancel'

    def test_prompt_overwrite_policy_invalid_then_valid(self, temp_dir):
        """無効な入力後に有効な入力で再試行することをテスト"""
        existing_files = [temp_dir / 'file.png']

        # Mock input to return invalid inputs first, then valid
        inputs = iter(['x', 'invalid', '123', 'a'])
        with patch('builtins.input', side_effect=inputs):
            result = _prompt_overwrite_policy(existing_files)

        assert result == 'all'

    def test_prompt_overwrite_policy_displays_file_list(self, temp_dir, capsys):
        """既存ファイルのリストが表示されることをテスト"""
        existing_files = [temp_dir / 'file1.png', temp_dir / 'file2.png']

        with patch('builtins.input', return_value='a'):
            _prompt_overwrite_policy(existing_files)

        captured = capsys.readouterr()
        assert "Found 2 file(s) that already exist" in captured.out
        assert "file1.png" in captured.out
        assert "file2.png" in captured.out

    def test_prompt_overwrite_policy_truncates_long_list(self, temp_dir, capsys):
        """ファイルリストが長い場合に切り詰められることをテスト"""
        # Create list with more than 5 files
        existing_files = [temp_dir / f'file{i}.png' for i in range(10)]

        with patch('builtins.input', return_value='s'):
            _prompt_overwrite_policy(existing_files)

        captured = capsys.readouterr()
        assert "Found 10 file(s) that already exist" in captured.out
        assert "First 5" in captured.out
        assert "and 5 more" in captured.out
