# Image Converter - GitHub Copilot 共通ルール

## プロジェクト概要

**Image Converter** は、複数の画像フォーマット間で変換を行う CLI ツールです。

### 主な特徴
- **対応フォーマット**: JPEG, PNG, BMP, GIF, TIFF, WebP, ICO, AVIF（8形式）
- **並列処理**: マルチコア CPU を活用した高速バッチ処理
- **セキュリティ**: ファイルサイズ制限、パス検証、入力バリデーション
- **UX**: プログレスバー表示、対話的な上書き確認、詳細なエラーログ
- **Python 3.10+**: 最新の型ヒント構文を活用

---

## コーディング規約

### Python バージョンと型ヒント

**Python 3.10 以上の機能を積極的に活用すること。**

```python
# ✅ 推奨：Python 3.10+ の型ヒント
def get_supported_formats() -> dict[str, str]:
    pass

def validate_input_path(path: Path, max_size: int = 100_000_000) -> Path:
    pass

def _resolve_output_dir(img_file: Path, input_dir: Path, output_dir: Path | None, recursive: bool) -> Path:
    pass

# ❌ 非推奨：古い型ヒント（typing.Dict, typing.Optional）
from typing import Dict, Optional

def get_supported_formats() -> Dict[str, str]:  # NG
    pass

def _resolve_output_dir(output_dir: Optional[Path]) -> Path:  # NG
    pass
```

**すべての関数に型ヒントを必須とする（引数、戻り値）。**

### コードスタイル（Ruff 準拠）

**Ruff の設定に従うこと**（[pyproject.toml](../pyproject.toml) 参照）。

- **行長**: 120文字以内
- **クォート**: シングルクォート `'text'` を使用
- **インデント**: スペース
- **インポート順序**: isort 互換（標準ライブラリ → サードパーティ → ローカル）

```python
# ✅ 推奨
message = 'Converting image'
path = Path('converted/output.png')

# ❌ 非推奨
message = "Converting image"  # ダブルクォートは使わない
```

**有効なルール**: E（pycodestyle errors）、W（warnings）、F（Pyflakes）、I（isort）、B（bugbear）、C4（comprehensions）、UP（pyupgrade）

### ドックストリング

**Google スタイルのドックストリングを使用すること。**

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
    # 実装...
```

**必須項目**:
- **Args**: 各引数の説明（型は型ヒントで表現されているため省略可）
- **Returns**: 戻り値の説明
- **Raises**: 発生する可能性のある例外

### 命名規則

| 対象 | 規則 | 例 |
|------|------|-----|
| 関数・変数 | スネークケース | `convert_image`, `input_path`, `max_workers` |
| プライベート関数 | アンダースコアプレフィックス | `_check_avif_support`, `_normalize_format` |
| 定数 | 大文字スネークケース | `PILLOW_AVAILABLE`, `MAX_FILE_SIZE` |
| クラス | パスカルケース | `ImageConverterError`, `SecurityError` |

**説明的で意味のある名前を使用すること。**

```python
# ✅ 推奨
def _resolve_output_dir(img_file: Path, input_dir: Path, output_dir: Path | None, recursive: bool) -> Path:
    pass

# ❌ 非推奨
def _resolve(f: Path, i: Path, o: Path | None, r: bool) -> Path:  # 短すぎて意味不明
    pass
```

---

## エラーハンドリング

エラーハンドリングの詳細は [guides/error-handling.md](guides/error-handling.md) を参照してください。

**要点**:
- 関数は `bool` または `tuple` で成功/失敗を返す（例外を返さない設計）
- カスタム例外階層を使用（`ImageConverterError`, `SecurityError`, `ConversionError`）
- 詳細なエラーログを記録、ユーザーには簡潔なメッセージを表示

---

## セキュリティ

セキュリティ要件の詳細は [guides/security.md](guides/security.md) を参照してください。

**要点**:
- ファイルサイズ制限（デフォルト100MB）
- パス検証（シンボリックリンク解決、絶対パス化）
- 出力ディレクトリの除外（無限ループ防止）
- 入力バリデーション（サポート形式のみ受け付け）

---

## パフォーマンス（重点項目）

パフォーマンス最適化の詳細は [guides/performance.md](guides/performance.md) を参照してください。

**要点**:
- **並列処理**: `ProcessPoolExecutor` でマルチコア CPU 活用（ワーカー数 = CPU × 1.5）
- **メモ化**: `@functools.lru_cache` で頻繁に呼ばれる関数をキャッシュ
- **プログレスバー**: `tqdm` で進捗表示
- **大量ファイル処理**: ディレクトリ作成キャッシング、事前フィルタリング

---

## ファイル操作

### pathlib.Path の一貫使用

**ファイルパスは `pathlib.Path` を一貫して使用すること。文字列パスは禁止。**

```python
from pathlib import Path

# ✅ 推奨
def convert_image(input_path: Path, output_format: str, output_dir: Path | None = None) -> bool:
    if not input_path.exists():
        return False

    output_path = get_output_path(input_path, output_format, output_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)

# ❌ 非推奨
def convert_image(input_path: str, output_format: str, output_dir: str = None) -> bool:  # NG
    if not os.path.exists(input_path):  # NG
        return False
```

**文字列パスを受け取った場合は即座に Path に変換**:

```python
def main():
    args = parser.parse_args()

    # CLI 引数（文字列）を Path に変換
    input_path = Path(args.input)
    output_dir = Path(args.output_dir) if args.output_dir else None
```

### ディレクトリ作成

**常に `parents=True, exist_ok=True` を指定すること。**

```python
# ✅ 推奨
output_dir.mkdir(parents=True, exist_ok=True)

# ❌ 非推奨
if not output_dir.exists():  # 冗長
    output_dir.mkdir()
```

### ファイル存在確認

**Path のメソッドを使用すること。**

```python
# ✅ 推奨
if path.exists() and path.is_file():
    pass

if path.is_dir():
    pass

# ❌ 非推奨
if os.path.exists(str(path)) and os.path.isfile(str(path)):  # NG
    pass
```

---

## テスト規約

テストの詳細は [guides/testing.md](guides/testing.md) を参照してください。

**要点**:
- **pytest** でテスト実行、フィクスチャー活用でコードの重複削減
- **5種類のテスト**: 正常系、異常系、境界値、セキュリティ、並列処理
- **モッキング**: `unittest.mock` で外部依存をモック
- **カバレッジ 90% 以上**: CI で自動チェック

---

## 新機能実装チェックリスト

新機能を実装する際は、以下のチェックリストに従うこと。

### 実装前
- [ ] 既存機能との互換性を確認
- [ ] セキュリティリスクを検討（[guides/security.md](guides/security.md) 参照）
- [ ] パフォーマンス影響を考慮（[guides/performance.md](guides/performance.md) 参照）

### 実装中
- [ ] 型ヒントを追加（引数、戻り値）
- [ ] Google スタイルのドックストリングを記述
- [ ] エラーハンドリングを実装（[guides/error-handling.md](guides/error-handling.md) 参照）
- [ ] ロギングを追加（必要に応じて）
- [ ] セキュリティ考慮（入力検証、リソース制限）
- [ ] パフォーマンス最適化（並列処理、キャッシング）

### 実装後
- [ ] テストを追加（[guides/testing.md](guides/testing.md) 参照）
- [ ] Ruff チェックをパス（`ruff check src/ tests/`, `ruff format --check src/ tests/`）
- [ ] Bandit スキャンをパス（`bandit -r src/ -ll`）
- [ ] カバレッジ 90% 以上を維持
- [ ] README の使用例を更新（必要に応じて）

---

## CI/CD

### 自動チェック

すべての変更は以下の CI ワークフローをパスする必要がある。

#### 1. Test Workflow ([.github/workflows/test.yml](workflows/test.yml))
- **トリガー**: push（master, develop）、PR（master）
- **マトリックスビルド**:
  - Windows: Python 3.10, 3.11, 3.12, 3.13
  - Ubuntu: Python 3.13
  - macOS: Python 3.13
- **処理**:
  - 依存関係インストール（pip cache 利用）
  - pytest 実行 + カバレッジ計測
  - Ubuntu 3.13 で PR にカバレッジコメント投稿（90% 以上グリーン）

#### 2. Lint Workflow ([.github/workflows/lint.yml](workflows/lint.yml))
- **トリガー**: push/PR
- **処理**:
  - Ruff リンター（`ruff check src/ tests/`）
  - Ruff フォーマッター検証（`ruff format --check src/ tests/`）
- **OS**: Ubuntu latest, Python 3.13

#### 3. Security Workflow ([.github/workflows/security.yml](workflows/security.yml))
- **トリガー**: push/PR
- **2つのジョブ**:
  - **pip-audit**: 依存関係の脆弱性チェック
  - **bandit**: コードセキュリティスキャン（`bandit -r src/ -ll`）

### PR ルール

- すべてのワークフローがグリーンであること
- カバレッジ 90% 以上
- コードレビュー後にマージ

---

## ドキュメント更新

### README.md

新機能を追加した場合は、以下を更新すること。

- **機能一覧**: 新機能の説明を追加
- **使用例**: 新機能の使い方を示すコマンド例を追加
- **トラブルシューティング**: 新しいエラーケースがあれば追加

### コミットメッセージ

**日本語でも英語でも OK。**

フォーマット: `[種別] 簡潔な説明`

種別例:
- `[機能追加]`: 新機能の追加
- `[修正]`: バグ修正
- `[テスト]`: テストの追加・修正
- `[ドキュメント]`: ドキュメントの更新
- `[リファクタリング]`: コードの整理・改善
- `[パフォーマンス]`: パフォーマンス改善

例:
```
[機能追加] AVIF形式のサポートを追加
[修正] 並列処理でのKeyboardInterrupt処理を改善
[テスト] セキュリティバリデーションのテストケースを追加
```

---

## 参考リンク

- **Pillow ドキュメント**: https://pillow.readthedocs.io/
- **pytest ドキュメント**: https://docs.pytest.org/
- **Ruff ドキュメント**: https://docs.astral.sh/ruff/
- **Python 3.10 新機能**: https://docs.python.org/3/whatsnew/3.10.html

---

## まとめ

このプロジェクトでは、以下を重視してください。

1. **型安全性**: Python 3.10+ の型ヒントを活用
2. **セキュリティ**: 入力検証、リソース制限を徹底（→ [guides/security.md](guides/security.md)）
3. **パフォーマンス**: 並列処理、キャッシングで最適化（→ [guides/performance.md](guides/performance.md)）
4. **エラーハンドリング**: 例外を返さない設計、詳細なログ（→ [guides/error-handling.md](guides/error-handling.md)）
5. **テスト**: 90% 以上のカバレッジを維持（→ [guides/testing.md](guides/testing.md)）
6. **ユーザー体験**: プログレスバー、わかりやすいエラーメッセージ

新しい機能を追加する際は、既存のコーディングパターンを参考にし、このドキュメントのチェックリストに従ってください。
