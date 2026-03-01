# エラーハンドリング

このドキュメントでは、Image Converter プロジェクトにおけるエラーハンドリングのベストプラクティスを定義します。

---

## 例外を返さない設計

**関数は例外を発生させる代わりに、`bool` または `tuple` で成功/失敗を返すこと。**

```python
# ✅ 推奨：成功/失敗を戻り値で返す
def convert_image(input_path: Path, output_format: str, output_dir: Path | None = None,
                  lossless: bool = False) -> bool:
    """Convert an image file to the specified format.

    Returns:
        True if conversion succeeded, False otherwise
    """
    try:
        # 変換処理...
        return True
    except Exception as e:
        logger.error(f'Conversion failed: {e}')
        return False

# process_directory は (成功数, 失敗数, スキップ数) のタプルを返す
def process_directory(...) -> tuple[int, int, int]:
    success_count = 0
    fail_count = 0
    skip_count = 0
    # 処理...
    return success_count, fail_count, skip_count
```

### 設計の利点

- **呼び出し側のコードがシンプル**: try-exceptブロックが不要
- **明示的な結果**: 成功/失敗が戻り値で明確
- **バッチ処理に適している**: 1つの失敗が全体を止めない

---

## カスタム例外階層

**プロジェクト固有の例外は、カスタム例外階層を使用すること。**

### 例外クラスの定義

```python
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
```

### 例外階層の構造

```
ImageConverterError (基底)
  ├─ SecurityError (セキュリティ関連)
  ├─ ConversionError (変換失敗)
  └─ UnsupportedFormatError (未サポート形式)
```

### 使用例

```python
def validate_input_path(path: Path, max_size: int = 100_000_000) -> Path:
    try:
        resolved_path = path.resolve(strict=True)
    except (OSError, RuntimeError) as e:
        raise SecurityError(f'Invalid path or broken symlink: {path}') from e

    if not resolved_path.exists():
        raise FileNotFoundError(f'File not found: {path}')

    file_size = resolved_path.stat().st_size
    if file_size > max_size:
        raise SecurityError(
            f'File too large: {file_size / 1_000_000:.1f}MB (max: {max_size / 1_000_000:.0f}MB)'
        )

    return resolved_path
```

### 例外を発生させるケース

以下の場合には例外を発生させる：

1. **入力検証の失敗**: セキュリティリスクがある場合（`SecurityError`）
2. **ファイルが存在しない**: 必須ファイルが見つからない場合（`FileNotFoundError`）
3. **設定エラー**: 回復不可能な設定ミス（`ValueError`）
4. **システムエラー**: OSレベルのエラー（`OSError`）

### 例外をキャッチするケース

以下の場合には例外をキャッチして `False` を返す：

1. **個別ファイルの変換失敗**: バッチ処理を継続する必要がある場合
2. **オプショナルな処理の失敗**: 処理の継続に影響しない場合
3. **ユーザー操作エラー**: ログに記録して処理を継続

---

## ロギング

**詳細なエラーログを出力し、ユーザーには簡潔なメッセージを表示すること。**

### ロガーの設定

```python
import logging

logger = logging.getLogger(__name__)
```

### エラーログのパターン

```python
# ✅ 推奨：詳細なエラーログ
try:
    # 処理...
    pass
except Exception as e:
    logger.error(f'Failed to convert {input_path}: {e}')
    logger.error(traceback.format_exc())  # スタックトレースも記録
    print(f'Error: Conversion failed. See log file for details.')
    return False
```

### ログレベルの使い分け

| レベル | 用途 | 例 |
|--------|------|-----|
| `logger.error()` | エラーが発生した場合 | 変換失敗、ファイルアクセスエラー |
| `logger.warning()` | 警告（処理は継続） | キャンセル操作、スキップされたファイル |
| `logger.info()` | 重要な情報 | 処理開始、処理完了の統計 |
| `logger.debug()` | デバッグ情報 | 詳細な処理ステップ |

### ユーザー向けメッセージ

**原則**: 簡潔でわかりやすく、ログファイルへ誘導する。

```python
# ✅ 良い例
print(f'Error: Conversion failed. See log file for details.')
print(f'Warning: {skipped_count} files were skipped.')
print(f'Success: Converted {success_count} files.')

# ❌ 悪い例
print(f'Error: PIL.UnidentifiedImageError: cannot identify image file')  # 技術的すぎる
print(f'エラーが発生しました')  # 情報が不足
```

### ログファイルの出力先

プロジェクトでは `log/` ディレクトリにログファイルを出力：

```
log/
  └── image_converter_YYYYMMDD_HHMMSS.log
```

エラーメッセージでは、このログファイルの場所を明示的に伝える。

---

## エラーハンドリングのベストプラクティス

### 1. 具体的な例外をキャッチする

```python
# ✅ 推奨
try:
    img = Image.open(input_path)
except (OSError, IOError) as e:
    logger.error(f'Failed to open image: {e}')
    return False

# ❌ 非推奨：広範囲すぎる
try:
    img = Image.open(input_path)
except Exception:  # 全ての例外をキャッチするのは避ける
    return False
```

### 2. 例外チェーンを使用する

```python
# ✅ 推奨：from e で元の例外を保持
try:
    resolved_path = path.resolve(strict=True)
except (OSError, RuntimeError) as e:
    raise SecurityError(f'Invalid path: {path}') from e

# ❌ 非推奨：元の例外情報が失われる
try:
    resolved_path = path.resolve(strict=True)
except (OSError, RuntimeError) as e:
    raise SecurityError(f'Invalid path: {path}')
```

### 3. リソースのクリーンアップ

```python
# ✅ 推奨：contextマネージャーを使用
try:
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # 処理...
        pass
except KeyboardInterrupt:
    logger.warning('Canceling...')
    # contextマネージャーが自動的にクリーンアップ
finally:
    if pbar:
        pbar.close()

# ✅ 推奨：明示的なクリーンアップ
executor = None
try:
    executor = ProcessPoolExecutor(max_workers=max_workers)
    # 処理...
finally:
    if executor:
        executor.shutdown(wait=False, cancel_futures=True)
```

### 4. 早期リターンを活用

```python
# ✅ 推奨：早期リターンで条件チェック
def convert_image(input_path: Path, output_format: str, ...) -> bool:
    if not input_path.exists():
        logger.error(f'File not found: {input_path}')
        return False

    if not is_supported_format(input_path):
        logger.error(f'Unsupported format: {input_path.suffix}')
        return False

    # メイン処理...
    return True

# ❌ 非推奨：深いネストを避ける
def convert_image(input_path: Path, output_format: str, ...) -> bool:
    if input_path.exists():
        if is_supported_format(input_path):
            # メイン処理...
            return True
        else:
            return False
    else:
        return False
```

### 5. コンテキスト情報を含める

```python
# ✅ 推奨：エラーメッセージに十分な情報を含める
logger.error(f'Failed to convert {input_path} to {output_format}: {e}')
logger.error(f'Invalid file size: {file_size / 1_000_000:.1f}MB (max: {max_size / 1_000_000:.0f}MB)')

# ❌ 非推奨：情報が不足
logger.error(f'Conversion failed')
logger.error(f'File too large')
```

---

## まとめ

エラーハンドリングのチェックリスト：

- [ ] 関数は `bool` または `tuple` で成功/失敗を返す
- [ ] 適切なカスタム例外を使用する（`SecurityError`, `ConversionError` など）
- [ ] 詳細なエラーログを記録する（スタックトレース含む）
- [ ] ユーザーには簡潔でわかりやすいメッセージを表示
- [ ] 具体的な例外をキャッチする（`Exception` を避ける）
- [ ] 例外チェーン（`from e`）を使用する
- [ ] リソースのクリーンアップを確実に行う
- [ ] エラーメッセージに十分なコンテキスト情報を含める
