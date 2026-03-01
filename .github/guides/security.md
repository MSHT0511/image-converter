# セキュリティ

このドキュメントでは、Image Converter プロジェクトにおけるセキュリティ要件とベストプラクティスを定義します。

---

## ファイルサイズ制限

**デフォルトで100MB の制限を設けること。**

### 実装パターン

```python
def validate_input_path(path: Path, max_size: int = 100_000_000) -> Path:
    """Validate input path for security and size constraints.

    Args:
        path: Path to validate
        max_size: Maximum file size in bytes (default: 100MB)

    Returns:
        Resolved absolute path

    Raises:
        SecurityError: If path validation fails or file is too large
        FileNotFoundError: If file doesn't exist
    """
    # パス検証...

    # ファイルサイズチェック
    file_size = resolved_path.stat().st_size
    if file_size > max_size:
        raise SecurityError(
            f'File too large: {file_size / 1_000_000:.1f}MB (max: {max_size / 1_000_000:.0f}MB)'
        )

    return resolved_path
```

### サイズ制限の理由

1. **メモリ枯渇の防止**: 巨大な画像ファイルがメモリを消費しすぎるのを防ぐ
2. **DoS攻撃の防止**: 悪意のあるユーザーが大量のリソースを消費するのを防ぐ
3. **処理時間の制限**: 処理が長時間かかるケースを避ける

### サイズ制限のデフォルト値

| ファイルタイプ | デフォルト制限 | 理由 |
|----------------|----------------|------|
| 画像ファイル | 100MB | 一般的な画像ファイルの上限として適切 |

### カスタマイズ可能にする

**ユーザーが必要に応じて制限を変更できるようにする（CLI引数など）。**

```python
# CLI引数として渡せるようにする
parser.add_argument('--max-size', type=int, default=100_000_000,
                    help='Maximum file size in bytes (default: 100MB)')
```

---

## パス検証

**シンボリックリンクを解決し、絶対パスに変換すること。**

### 実装パターン

```python
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
        # strict=True でシンボリックリンクを解決し、存在確認
        resolved_path = path.resolve(strict=True)
    except (OSError, RuntimeError) as e:
        raise SecurityError(f'Invalid path or broken symlink: {path}') from e

    if not resolved_path.exists():
        raise FileNotFoundError(f'File not found: {path}')

    # ファイルタイプのチェック
    if not resolved_path.is_file():
        raise SecurityError(f'Path is not a file: {path}')

    return resolved_path
```

### パス検証の目的

1. **シンボリックリンク対策**: 壊れたシンボリックリンクや無限ループを防ぐ
2. **パストラバーサル対策**: 相対パス（`../`）による意図しないファイルアクセスを防ぐ
3. **存在確認**: 処理実行前にファイルの存在を確認
4. **タイプ確認**: ディレクトリや特殊ファイルではなく、通常のファイルであることを確認

### 検証項目

- [ ] `path.resolve(strict=True)` でシンボリックリンクを解決
- [ ] `path.exists()` でファイルの存在を確認
- [ ] `path.is_file()` でファイルタイプを確認
- [ ] 例外処理で `SecurityError` を発生させる

---

## 出力ディレクトリの除外

**無限ループ防止のため、入力ディレクトリと出力ディレクトリが重複する場合は除外すること。**

### 問題のシナリオ

```
input_dir/
  ├── image1.png
  ├── image2.jpg
  └── converted/       # output_dir が input_dir 内にある
      ├── image1.jpg   # 変換済み
      └── image2.png   # 変換済み
```

再帰的に処理すると、`converted/` 内のファイルも変換対象となり、無限ループに陥る。

### 実装パターン

```python
def process_directory(...):
    # 出力ディレクトリを決定
    actual_output_dir = output_dir if output_dir else input_dir / 'converted'

    # ファイルリストを取得
    all_files = list(input_dir.rglob('*') if recursive else input_dir.glob('*'))

    # 画像ファイルのみをフィルタリング
    image_files = []
    for img_file in all_files:
        if not img_file.is_file():
            continue

        # 出力ディレクトリ内のファイルはスキップ
        if actual_output_dir in img_file.parents:
            continue

        if is_supported_format(img_file):
            image_files.append(img_file)

    # 処理...
```

### 除外ロジックの説明

1. **出力ディレクトリの決定**: ユーザー指定または `input_dir/converted`
2. **親ディレクトリのチェック**: `actual_output_dir in img_file.parents` で親階層をチェック
3. **スキップ**: 出力ディレクトリ内のファイルは処理対象から除外

### エッジケース

| ケース | 動作 |
|--------|------|
| `input_dir == output_dir` | 入力ファイルの変換のみ実行（既存の変換済みファイルはスキップ） |
| `output_dir` が `input_dir` の子 | 子ディレクトリ内のファイルを除外 |
| `output_dir` が `input_dir` の外 | すべてのファイルを処理 |

---

## 入力バリデーション

### ファイル拡張子の検証

**サポートされているフォーマットのみを処理すること。**

```python
def is_supported_format(file_path: Path) -> bool:
    """Check if the file extension is supported.

    Args:
        file_path: Path to the file to check

    Returns:
        True if the file extension is supported, False otherwise
    """
    return file_path.suffix.lower() in get_supported_formats()
```

### 出力フォーマットの検証

```python
def _normalize_format(format_str: str) -> str:
    """Normalize format string to PIL format name.

    Args:
        format_str: Format string (e.g., 'jpg', 'jpeg', 'tif')

    Returns:
        Normalized PIL format name (e.g., 'JPEG', 'TIFF')

    Raises:
        UnsupportedFormatError: If format is not supported
    """
    format_upper = format_str.upper()
    if format_upper == 'JPG':
        return 'JPEG'
    elif format_upper == 'TIF':
        return 'TIFF'

    # サポートされているフォーマットか確認
    if format_upper not in get_supported_formats().values():
        raise UnsupportedFormatError(f'Unsupported format: {format_str}')

    return format_upper
```

### ユーザー入力の検証

**対話的な入力（上書き確認など）は限定された選択肢のみを受け付ける。**

```python
def _prompt_overwrite_policy(existing_files: list[Path]) -> str:
    """Prompt user for overwrite policy when files exist.

    Returns:
        'all', 'skip', or 'cancel'
    """
    while True:
        response = input('Enter choice (a/s/c): ').strip().lower()

        # 有効な入力のみを受け付ける
        if response in ['a', 'all']:
            return 'all'
        elif response in ['s', 'skip']:
            return 'skip'
        elif response in ['c', 'cancel']:
            return 'cancel'
        else:
            print("Invalid choice. Please enter 'a', 's', or 'c'.")
```

---

## リソース制限

### 並列処理のワーカー数制限

**無制限にワーカープロセスを生成しないこと。**

```python
def process_directory(..., max_workers: int | None = None) -> tuple[int, int, int]:
    # デフォルトは CPU 数 × 1.5（上限を設ける）
    if max_workers is None:
        cpu_count = os.cpu_count() or 4
        max_workers = min(int(cpu_count * 1.5), 32)  # 最大32プロセス

    # ProcessPoolExecutor で並列処理
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # 処理...
```

### メモリ使用量の考慮

**大きな画像を処理する際は、メモリ使用量に注意する。**

```python
# 画像を開いた後、不要になったらすぐに閉じる
with Image.open(input_path) as img:
    # 処理...
    img.save(output_path, output_format, **save_kwargs)
# ここで自動的に閉じられる
```

---

## セキュリティチェックリスト

新機能を実装する際は、以下を確認すること：

### 入力検証
- [ ] ファイルサイズ制限を適用している
- [ ] パス検証（シンボリックリンク解決、存在確認）を実施
- [ ] サポートされているフォーマットのみを受け付ける
- [ ] ユーザー入力は限定された選択肢のみ

### リソース保護
- [ ] 並列処理のワーカー数に上限を設けている
- [ ] ファイルハンドルを適切に閉じている
- [ ] メモリ使用量を考慮した実装になっている

### パストラバーサル対策
- [ ] 出力ディレクトリの除外ロジックが実装されている
- [ ] 相対パスによる意図しないアクセスを防いでいる
- [ ] 絶対パスに変換してから処理している

### エラーハンドリング
- [ ] セキュリティエラーは `SecurityError` で明示的に示す
- [ ] 詳細なエラー情報はログに記録（ユーザーには簡潔に通知）
- [ ] 例外チェーンで元のエラー情報を保持

---

## セキュリティスキャン

### Bandit による静的解析

プロジェクトでは Bandit を使用してセキュリティ脆弱性をスキャン：

```bash
# 中・高レベルの問題のみを報告
bandit -r src/ -ll
```

CI/CD パイプラインで自動実行されます（`.github/workflows/security.yml`）。

### pip-audit による依存関係チェック

依存パッケージの既知の脆弱性をチェック：

```bash
pip-audit
```

---

## まとめ

セキュリティのベストプラクティス：

1. **ファイルサイズ制限**: デフォルト100MB、カスタマイズ可能
2. **パス検証**: シンボリックリンク解決、絶対パス化、存在確認
3. **出力ディレクトリ除外**: 無限ループを防ぐ
4. **入力バリデーション**: サポート形式、ユーザー入力の制限
5. **リソース制限**: ワーカー数上限、メモリ使用量の考慮
6. **セキュリティスキャン**: Bandit、pip-audit で定期チェック

新機能実装時は、このチェックリストを必ず確認してください。
