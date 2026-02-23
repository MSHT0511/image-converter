# Image Converter

[![Test](https://github.com/YOUR_USERNAME/image-converter/workflows/Test/badge.svg)](https://github.com/YOUR_USERNAME/image-converter/actions)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

一般的な画像フォーマット間で変換を行うシンプルで効率的なCLIツール

## ⚠️ 免責事項

このプロジェクトは個人開発のツールです。メンテナンスやサポートは保証されません。使用は自己責任でお願いします。

## 🌟 機能

- **複数フォーマット対応**: JPEG、PNG、BMP、GIF、TIFF、WebP間での変換
- **バッチ処理**: ディレクトリ内の画像を一度に変換
- **再帰モード**: サブディレクトリを自動的に処理
- **柔軟な出力**: カスタム出力ディレクトリの指定
- **安全な操作**: 既存ファイルを上書きする前に確認プロンプトを表示
- **透過処理**: 透過をサポートしないフォーマットへの変換時にアルファチャンネルを自動処理

## 📋 サポートしているフォーマット

| 入力/出力フォーマット |
|---------------------|
| JPEG (.jpg, .jpeg)  |
| PNG (.png)          |
| BMP (.bmp)          |
| GIF (.gif)          |
| TIFF (.tiff, .tif)  |
| WebP (.webp)        |

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
  format                出力画像フォーマット (jpeg, jpg, png, bmp, gif, tiff, tif, webp)

オプション引数:
  -h, --help            ヘルプメッセージを表示して終了
  -o, --output-dir DIR  出力ディレクトリ (デフォルト: 入力と同じ)
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
# Converted: my_photos/img1.png -> jpg_versions/img1.jpeg
# Converted: my_photos/img2.webp -> jpg_versions/img2.jpeg
# ...
# Conversion complete: 15 succeeded, 0 failed
```

### 例3: 透過処理での変換

```bash
# 透過PNGからJPEGへ (自動的に白い背景が追加される)
python src/image_converter.py logo.png jpeg
```

## 🐛 トラブルシューティング

**問題**: "Error: Pillow is not installed"
- **解決策**: `pip install Pillow`を実行

**問題**: "Error: Unsupported file format"
- **解決策**: ファイルがサポートされている拡張子(.jpg, .png, .bmp, .gif, .tiff, .webp)を持っているか確認

**問題**: ファイル上書き時に権限が拒否される
- **解決策**: `--no-confirm`フラグを使用するか、書き込み権限があることを確認

## 📄 ライセンス

このプロジェクトはMITライセンスの下でライセンスされています。詳細はLICENSEファイルを参照してください。

## 🙏 謝辞

- [Pillow (PIL Fork)](https://python-pillow.org/) - The Python Imaging Library を使用して構築
- [pytest](https://pytest.org/)でテスト

## 📞 連絡先

問題、質問、提案がある場合は、GitHubでissueを開いてください。

---

Made with ❤️ by [Your Name]
