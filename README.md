# Image Converter

[![Test](https://github.com/YOUR_USERNAME/image-converter/workflows/Test/badge.svg)](https://github.com/YOUR_USERNAME/image-converter/actions)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A simple and efficient CLI tool to convert images between common formats.

## 🌟 Features

- **Multiple Format Support**: Convert between JPEG, PNG, BMP, GIF, TIFF, and WebP
- **Batch Processing**: Convert entire directories of images at once
- **Recursive Mode**: Process subdirectories automatically
- **Flexible Output**: Specify custom output directories
- **Safe Operations**: Confirmation prompts before overwriting existing files
- **Transparency Handling**: Automatically handles alpha channels when converting to formats that don't support transparency

## 📋 Supported Formats

| Input/Output Formats |
|---------------------|
| JPEG (.jpg, .jpeg)  |
| PNG (.png)          |
| BMP (.bmp)          |
| GIF (.gif)          |
| TIFF (.tiff, .tif)  |
| WebP (.webp)        |

## 🚀 Installation

### Prerequisites

- Python 3.9 or higher
- pip package manager

### Install from source

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/image-converter.git
cd image-converter

# Install dependencies
pip install -r requirements.txt

# (Optional) Install in development mode
pip install -e .
```

## 📖 Usage

### Basic Usage

Convert a single image:

```bash
python src/image_converter.py input.png jpeg
```

Convert with custom output directory:

```bash
python src/image_converter.py photo.jpg webp --output-dir converted/
```

### Directory Conversion

Convert all images in a directory:

```bash
python src/image_converter.py images/ png
```

Convert with output directory (preserves subdirectory structure):

```bash
python src/image_converter.py photos/ jpeg --output-dir converted/
```

Non-recursive mode (only process files in the root directory):

```bash
python src/image_converter.py images/ webp --no-recursive
```

### Advanced Options

Skip confirmation prompts:

```bash
python src/image_converter.py images/ jpeg --no-confirm
```

Combine multiple options:

```bash
python src/image_converter.py input/ webp -o output/ --no-confirm --no-recursive
```

### Command-Line Arguments

```
positional arguments:
  input                 Input image file or directory
  format                Output image format (jpeg, jpg, png, bmp, gif, tiff, tif, webp)

optional arguments:
  -h, --help            Show help message and exit
  -o, --output-dir DIR  Output directory (default: same as input)
  --no-confirm          Skip confirmation when overwriting existing files
  --no-recursive        Do not process subdirectories recursively
```

## 🧪 Testing

Run the test suite:

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v

# Run tests with coverage report
pytest tests/ -v --cov=src --cov-report=term-missing
```

## 🔧 Development

### Project Structure

```
image-converter/
├── src/
│   ├── __init__.py
│   └── image_converter.py    # Main CLI implementation
├── tests/
│   └── test_image_converter.py  # Unit tests
├── .github/
│   └── workflows/
│       └── test.yml          # GitHub Actions CI/CD
├── .gitignore
├── pyproject.toml            # Project configuration
├── requirements.txt          # Runtime dependencies
├── requirements-dev.txt      # Development dependencies
└── README.md
```

### Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 Examples

### Example 1: Convert WebP to PNG

```bash
python src/image_converter.py photo.webp png
# Output: Converted: photo.webp -> photo.png
```

### Example 2: Batch Convert Directory

```bash
python src/image_converter.py my_photos/ jpeg --output-dir jpg_versions/
# Output: 
# Found 15 image(s) to convert
# Converted: my_photos/img1.png -> jpg_versions/img1.jpeg
# Converted: my_photos/img2.webp -> jpg_versions/img2.jpeg
# ...
# Conversion complete: 15 succeeded, 0 failed
```

### Example 3: Convert with Transparency Handling

```bash
# PNG with transparency -> JPEG (white background added automatically)
python src/image_converter.py logo.png jpeg
```

## 🐛 Troubleshooting

**Issue**: "Error: Pillow is not installed"
- **Solution**: Run `pip install Pillow`

**Issue**: "Error: Unsupported file format"
- **Solution**: Check that your file has a supported extension (.jpg, .png, .bmp, .gif, .tiff, .webp)

**Issue**: Permission denied when overwriting files
- **Solution**: Use `--no-confirm` flag or ensure you have write permissions

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built with [Pillow (PIL Fork)](https://python-pillow.org/) - The Python Imaging Library
- Tested with [pytest](https://pytest.org/)

## 📞 Contact

For issues, questions, or suggestions, please open an issue on GitHub.

---

Made with ❤️ by [Your Name]
