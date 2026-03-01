# テスト規約

このドキュメントでは、Image Converter プロジェクトにおけるテストのベストプラクティスを定義します。

---

## テストフレームワーク

**すべてのテストは pytest で実行すること。**

### テストの実行

```bash
# 通常実行
pytest tests/ -v

# カバレッジ付き
pytest tests/ -v --cov=src --cov-report=term-missing

# HTMLレポート生成
pytest tests/ --cov=src --cov-report=html

# 特定のテストクラスのみ
pytest tests/test_image_converter.py::TestImageConversion -v

# 特定のテスト関数のみ
pytest tests/test_image_converter.py::TestImageConversion::test_convert_image_png_to_jpeg -v
```

### pytest の設定

[pyproject.toml](../pyproject.toml) で設定：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --cov=src --cov-report=term-missing"
```

---

## フィクスチャーの活用

**pytest フィクスチャーを活用してテストコードの重複を削減すること。**

### 基本的なフィクスチャー

```python
import pytest
from pathlib import Path
from PIL import Image

@pytest.fixture
def temp_dir(tmp_path):
    """一時ディレクトリを提供

    Args:
        tmp_path: pytest組み込みフィクスチャー

    Returns:
        Path: 一時ディレクトリのパス
    """
    return tmp_path
```

### サンプル画像生成フィクスチャー

```python
@pytest.fixture
def sample_images(temp_dir):
    """各種フォーマットのサンプル画像を生成

    Args:
        temp_dir: 一時ディレクトリ

    Returns:
        Path: サンプル画像が格納されたディレクトリ
    """
    formats = {
        'test.png': 'PNG',
        'test.jpg': 'JPEG',
        'test.bmp': 'BMP',
        'test.gif': 'GIF',
        'test.tiff': 'TIFF',
        'test.webp': 'WEBP',
    }

    for filename, fmt in formats.items():
        img = Image.new('RGB', (100, 100), color='red')
        img.save(temp_dir / filename, fmt)

    return temp_dir
```

### フィクスチャーのスコープ

| スコープ | 説明 | 用途 |
|---------|------|------|
| `function` | 各テスト関数ごと（デフォルト） | 一時ファイル、サンプル画像 |
| `class` | テストクラスごと | クラス内で共有するデータ |
| `module` | モジュールごと | モジュール内で共有するデータ |
| `session` | テストセッション全体 | 重い初期化処理 |

```python
@pytest.fixture(scope='module')
def expensive_resource():
    """モジュール全体で1回だけ初期化"""
    resource = create_expensive_resource()
    yield resource
    resource.cleanup()
```

---

## クラスベースのテスト編成

**機能ごとにテストクラスを作成し、関連するテストをグループ化すること。**

### テストクラスの構造

```python
class TestSecurityValidation:
    """セキュリティバリデーション関数のテスト"""

    def test_validate_input_path_normal_file(self, temp_dir):
        """通常のファイルが正常にバリデートされることをテスト"""
        test_file = temp_dir / 'test.png'
        test_file.touch()

        validated_path = validate_input_path(test_file)
        assert validated_path.exists()
        assert validated_path.is_absolute()

    def test_validate_input_path_file_too_large(self, temp_dir):
        """サイズ制限を超えるファイルがSecurityErrorを発生させることをテスト"""
        test_file = temp_dir / 'large.png'
        test_file.touch()

        mock_stat_result = MagicMock()
        mock_stat_result.st_size = 150_000_000  # 150MB

        with patch.object(Path, 'stat', return_value=mock_stat_result):
            with pytest.raises(SecurityError, match='File too large'):
                validate_input_path(test_file, max_size=100_000_000)

class TestImageConversion:
    """画像変換機能のテスト"""

    def test_convert_image_png_to_jpeg(self, sample_images):
        """PNG から JPEG への変換が正常に動作することをテスト"""
        input_path = sample_images / 'test.png'
        assert convert_image(input_path, 'jpeg')

    def test_convert_image_with_transparency(self, temp_dir):
        """透過PNG が JPEG に変換される際に白背景になることをテスト"""
        input_path = temp_dir / 'transparent.png'
        img = Image.new('RGBA', (100, 100), (255, 0, 0, 128))
        img.save(input_path, 'PNG')

        assert convert_image(input_path, 'jpeg')
```

### テストクラスの命名規則

| パターン | 例 | 用途 |
|---------|-----|------|
| `Test<機能名>` | `TestImageConversion` | 機能別のテスト |
| `Test<関数名>` | `TestValidateInputPath` | 特定関数のテスト |
| `Test<シナリオ>` | `TestParallelProcessing` | シナリオ別のテスト |

---

## テストの種類

**以下の5種類のテストを網羅すること。**

### 1. 正常系テスト

**基本的な機能が正常に動作することを確認。**

```python
def test_convert_image_png_to_jpeg(self, sample_images):
    """PNG から JPEG への変換が正常に動作することをテスト"""
    input_path = sample_images / 'test.png'
    assert convert_image(input_path, 'jpeg')

    output_path = sample_images / 'converted' / 'test.jpeg'
    assert output_path.exists()
```

### 2. 異常系テスト

**エラーハンドリングが正しく動作することを確認。**

```python
def test_convert_image_unsupported_format(self, temp_dir):
    """未サポート形式への変換が False を返すことをテスト"""
    input_path = temp_dir / 'test.png'
    Image.new('RGB', (100, 100)).save(input_path)

    assert not convert_image(input_path, 'xyz')

def test_convert_image_corrupted_file(self, temp_dir):
    """破損ファイルが適切にエラーハンドリングされることをテスト"""
    input_path = temp_dir / 'corrupted.png'
    input_path.write_text('not an image')

    assert not convert_image(input_path, 'jpeg')
```

### 3. 境界値テスト

**エッジケースが正しく処理されることを確認。**

```python
def test_convert_image_1x1_size(self, temp_dir):
    """1x1 サイズの画像が変換できることをテスト"""
    input_path = temp_dir / 'tiny.png'
    Image.new('RGB', (1, 1)).save(input_path)

    assert convert_image(input_path, 'jpeg')

def test_convert_image_large_size(self, temp_dir):
    """大きな画像（4096x4096）が変換できることをテスト"""
    input_path = temp_dir / 'large.png'
    Image.new('RGB', (4096, 4096), color='blue').save(input_path)

    assert convert_image(input_path, 'jpeg')

def test_process_directory_empty_directory(self, temp_dir):
    """空のディレクトリを処理しても問題ないことをテスト"""
    success, fail, skip = process_directory(temp_dir, 'jpeg')
    assert success == 0
    assert fail == 0
    assert skip == 0
```

### 4. セキュリティテスト

**セキュリティ要件が満たされていることを確認。**

```python
def test_validate_input_path_file_too_large(self, temp_dir):
    """ファイルサイズ制限のテスト"""
    test_file = temp_dir / 'large.png'
    test_file.touch()

    mock_stat_result = MagicMock()
    mock_stat_result.st_size = 150_000_000  # 150MB

    with patch.object(Path, 'stat', return_value=mock_stat_result):
        with pytest.raises(SecurityError, match='File too large'):
            validate_input_path(test_file, max_size=100_000_000)

def test_validate_input_path_broken_symlink(self, temp_dir):
    """壊れたシンボリックリンクが SecurityError を発生させることをテスト"""
    # このテストはWindows環境では管理者権限が必要なのでスキップ
    if platform.system() == 'Windows':
        pytest.skip('Symlink test requires admin privileges on Windows')

    symlink = temp_dir / 'broken_link'
    target = temp_dir / 'nonexistent'

    symlink.symlink_to(target)

    with pytest.raises(SecurityError, match='Invalid path or broken symlink'):
        validate_input_path(symlink)
```

### 5. 並列処理テスト

**並列処理が正常に動作することを確認。**

```python
def test_process_directory_parallel(self, sample_images):
    """並列処理が正常に動作することをテスト"""
    success, fail, skip = process_directory(
        sample_images, 'jpeg', max_workers=2, no_confirm=True
    )

    assert success > 0
    assert fail == 0

def test_process_directory_keyboard_interrupt(self, sample_images):
    """KeyboardInterrupt が適切に処理されることをテスト"""
    # KeyboardInterrupt をシミュレート
    with patch('concurrent.futures.as_completed', side_effect=KeyboardInterrupt):
        success, fail, skip = process_directory(
            sample_images, 'jpeg', max_workers=2, no_confirm=True
        )

    # キャンセルされても部分的な結果が返されることを確認
    assert isinstance(success, int)
    assert isinstance(fail, int)
    assert isinstance(skip, int)
```

---

## モッキング

**`unittest.mock` を活用すること。**

### 基本的なモッキング

```python
from unittest.mock import patch, MagicMock

def test_user_input_overwrite_all(self, sample_images):
    """ユーザーが 'all' を選択した場合のテスト"""
    # builtins.input をモック
    with patch('builtins.input', return_value='all'):
        success, fail, skip = process_directory(sample_images, 'jpeg')
        assert success > 0
```

### ファイルシステムのモッキング

```python
def test_validate_input_path_file_too_large(self, temp_dir):
    """ファイルサイズのモック"""
    test_file = temp_dir / 'large.png'
    test_file.touch()

    # stat() の結果をモック
    mock_stat_result = MagicMock()
    mock_stat_result.st_size = 150_000_000  # 150MB

    with patch.object(Path, 'stat', return_value=mock_stat_result):
        with pytest.raises(SecurityError, match='File too large'):
            validate_input_path(test_file, max_size=100_000_000)
```

### 例外のモッキング

```python
def test_convert_image_pil_error(self, sample_images):
    """PIL のエラーが適切に処理されることをテスト"""
    input_path = sample_images / 'test.png'

    # Image.open() がエラーを発生させるようにモック
    with patch('PIL.Image.open', side_effect=OSError('Mock error')):
        assert not convert_image(input_path, 'jpeg')
```

### モック使用のベストプラクティス

| 原則 | 説明 | 例 |
|------|------|-----|
| **外部依存をモック** | ファイルシステム、ネットワーク、時刻など | `Path.stat()`, `Image.open()` |
| **内部ロジックは実際に実行** | 可能な限り実コードを実行する | 実際のファイルで画像変換をテスト |
| **戻り値を明示** | `return_value` または `side_effect` を設定 | `return_value='all'` |

---

## カバレッジ目標

**テストカバレッジは 90% 以上を維持すること。**

### カバレッジの確認

```bash
# カバレッジレポートを表示
pytest tests/ -v --cov=src --cov-report=term-missing

# HTMLレポート生成
pytest tests/ --cov=src --cov-report=html

# カバレッジ率だけを表示
pytest tests/ --cov=src --cov-report=term | grep 'TOTAL'
```

### カバレッジレポートの読み方

```
Name                        Stmts   Miss  Cover   Missing
---------------------------------------------------------
src/__init__.py                 0      0   100%
src/image_converter.py        380     18    95%   45-48, 123, 456-460
---------------------------------------------------------
TOTAL                         380     18    95%
```

- **Stmts**: 総ステートメント数
- **Miss**: カバーされていないステートメント数
- **Cover**: カバレッジ率
- **Missing**: カバーされていない行番号

### カバレッジを上げるコツ

1. **分岐網羅**: if/else の両方をテスト
2. **例外パス**: try/except の両方をテスト
3. **エッジケース**: 境界値や特殊ケースをテスト
4. **未到達コード**: デッドコードは削除

### CI でのカバレッジチェック

[.github/workflows/test.yml](workflows/test.yml) でカバレッジを自動チェック：

```yaml
- name: Check coverage threshold
  run: |
    coverage report --fail-under=90
```

90% 未満の場合は CI が失敗します。

---

## テストヘルパー関数

**テストコードの重複を削減するヘルパー関数を定義すること。**

### アニメーションGIF作成

```python
def create_animated_gif(path: Path, num_frames: int = 3, duration: int = 100, loop: int = 0):
    """テスト用のアニメーションGIFを作成

    Args:
        path: 保存先パス
        num_frames: フレーム数
        duration: 各フレームの表示時間（ミリ秒）
        loop: ループ回数（0 = 無限）
    """
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
```

### 大きなファイルのモック

```python
def create_large_file_mock(path: Path, size_mb: int):
    """実際のデータを書き込まずに大きなファイルをモック

    Args:
        path: ファイルパス
        size_mb: ファイルサイズ（MB）

    Returns:
        int: ファイルサイズ（バイト）
    """
    path.touch()
    return size_mb * 1_000_000
```

---

## テスト実行のベストプラクティス

### 1. テストの独立性

**各テストは独立して実行可能であること。**

```python
# ✅ 推奨：各テストで独自の一時ディレクトリを使用
def test_convert_image(self, temp_dir):
    input_path = temp_dir / 'test.png'
    # ...

# ❌ 非推奨：グローバルな共有状態を変更
global_counter = 0  # NG

def test_something():
    global global_counter
    global_counter += 1  # 他のテストに影響を与える
```

### 2. テストの順序依存を避ける

```python
# ✅ 推奨：各テストで必要なデータを準備
def test_step1(self, temp_dir):
    data = create_test_data()
    process(data)

def test_step2(self, temp_dir):
    data = create_test_data()  # 独自にデータを準備
    process(data)

# ❌ 非推奨：前のテストの結果に依存
def test_step1(self):
    self.data = create_test_data()  # クラス変数に保存

def test_step2(self):
    process(self.data)  # test_step1 に依存
```

### 3. 適切なアサーション

```python
# ✅ 推奨：具体的なアサーション
assert output_path.exists()
assert output_path.stat().st_size > 0
assert output_path.suffix == '.jpeg'

# ❌ 非推奨：曖昧なアサーション
assert output_path  # 存在しても False になりうる
assert True  # 常に成功
```

---

## テストチェックリスト

新機能を実装する際は、以下を確認すること：

### テストの網羅性
- [ ] 正常系テストを追加した
- [ ] 異常系テストを追加した
- [ ] 境界値テストを追加した（必要に応じて）
- [ ] セキュリティテストを追加した（入力検証が含まれる場合）
- [ ] 並列処理テストを追加した（並列処理が含まれる場合）

### テスト品質
- [ ] フィクスチャーを活用してコードの重複を削減した
- [ ] テストクラスで関連テストをグループ化した
- [ ] モッキングを適切に使用した
- [ ] 各テストは独立して実行可能

### カバレッジ
- [ ] `pytest --cov=src --cov-report=term-missing` を実行した
- [ ] カバレッジ 90% 以上を維持した
- [ ] カバーされていない行がある場合は、理由を説明できる

### CI/CD
- [ ] すべてのテストがローカルでパスする
- [ ] CI でもテストがパスする
- [ ] カバレッジチェックがパスする

---

## まとめ

テスト規約のポイント：

1. **pytest**: すべてのテストは pytest で実行
2. **フィクスチャー**: 重複を削減、再利用可能なテストデータ
3. **5種類のテスト**: 正常系、異常系、境界値、セキュリティ、並列処理
4. **モッキング**: 外部依存をモック、内部ロジックは実コードで実行
5. **カバレッジ 90%**: CI で自動チェック、未カバーは明確に理由を説明
6. **テストの独立性**: 各テストは独立して実行可能、順序依存を避ける

高品質なテストを書くことで、リファクタリングや新機能追加時の安心感が得られます。
