# Contributing to PC Express MCP Server

First off, thank you for considering contributing! 🎉

This project is built by the community, for the community. All contributions are welcome!

## Code of Conduct

Be respectful, inclusive, and constructive. We're all here to make grocery shopping better!

## How Can I Contribute?

### 🐛 Reporting Bugs

Found a bug? Help us fix it!

1. **Check existing issues** - Someone might have already reported it
2. **Create a new issue** with:
   - Clear, descriptive title
   - Steps to reproduce
   - Expected vs actual behavior
   - Your environment (OS, Python version, banner)
   - Relevant logs (remove sensitive data!)

### 💡 Suggesting Features

Have an idea? We'd love to hear it!

1. **Check existing issues** - Avoid duplicates
2. **Create a feature request** with:
   - Clear description of the feature
   - Why it would be useful
   - How it might work
   - Any implementation ideas

### 🔧 Code Contributions

Ready to code? Awesome!

#### Development Setup

1. **Fork the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/pcexpress-mcp-server.git
   cd pcexpress-mcp-server
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up credentials**
   ```bash
   cp .env.example .env
   # Edit .env with your test credentials
   ```

5. **Run tests**
   ```bash
   python test_api.py
   ```

#### Making Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clean, readable code
   - Follow existing code style
   - Add comments where needed
   - Update documentation

3. **Test your changes**
   ```bash
   python test_api.py
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "Add feature: brief description"
   ```

   Commit message format:
   - `Add feature: ...` - New functionality
   - `Fix bug: ...` - Bug fixes
   - `Update docs: ...` - Documentation
   - `Refactor: ...` - Code improvements
   - `Test: ...` - Test additions/changes

5. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Open a Pull Request**
   - Clear title and description
   - Reference related issues
   - Explain what you changed and why

#### Code Style

- **Python**: Follow PEP 8
- **Line length**: Max 100 characters
- **Docstrings**: Google-style
- **Type hints**: Use where appropriate
- **Error handling**: Be explicit

Example:
```python
def get_order_details(self, order_id: str) -> dict:
    """
    Get details for a specific order including all items

    Args:
        order_id: The order ID

    Returns:
        dict: Order details including items, prices, etc.

    Raises:
        requests.HTTPError: If API request fails
    """
    url = f"{self.BASE_URL}/orders/{order_id}"
    response = requests.get(url, headers=self._get_headers())
    response.raise_for_status()
    return response.json()
```

### 📝 Documentation

Documentation improvements are always welcome!

- Fix typos and grammar
- Clarify confusing sections
- Add examples
- Update outdated information
- Translate to other languages

### 🎨 Design

Help make the project more user-friendly:

- Improve README clarity
- Create diagrams or flowcharts
- Design better error messages
- Suggest UX improvements

## Priority Areas

### High Priority

1. **Token Refresh** - Automatic token renewal
2. **Product Search** - Better product discovery
3. **Error Handling** - More helpful error messages
4. **Testing** - Unit tests and integration tests

### Medium Priority

1. **Multi-banner** - Better support for all banners
2. **Documentation** - More examples and guides
3. **Performance** - Optimize API calls
4. **Monitoring** - Health checks and logging

### Help Wanted

Check issues labeled `help-wanted` or `good-first-issue`!

## Testing Guidelines

### Before Submitting

- [ ] Code runs without errors
- [ ] `test_api.py` passes
- [ ] No sensitive data in code
- [ ] Documentation updated
- [ ] Commit messages clear

### Manual Testing

Test with different scenarios:
- Different banners (if applicable)
- Empty cart
- Multiple items
- Error conditions
- Token expiration

## Security

### Reporting Security Issues

**DO NOT** open public issues for security vulnerabilities.

Instead, email: [security contact] or use GitHub Security Advisories.

### Security Best Practices

- Never commit credentials
- Never log bearer tokens
- Sanitize user input
- Validate API responses
- Use secure dependencies

## Getting Help

Need help contributing?

- 💬 [GitHub Discussions](https://github.com/YOUR_USERNAME/pcexpress-mcp-server/discussions)
- 📝 [Documentation](README.md)
- 🐛 [Issue Tracker](https://github.com/YOUR_USERNAME/pcexpress-mcp-server/issues)

## Recognition

Contributors will be:
- Listed in README acknowledgments
- Credited in release notes
- Given our eternal gratitude! 🙏

## Legal

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Thank you for making grocery shopping better for everyone!** 🛒✨
