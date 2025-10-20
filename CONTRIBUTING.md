# Contributing to geoNamesFromPdf

Thank you for your interest in contributing to geoNamesFromPdf! This document provides guidelines and instructions for contributing.

## 🌟 Ways to Contribute

- **Report bugs** - Found a bug? Open an issue
- **Suggest features** - Have an idea? We'd love to hear it
- **Add language support** - Help us support more languages
- **Improve documentation** - Better docs help everyone
- **Submit code** - Fix bugs or add features via pull requests

## 🐛 Reporting Bugs

When reporting bugs, please include:

- **Python version** - Output of `python --version`
- **Operating system** - macOS, Windows, Linux (which distro?)
- **Steps to reproduce** - Clear, numbered steps
- **Expected behavior** - What should happen
- **Actual behavior** - What actually happens
- **Error messages** - Full traceback if applicable
- **Sample PDF** - If possible (without sensitive data)

## 💡 Suggesting Features

When suggesting features:

- Check if it's already been suggested
- Explain the use case clearly
- Describe the proposed solution
- Consider alternatives you've thought of

## 🌍 Adding Language Support

To add support for a new language:

1. **Check spaCy models** - Visit https://spacy.io/models
2. **Test the model** - Ensure it has good NER support
3. **Update the code**:
   ```python
   # In geoNamesFromPdf.py, add to LANGUAGE_MODELS dict:
   LANGUAGE_MODELS = {
       # ...existing languages...
       'xx': 'xx_core_news_lg',  # Your language
   }
   ```
4. **Test thoroughly** - Use sample documents
5. **Update README** - Add language to the supported languages table
6. **Submit PR** - Include test results

## 🔧 Development Setup

1. **Fork the repository**
   ```bash
   # Click 'Fork' on GitHub, then:
   git clone https://github.com/YOUR_USERNAME/geoNamesFromPdf.git
   cd geoNamesFromPdf
   ```

2. **Create virtual environment**
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate  # macOS/Linux
   # or: venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install PyMuPDF spacy langdetect
   python -m spacy download en_core_web_lg
   python -m spacy download it_core_news_lg
   ```

4. **Create a branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

## 📝 Code Style

- Follow [PEP 8](https://pep8.org/) style guidelines
- Use descriptive variable names
- Add comments for complex logic
- Keep functions focused and small
- Use docstrings for functions

Example:
```python
def extract_toponyms(text, nlp_model):
    """Extract place names using spaCy NER.
    
    Args:
        text (str): The text to analyze
        nlp_model: Loaded spaCy language model
        
    Returns:
        list: Sorted list of unique toponyms
    """
    # Implementation...
```

## 🧪 Testing

Before submitting:

1. **Test basic functionality**
   ```bash
   python geoNamesFromPdf.py test_document.pdf
   ```

2. **Test with multiple languages**
   ```bash
   python geoNamesFromPdf.py -l it italian_doc.pdf
   python geoNamesFromPdf.py -l en english_doc.pdf
   ```

3. **Test edge cases**
   - Empty PDFs
   - PDFs with no text
   - Multi-language documents
   - Very large PDFs

4. **Check for errors**
   ```bash
   python geoNamesFromPdf.py --list-languages
   python geoNamesFromPdf.py --install-language xx
   ```

## 📤 Submitting Pull Requests

1. **Update your fork**
   ```bash
   git remote add upstream https://github.com/ORIGINAL_OWNER/geoNamesFromPdf.git
   git fetch upstream
   git merge upstream/main
   ```

2. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: Add support for Spanish language"
   ```
   
   Use conventional commit messages:
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation changes
   - `refactor:` - Code refactoring
   - `test:` - Adding tests
   - `chore:` - Maintenance tasks

3. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

4. **Create Pull Request**
   - Go to GitHub and click "New Pull Request"
   - Provide clear title and description
   - Reference related issues if applicable
   - Wait for review and address feedback

## ✅ Pull Request Checklist

- [ ] Code follows project style guidelines
- [ ] Changes have been tested
- [ ] Documentation has been updated
- [ ] Commit messages are clear
- [ ] No merge conflicts
- [ ] All existing tests still pass

## 📋 Code of Conduct

- Be respectful and considerate
- Welcome newcomers and help them learn
- Focus on constructive feedback
- Assume good intentions
- Be patient with response times

## 🎯 Priority Areas

We especially welcome contributions in these areas:

1. **Language support** - Adding more spaCy language models
2. **Performance** - Optimizing for large PDFs
3. **Error handling** - Better error messages and recovery
4. **Testing** - Adding automated tests
5. **Documentation** - Examples, tutorials, use cases

## 💬 Questions?

- Open a [Discussion](https://github.com/yourusername/geoNamesFromPdf/discussions)
- Ask in the [Issues](https://github.com/yourusername/geoNamesFromPdf/issues) section
- Be specific about what you need help with

## 🙏 Thank You!

Every contribution helps make this tool better for everyone. Whether it's code, documentation, bug reports, or feature suggestions - we appreciate your help!

---

**Remember:** Your first contribution doesn't have to be perfect. We're here to help and learn together!
