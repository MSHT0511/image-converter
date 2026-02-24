# Image Converter - 未実装機能リスト

最初の機能分析で提案された機能のうち、まだ実装されていないものをまとめました。

---

## ✅ 実装済み機能（v1.1）

- [x] **並列処理** (`--parallel`, `--workers`)
- [x] **プログレスバー** (tqdm)
- [x] **出力制御** (verbose パラメータでバッチ処理時のログを抑制)

---

## 🔴 優先度：高（推奨実装）

### 1. 品質・圧縮制御 ⭐⭐⭐⭐⭐

**概要**: JPEG/PNG/WebP/AVIFの品質・圧縮レベルを指定可能にする

**CLI例**:
```bash
# JPEG品質指定
python src/image_converter.py input.png jpeg --quality 90

# PNG圧縮レベル
python src/image_converter.py input.jpg png --compression 9

# WebPロスレス圧縮
python src/image_converter.py input.png webp --lossless
```

**実装難易度**: 低
**作業時間**: 1-2時間
**主な変更箇所**:
- CLI引数追加: `--quality`, `--compression`, `--lossless`
- `convert_image` 関数: `save_kwargs` に品質パラメータを追加

**実装メモ**:
```python
# 例: JPEG
if output_format == 'JPEG':
    save_kwargs['quality'] = quality  # 1-100
    save_kwargs['optimize'] = True
    
# PNG
elif output_format == 'PNG':
    save_kwargs['compress_level'] = compression  # 0-9
    
# WebP
elif output_format == 'WEBP':
    save_kwargs['quality'] = quality if not lossless else 100
    save_kwargs['lossless'] = lossless
```

---

### 2. 画像リサイズ・スケーリング ⭐⭐⭐⭐⭐

**概要**: 画像サイズを変更する機能

**CLI例**:
```bash
# 固定サイズにリサイズ
python src/image_converter.py input.png jpeg --resize 1920x1080

# パーセンテージでスケール
python src/image_converter.py input.jpg webp --scale 50
```

**実装難易度**: 低
**作業時間**: 2-3時間
**主な変更箇所**:
- CLI引数追加: `--resize WxH`, `--scale PERCENT`
- `convert_image` 関数内で `img.resize()` を呼び出し

**実装メモ**:
```python
from PIL import Image

# リサイズ処理
if resize:
    w, h = map(int, resize.split('x'))
    img = img.resize((w, h), Image.Resampling.LANCZOS)
elif scale:
    new_size = tuple(int(dim * scale / 100) for dim in img.size)
    img = img.resize(new_size, Image.Resampling.LANCZOS)
```

**追加検討事項**:
- アスペクト比を保持するオプション (`--keep-aspect`)
- 複数のリサンプリングアルゴリズム選択

---

### 3. メタデータ保持 ⭐⭐⭐⭐

**概要**: EXIF情報などのメタデータを保存/削除するオプション

**CLI例**:
```bash
# メタデータを保持
python src/image_converter.py photo.jpg webp --preserve-metadata

# メタデータを削除
python src/image_converter.py photo.jpg png --strip-metadata
```

**実装難易度**: 中
**作業時間**: 3-4時間
**依存関係**: `piexif` (optional)
**主な変更箇所**:
- CLI引数追加: `--preserve-metadata`, `--strip-metadata`
- メタデータコピーロジックの実装

**実装メモ**:
```python
# 基本的なメタデータ保持
if preserve_metadata:
    exif = img.info.get('exif')
    if exif:
        save_kwargs['exif'] = exif

# より高度なEXIF処理（piexif使用）
import piexif
exif_dict = piexif.load(input_path)
exif_bytes = piexif.dump(exif_dict)
save_kwargs['exif'] = exif_bytes
```

**注意事項**:
- フォーマット間のメタデータ互換性問題
- JPEG EXIF ≠ PNG metadata

---

### 4. エラーログ出力 ⭐⭐⭐⭐

**概要**: エラーをファイルに記録

**CLI例**:
```bash
python src/image_converter.py images/ jpeg --log-file conversion.log
```

**実装難易度**: 低
**作業時間**: 1-2時間
**主な変更箇所**:
- CLI引数追加: `--log-file PATH`
- `logging` モジュールの導入

**実装メモ**:
```python
import logging

if log_file:
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
logging.info(f"Converted: {input_path} -> {output_path}")
logging.error(f"Failed to convert: {input_path}")
```

---

## 🟡 優先度：中（便利な機能）

### 5. ドライランモード ⭐⭐⭐

**概要**: 実際に変換せずに動作をプレビュー

**CLI例**:
```bash
python src/image_converter.py images/ jpeg --dry-run
```

**実装難易度**: 低
**作業時間**: 1時間
**実装**: `convert_image` と `process_file` 関数に dry_run フラグ追加

---

### 6. 既存ファイルスキップ ⭐⭐⭐

**概要**: 既存ファイルがあれば上書きせずスキップ

**CLI例**:
```bash
python src/image_converter.py images/ webp --skip-existing
```

**実装難易度**: 低
**作業時間**: 30分
**実装**: `process_file` 関数で出力パスの存在チェック

---

### 7. 詳細/静粛モード ⭐⭐⭐

**概要**: 出力の詳細レベルを制御

**CLI例**:
```bash
# 詳細出力
python src/image_converter.py images/ jpeg --verbose

# 静粛モード（エラーのみ）
python src/image_converter.py images/ jpeg --quiet
```

**実装難易度**: 低
**作業時間**: 1時間
**実装**: 既存の verbose パラメータを拡張

---

### 8. 回転・反転 ⭐⭐⭐

**概要**: 画像を回転または反転

**CLI例**:
```bash
python src/image_converter.py input.jpg png --rotate 90
python src/image_converter.py input.png jpeg --flip horizontal
```

**実装難易度**: 低
**作業時間**: 1-2時間
**実装**: `img.rotate()`, `img.transpose()` 使用

---

### 9. グレースケール変換 ⭐⭐⭐

**概要**: 画像を白黒に変換

**CLI例**:
```bash
python src/image_converter.py input.png jpeg --grayscale
```

**実装難易度**: 低
**作業時間**: 30分
**実装**: `img.convert('L')` 使用

---

### 10. HEIC/HEIF対応 ⭐⭐⭐

**概要**: iOS写真形式のサポート

**CLI例**:
```bash
python src/image_converter.py photo.heic jpeg
```

**実装難易度**: 高（システム依存）
**作業時間**: 3-4時間
**依存関係**: `pillow-heif`, `libheif`
**実装**: AVIFと同様にオプショナルプラグインとして追加

---

## 🟢 優先度：低（将来的な拡張）

### 11. progressive JPEG
**CLI**: `--progressive`
**実装難易度**: 低

### 12. 設定ファイル対応
**ファイル**: `.imageconverterrc`, `config.toml`
**実装難易度**: 中

### 13. 統計レポート
**CLI**: `--report stats.json`
**実装難易度**: 中

### 14. RAW形式対応
**依存**: `rawpy`
**実装難易度**: 非常に高

### 15. PDF出力
**依存**: `img2pdf`
**実装難易度**: 中

### 16. 色調整（明度・コントラスト）
**API**: `PIL.ImageEnhance`
**実装難易度**: 中

### 17. ウォーターマーク
**CLI**: `--watermark logo.png`
**実装難易度**: 中

### 18. ディレクトリ監視モード
**依存**: `watchdog`
**実装難易度**: 高

---

## 📊 実装優先順位の推奨

### Phase 1 (次回実装推奨)
1. **品質・圧縮制御** - 最も需要が高い
2. **画像リサイズ** - 基本機能として必須
3. **エラーログ出力** - デバッグに有用

**推定作業時間**: 4-7時間

### Phase 2
4. **メタデータ保持** - プロフェッショナル用途
5. **ドライランモード** - 安全性向上
6. **詳細/静粛モード** - UX改善

**推定作業時間**: 5-6時間

### Phase 3
7. **回転・反転** - 便利機能
8. **グレースケール** - 簡単に実装可能
9. **既存ファイルスキップ** - ワークフロー改善

**推定作業時間**: 2-3時間

---

## 🔧 技術的考慮事項

### 下位互換性
- すべての新機能はオプショナル
- デフォルト動作は既存のまま維持
- 既存のテストが通ることを確認

### テスト追加
各機能に対して以下のテストが必要:
- 機能有効時の動作確認
- デフォルト動作の確認
- エッジケース（エラー処理）

### ドキュメント更新
- README.md の使用例追加
- `--help` 出力の更新
- 使用例セクションの拡充

---

## 📝 実装時の注意点

1. **段階的な実装**: 一度に多くの機能を追加せず、1-3機能ずつ実装
2. **テスト駆動**: 機能追加前にテストケースを作成
3. **パフォーマンス**: 特にリサイズなど処理負荷が高い機能は並列処理と組み合わせて最適化
4. **エラーハンドリング**: 新機能で発生しうる例外を適切に処理
5. **ドキュメント**: コード変更と同時にREADMEも更新

---

## 🎯 次のステップ

Phase 1の実装を開始する場合:

1. 新しいブランチ作成: `feature/quality-controls`
2. 品質・圧縮制御を実装
3. テスト追加
4. README更新
5. PR作成

または、他の機能から優先的に実装する場合は、それに応じたブランチを作成してください。
