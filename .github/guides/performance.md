# パフォーマンス最適化

このドキュメントでは、Image Converter プロジェクトにおけるパフォーマンス最適化のベストプラクティスを定義します。

---

## 並列処理

**`ProcessPoolExecutor` を使用してマルチコア CPU を活用すること。**

### 基本的な実装パターン

```python
from concurrent.futures import ProcessPoolExecutor, as_completed

def process_directory(..., max_workers: int | None = None) -> tuple[int, int, int]:
    """Process all images in a directory with parallel processing.

    Args:
        max_workers: Maximum number of worker processes (default: CPU count × 1.5)

    Returns:
        Tuple of (success_count, fail_count, skip_count)
    """
    # デフォルトは CPU 数 × 1.5
    if max_workers is None:
        cpu_count = os.cpu_count() or 4
        max_workers = int(cpu_count * 1.5)

    # タスクリストを作成
    tasks = []
    for img_file in image_files:
        tasks.append((img_file, output_format, output_dir, no_confirm, lossless, False))

    # ProcessPoolExecutor で並列処理
    success_count = 0
    fail_count = 0
    skip_count = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_convert_single_file, task): task for task in tasks}

        for future in as_completed(futures):
            success, img_file, skipped, error_msg = future.result()
            if success:
                success_count += 1
            elif skipped:
                skip_count += 1
            else:
                fail_count += 1

    return success_count, fail_count, skip_count
```

### ワーカー数の決定

| CPU コア数 | 推奨ワーカー数 | 理由 |
|-----------|---------------|------|
| 4コア | 6ワーカー | CPU × 1.5（I/O待ち時間を考慮） |
| 8コア | 12ワーカー | 画像処理は I/O バウンドな側面もある |
| 16コア | 24ワーカー | 最適なスループット |

**計算式**: `max_workers = int(CPU数 × 1.5)`

### I/O バウンド vs CPU バウンド

| 処理タイプ | 特性 | 最適化戦略 |
|-----------|------|-----------|
| **I/O バウンド** | ファイル読み書き、ディスク待ち | ワーカー数を増やす（CPU × 1.5〜2） |
| **CPU バウンド** | 画像デコード、エンコード | ワーカー数 = CPU 数 |
| **混合** | 画像変換（両方の特性を持つ） | CPU × 1.5（バランスを取る） |

Image Converter は混合型なので、`CPU × 1.5` が最適。

### KeyboardInterrupt 対応

**ユーザーがキャンセルした場合は即座に終了すること。**

```python
def process_directory(...):
    executor = None
    pbar = None
    futures = {}

    try:
        executor = ProcessPoolExecutor(max_workers=max_workers)
        futures = {executor.submit(_convert_single_file, task): task for task in tasks}
        pbar = tqdm(total=len(futures), desc='Converting images', unit='file')

        for future in as_completed(futures):
            # 処理...
            pbar.update(1)

    except KeyboardInterrupt:
        logger.warning('Canceling...')

        # すべての未完了タスクをキャンセル
        for future in futures:
            future.cancel()

        # Executor を即座にシャットダウン
        if executor:
            executor.shutdown(wait=False, cancel_futures=True)

        # プログレスバーをクリーンアップ
        if pbar:
            pbar.close()

        print('\nCanceled.')
        return success_count, fail_count, skip_count

    finally:
        # クリーンアップを確実に実行
        if pbar:
            pbar.close()

        if executor:
            executor.shutdown(wait=False, cancel_futures=True)

    return success_count, fail_count, skip_count
```

### ワーカー関数の設計

**ワーカー関数は引数をタプルで受け取る設計にすること。**

```python
def _convert_single_file(args: tuple) -> tuple[bool, Path, bool, str]:
    """Worker function for parallel processing.

    Args:
        args: Tuple of (img_file, output_format, output_dir, no_confirm, lossless, quiet)

    Returns:
        Tuple of (success, img_file, skipped, error_msg)
    """
    img_file, output_format, output_dir, no_confirm, lossless, quiet = args

    try:
        # 変換処理...
        return True, img_file, False, ''
    except Exception as e:
        error_msg = f'Failed to convert {img_file}: {e}'
        return False, img_file, False, error_msg
```

### エラーハンドリング

**ワーカー内で例外をキャッチし、結果としてタプルを返すこと。**

```python
# ✅ 推奨：ワーカー内で例外をキャッチ
def _convert_single_file(args: tuple) -> tuple[bool, Path, bool, str]:
    try:
        # 処理...
        return True, img_file, False, ''
    except Exception as e:
        # 例外をキャッチして、エラーメッセージとして返す
        return False, img_file, False, str(e)

# ❌ 非推奨：例外を伝播させる（全体が停止する）
def _convert_single_file(args: tuple) -> tuple[bool, Path, bool, str]:
    # 処理...（例外がそのまま伝播）
    return True, img_file, False, ''
```

---

## メモ化（キャッシング）

**頻繁に呼ばれる関数は `functools.lru_cache` でメモ化すること。**

### 基本的な使い方

```python
import functools

@functools.lru_cache(maxsize=1)
def _check_avif_support() -> bool:
    """Check if AVIF format is supported by Pillow.

    Returns:
        True if AVIF is supported, False otherwise
    """
    try:
        from PIL import Image, features
        return features.check('avif') or '.avif' in Image.registered_extensions()
    except Exception:
        return False
```

### maxsize の決定

| maxsize | 用途 | 例 |
|---------|------|-----|
| `1` | 結果が常に同じ | システム情報の取得（AVIF サポート確認） |
| `128`（デフォルト） | 複数の結果をキャッシュ | 設定値の読み込み、フォーマット変換 |
| `None` | 無制限キャッシュ | 静的データ、頻繁に参照される値 |

### メモ化のユースケース

#### 1. システム情報の取得

```python
@functools.lru_cache(maxsize=1)
def _check_avif_support() -> bool:
    """AVIF サポートは実行中に変わらないのでキャッシュ"""
    try:
        from PIL import Image, features
        return features.check('avif') or '.avif' in Image.registered_extensions()
    except Exception:
        return False
```

#### 2. 対応フォーマット一覧の生成

```python
@functools.lru_cache(maxsize=1)
def get_supported_formats() -> dict[str, str]:
    """対応フォーマット一覧は実行中に変わらない"""
    fmts = {
        '.jpg': 'JPEG',
        '.jpeg': 'JPEG',
        '.png': 'PNG',
        # ...
    }
    if _check_avif_support():
        fmts['.avif'] = 'AVIF'
    return fmts
```

#### 3. フォーマット正規化

```python
@functools.lru_cache(maxsize=128)
def _normalize_format(format_str: str) -> str:
    """同じフォーマット文字列が何度も来るのでキャッシュ"""
    format_upper = format_str.upper()
    if format_upper == 'JPG':
        return 'JPEG'
    elif format_upper == 'TIF':
        return 'TIFF'
    return format_upper
```

### メモ化を避けるべきケース

- **副作用がある関数**: ファイル書き込み、ログ出力など
- **引数が可変オブジェクト**: リスト、辞書など（ハッシュ化できない）
- **結果が時間依存**: 現在時刻、ランダム値など

---

## プログレスバー

**長時間処理には `tqdm` でプログレスバーを表示すること。**

### 基本的な使い方

```python
from tqdm import tqdm

def process_directory(...):
    # タスクリストを作成
    tasks = [...]

    # プログレスバーを初期化
    pbar = tqdm(total=len(tasks), desc='Converting images', unit='file')

    try:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_convert_single_file, task): task for task in tasks}

            for future in as_completed(futures):
                # 処理...
                pbar.update(1)  # 1つ完了するたびに更新

    finally:
        pbar.close()  # 必ずクリーンアップ
```

### プログレスバーのカスタマイズ

```python
pbar = tqdm(
    total=len(tasks),           # 総タスク数
    desc='Converting images',   # 説明文
    unit='file',                # 単位
    ncols=80,                   # 横幅（オプション）
    leave=True,                 # 完了後も表示を残す
)
```

### 手動更新パターン

```python
# 1つずつ更新
pbar.update(1)

# まとめて更新
pbar.update(n)

# 直接値を設定
pbar.n = current_value
pbar.refresh()
```

---

## 大量ファイル処理の最適化

### ディレクトリ作成のキャッシング

**同じディレクトリへの `mkdir` を繰り返さないこと。**

```python
# モジュールレベルでキャッシュセットを定義
_created_dirs: set[Path] = set()

def get_output_path(input_path: Path, output_format: str, output_dir: Path | None = None) -> Path:
    """Generate the output file path.

    Args:
        input_path: Path to the input image file
        output_format: Target format (e.g., 'jpeg', 'png')
        output_dir: Optional output directory

    Returns:
        Path object for the output file
    """
    if output_dir:
        # すでに作成済みのディレクトリは再度作成しない
        if output_dir not in _created_dirs:
            output_dir.mkdir(parents=True, exist_ok=True)
            _created_dirs.add(output_dir)

        stem = input_path.stem
        return output_dir / f'{stem}.{output_format.lower()}'
    else:
        # デフォルト出力ディレクトリ
        default_output_dir = input_path.parent / 'converted'
        if default_output_dir not in _created_dirs:
            default_output_dir.mkdir(parents=True, exist_ok=True)
            _created_dirs.add(default_output_dir)

        return default_output_dir / f'{input_path.stem}.{output_format.lower()}'
```

**効果**: 1000ファイル処理時、ディレクトリ作成のオーバーヘッドを数百回削減。

### ファイルリストの事前フィルタリング

**対応フォーマットでフィルタリングしてから処理すること。**

```python
def process_directory(...):
    # すべてのファイルを取得
    all_files = list(input_dir.rglob('*') if recursive else input_dir.glob('*'))

    # 対応フォーマットのみをフィルタリング
    image_files = []
    for f in all_files:
        if not f.is_file():
            continue

        # 出力ディレクトリ内のファイルはスキップ
        if actual_output_dir in f.parents:
            continue

        # 対応フォーマットのみ
        if is_supported_format(f):
            image_files.append(f)

    # この時点で image_files は処理対象のみ
```

**効果**: 不要なファイルを早期に除外することで、後続処理のオーバーヘッドを削減。

### リストの事前作成 vs ジェネレーター

```python
# ✅ 推奨：並列処理では事前にリスト化
all_files = list(input_dir.rglob('*'))  # リストに変換
# → ProcessPoolExecutor で複数ワーカーが同時にアクセス可能

# ❌ 非推奨：ジェネレーターは並列処理に不向き
all_files = input_dir.rglob('*')  # ジェネレーター
# → 状態を共有できずエラーになる
```

### バッチ処理の考慮

**タスクを適切なサイズにバッチ化することで、オーバーヘッドを削減できる。**

```python
# 小さなファイルが大量にある場合は、バッチ処理を検討
# （現在の実装では1ファイル = 1タスク）

# 将来的な改善案：
# - 10個の小さなファイルを1タスクにまとめる
# - タスク投入のオーバーヘッドを削減
```

---

## パフォーマンス測定

### 処理時間の記録

```python
import time

def process_directory(...):
    start_time = time.time()

    # 処理...

    elapsed_time = time.time() - start_time
    logger.info(f'Processed {success_count} files in {elapsed_time:.2f}s')
    logger.info(f'Average: {elapsed_time / len(image_files):.3f}s per file')
```

### プロファイリング

**パフォーマンスボトルネックを特定する場合は `cProfile` を使用。**

```bash
# 実行時間を測定
python -m cProfile -s cumtime src/image_converter.py input/ jpeg

# 出力をファイルに保存
python -m cProfile -o profile.stats src/image_converter.py input/ jpeg

# プロファイル結果を解析
python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumtime'); p.print_stats(20)"
```

---

## パフォーマンスチェックリスト

新機能を実装する際は、以下を確認すること：

### 並列処理
- [ ] `ProcessPoolExecutor` を使用している
- [ ] ワーカー数は `CPU × 1.5` をデフォルトにしている
- [ ] `KeyboardInterrupt` で即座にキャンセルできる
- [ ] ワーカー関数内で例外を適切にハンドリングしている

### メモ化
- [ ] 頻繁に呼ばれる関数に `@lru_cache` を適用している
- [ ] 適切な `maxsize` を設定している
- [ ] 副作用のない純粋関数にのみ適用している

### プログレスバー
- [ ] `tqdm` でプログレスバーを表示している
- [ ] `finally` ブロックで確実にクリーンアップしている
- [ ] わかりやすい説明文と単位を設定している

### 大量ファイル処理
- [ ] ディレクトリ作成をキャッシュしている
- [ ] ファイルリストを事前にフィルタリングしている
- [ ] ジェネレーターではなくリストを使用している（並列処理時）

### 測定と改善
- [ ] 処理時間をログに記録している
- [ ] ボトルネックを特定するためのプロファイリングを実施している

---

## まとめ

パフォーマンス最適化のポイント：

1. **並列処理**: `ProcessPoolExecutor` でマルチコア CPU を活用（ワーカー数 = CPU × 1.5）
2. **メモ化**: `@lru_cache` で頻繁に呼ばれる関数をキャッシュ
3. **プログレスバー**: `tqdm` でユーザーに進捗を表示
4. **ディレクトリキャッシング**: 同じディレクトリへの `mkdir` を削減
5. **事前フィルタリング**: 処理前に対象ファイルを絞り込む
6. **測定**: 処理時間を記録し、改善点を特定

これらの手法を組み合わせることで、大量ファイル処理時に 50-100 倍の高速化が可能。
