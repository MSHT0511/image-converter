# Image Converter

[![Test](https://github.com/MSHT0511/image-converter/workflows/Test/badge.svg)](https://github.com/MSHT0511/image-converter/actions)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

一般的な画像フォーマット間で変換を行うシンプルで効率的なCLIツール

## ⚠️ 免責事項

このプロジェクトは個人開発のツールです。メンテナンスやサポートは保証されません。使用は自己責任でお願いします。

## 🌟 機能

- **複数フォーマット対応**: JPEG、PNG、BMP、GIF、TIFF、WebP、ICO、AVIF間での変換
- **バッチ処理**: ディレクトリ内の画像を一度に変換
- **並列処理**: マルチコアCPUを活用した高速変換（3-4倍の高速化）
- **プログレスバー**: バッチ変換の進捗状況をリアルタイム表示
- **再帰モード**: サブディレクトリを自動的に処理
- **柔軟な出力**: カスタム出力ディレクトリの指定
- **安全な操作**: 既存ファイルを上書きする前に確認プロンプトを表示
- **透過処理**: 透過をサポートしないフォーマットへの変換時にアルファチャンネルを自動処理

## 📋 サポートしているフォーマット

| 入力/出力フォーマット | 透過サポート | 備考 |
|---------------------|-------------|------|
| JPEG (.jpg, .jpeg)  | ❌ | 標準的な写真形式 |
| PNG (.png)          | ✅ | ロスレス圧縮 |
| BMP (.bmp)          | ❌ | Windows標準形式 |
| GIF (.gif)          | ✅ | アニメーション対応 |
| TIFF (.tiff, .tif)  | ✅ | 高品質画像 |
| WebP (.webp)        | ✅ | 次世代画像形式 |
| ICO (.ico)          | ✅ | アイコン形式 |
| AVIF (.avif)        | ✅ | 最新の高効率形式 |

## 🚀 インストール

### 前提条件

- Python 3.9以上
- pipパッケージマネージャー

### ソースからインストール

```bash
# リポジトリをクローン
git clone https://github.com/YOUR_USERNAME/image-converter.git
cd image-converter

# 依存関係をインストール
pip install -r requirements.txt

# (オプション) 開発モードでインストール
pip install -e .
```

### AVIFサポート（オプション）

AVIF形式のサポートには追加の依存関係が必要です。AVIFを使用しない場合でも、他のすべてのフォーマット（ICOを含む）は正常に動作します。

**Windows:**
```bash
pip install pillow-avif-plugin
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install libavif-dev
pip install pillow-avif-plugin
```

**macOS:**
```bash
brew install libavif
pip install pillow-avif-plugin
```

AVIFサポートが利用できない場合、ツールは自動的にAVIF形式を無効化し、他のすべての形式で正常に動作します。

## 📖 使い方

### 基本的な使い方

単一の画像を変換:

```bash
python src/image_converter.py input.png jpeg
```

カスタム出力ディレクトリを指定して変換:

```bash
python src/image_converter.py photo.jpg webp --output-dir converted/
```

### ディレクトリの変換

ディレクトリ内のすべての画像を変換:

```bash
python src/image_converter.py images/ png
```

出力ディレクトリを指定して変換（サブディレクトリ構造を保持）:

```bash
python src/image_converter.py photos/ jpeg --output-dir converted/
```

非再帰モード（ルートディレクトリのファイルのみ処理）:

```bash
python src/image_converter.py images/ webp --no-recursive
```

### 高度なオプション

#### 並列処理

並列処理で高速変換（CPUコア数分のワーカーを自動使用）:

```bash
python src/image_converter.py images/ webp --parallel
```

ワーカー数を指定:

```bash
python src/image_converter.py photos/ jpeg --parallel --workers 4
```

**並列処理のガイドライン:**
- **ワーカー未指定**: システムのCPUコア数分のワーカーを自動使用（最大効率）
- **小規模（< 20ファイル）**: `--workers 2-4` 推奨（プロセス起動オーバーヘッド削減）
- **中〜大規模（≥ 20ファイル）**: `--parallel` のみで自動最適化
- **メモリ制約あり**: `--workers` で制限（例: `--workers 4`）

> ⚠️ 並列処理は大量画像で特に効果的ですが、メモリ使用量が増加します。ワーカー数 × 画像サイズ分のメモリが必要です。

#### その他のオプション

確認プロンプトをスキップ:

```bash
python src/image_converter.py images/ jpeg --no-confirm
```

複数のオプションを組み合わせ:

```bash
python src/image_converter.py input/ webp -o output/ --no-confirm --no-recursive
```

### コマンドライン引数

```
位置引数:
  input                 入力画像ファイルまたはディレクトリ
  format                出力画像フォーマット (jpeg, jpg, png, bmp, gif, tiff, tif, webp, ico, avif)

オプション引数:
  -h, --help            ヘルプメッセージを表示して終了
  -o, --output-dir DIR  出力ディレクトリ (デフォルト: 入力と同じ)
  -p, --parallel        並列処理を有効化（バッチ変換のみ）
  -w, --workers N       並列ワーカー数（デフォルト: CPUコア数、--parallelと併用）
  --no-confirm          既存ファイルを上書きする際の確認をスキップ
  --no-recursive        サブディレクトリを再帰的に処理しない
```

## 🧪 テスト

テストスイートを実行:

```bash
# 開発依存関係をインストール
pip install -r requirements-dev.txt

# テストを実行
pytest tests/ -v

# カバレッジレポート付きでテストを実行
pytest tests/ -v --cov=src --cov-report=term-missing
```

## 🔧 開発

### プロジェクト構造

```
image-converter/
├── src/
│   ├── __init__.py
│   └── image_converter.py    # メインのCLI実装
├── tests/
│   └── test_image_converter.py  # ユニットテスト
├── .github/
│   └── workflows/
│       └── test.yml          # GitHub Actions CI/CD
├── .gitignore
├── pyproject.toml            # プロジェクト設定
├── requirements.txt          # ランタイム依存関係
├── requirements-dev.txt      # 開発依存関係
└── README.md
```

### 貢献

1. リポジトリをフォーク
2. フィーチャーブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add amazing feature'`)
4. ブランチにプッシュ (`git push origin feature/amazing-feature`)
5. プルリクエストを作成

## 📝 使用例

### 例1: WebPからPNGへ変換

```bash
python src/image_converter.py photo.webp png
# 出力: Converted: photo.webp -> photo.png
```

### 例2: ディレクトリのバッチ変換

```bash
python src/image_converter.py my_photos/ jpeg --output-dir jpg_versions/
# 出力: 
# Found 15 image(s) to convert
# Converting images: 100%|████████████████| 15/15 [00:02<00:00, 7.32file/s]
# 
# Conversion complete: 15 succeeded, 0 failed
```

並列処理での高速変換:

```bash
python src/image_converter.py my_photos/ jpeg --parallel --output-dir jpg_versions/
# 出力:
# Found 15 image(s) to convert
# Converting images: 100%|████████████████| 15/15 [00:00<00:00, 23.45file/s]
# 
# Conversion complete: 15 succeeded, 0 failed
```

### 例3: 透過処理での変換

```bash
# 透過PNGからJPEGへ (自動的に白い背景が追加される)
python src/image_converter.py logo.png jpeg
```

### 例4: アイコン（ICO）形式への変換

```bash
# PNGからICOへ（透過性を保持）
python src/image_converter.py logo.png ico
```

### 例5: 次世代フォーマット（AVIF）への変換

```bash
# JPEGからAVIFへ（高圧縮率）
python src/image_converter.py photo.jpg avif
# 出力: Converted: photo.jpg -> converted/photo.avif
```

## 🐛 トラブルシューティング

**問題**: "Error: Pillow is not installed"
- **解決策**: `pip install Pillow`を実行

**問題**: "Error: Unsupported file format"
- **解決策**: ファイルがサポートされている拡張子(.jpg, .png, .bmp, .gif, .tiff, .webp, .ico, .avif)を持っているか確認

**問題**: AVIF形式が選択肢に表示されない
- **解決策**: `pip install pillow-avif-plugin`を実行してAVIFサポートを有効化。システムによっては`libavif`のインストールが必要な場合があります。

**問題**: ファイル上書き時に権限が拒否される
- **解決策**: `--no-confirm`フラグを使用するか、書き込み権限があることを確認

## 📄 ライセンス

このプロジェクトはMITライセンスの下でライセンスされています。詳細はLICENSEファイルを参照してください。

## 🙏 謝辞

- [Pillow (PIL Fork)](https://python-pillow.org/) - The Python Imaging Library を使用して構築
- [pillow-avif-plugin](https://github.com/fdintino/pillow-avif-plugin) - AVIFフォーマットサポート
- [tqdm](https://github.com/tqdm/tqdm) - プログレスバー表示
- [pytest](https://pytest.org/) - テストフレームワーク

## 📞 連絡先

問題、質問、提案がある場合は、GitHubでissueを開いてください。

---

Made with ❤️ by MSHT0511 
