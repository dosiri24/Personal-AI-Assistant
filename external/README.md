# External Dependencies

## Apple MCP (Deprecated)

The TypeScript-based Apple MCP server has been deprecated and replaced with a Python-only implementation to reduce technology stack complexity.

- **Old location**: `apple-mcp/` (moved to `apple-mcp.backup/`)
- **New implementation**: `src/tools/implementations/simple_apple_tools.py`

### Migration Benefits

1. **Unified Technology Stack**: All code is now Python-based
2. **Simplified Deployment**: No need for Node.js/Bun runtime
3. **Reduced Complexity**: Single package management system
4. **Better Integration**: Direct integration with the main codebase

### For Developers

If you need to reference the old TypeScript implementation, it's available in the `apple-mcp.backup/` directory. However, all new development should use the Python implementation in `src/tools/implementations/simple_apple_tools.py`.