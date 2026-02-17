# Contributing to MCP Hub

---

Thank you for your interest in contributing to MCP Hub!

### Development Setup

**Prerequisites**: Python 3.11+, Docker (optional), Git

```bash
git clone https://github.com/airano-ir/mcphub.git
cd mcphub
cp env.example .env
pip install -e ".[dev]"
pytest  # Verify setup
```

### Running the Server

```bash
python server.py                                    # stdio (Claude Desktop)
python server.py --transport sse --port 8000        # HTTP (testing)
```

### Code Style

```bash
black .              # Format
ruff check .         # Lint
ruff check --fix .   # Auto-fix lint issues
```

- **Line length**: 100 characters
- **Target**: Python 3.11
- **Docstrings**: Google style

### Testing

```bash
pytest                                            # All tests
pytest -v                                         # Verbose
pytest tests/test_wordpress_plugin.py             # Single file
pytest --cov=core --cov=plugins --cov-report=html # Coverage
pytest -m "not slow"                              # Skip slow
```

All contributions must include tests. Target: 70%+ coverage on core modules.

### Commit Messages

```
<type>(<scope>): <description>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
- `feat(wordpress): add bulk post update tool`
- `fix(oauth): handle expired refresh tokens`
- `test(dashboard): add session management tests`

### Pull Request Process

1. Fork the repository
2. Create a feature branch (`feat/description`, `fix/description`)
3. Make changes, add tests
4. Verify: `pytest && black --check . && ruff check .`
5. Submit PR with clear description
6. CI must pass (tests, lint, Docker build)

### Priority Contribution Areas

- **Test coverage**: Expand tests for plugins and dashboard routes
- **New plugins**: See plugin development guide below
- **Client setup guides**: Claude Desktop, Cursor, VS Code, ChatGPT
- **Workflow templates**: Pre-built AI workflow examples
- **Translations**: Dashboard i18n (currently EN/FA)

### Adding a New Plugin

Create `plugins/yourplugin/` with:

```python
# plugins/yourplugin/plugin.py
from plugins.base import BasePlugin

class YourPlugin(BasePlugin):
    @staticmethod
    def get_plugin_name() -> str:
        return "yourplugin"

    @staticmethod
    def get_required_config_keys() -> list[str]:
        return ["url", "api_key"]

    @staticmethod
    def get_tool_specifications() -> list[dict]:
        return [
            {
                "name": "list_items",
                "method_name": "list_items",
                "description": "List items from YourPlatform",
                "schema": {"type": "object", "properties": {
                    "limit": {"type": "integer", "default": 10}
                }},
                "scope": "read",
            }
        ]

    async def list_items(self, **kwargs):
        return await self.client.get("items", params=kwargs)
```

Then register in `plugins/__init__.py` and add tests.

### Project Structure

```
core/       # Core system (auth, site manager, tool registry, dashboard)
plugins/    # Plugin system (9 plugins, each with handlers + schemas)
templates/  # Jinja2 templates (dashboard + OAuth)
tests/      # Test suite (289 tests)
scripts/    # Setup & deployment scripts
docs/       # Documentation
```

See [CLAUDE.md](CLAUDE.md) for detailed architecture docs.

---

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
