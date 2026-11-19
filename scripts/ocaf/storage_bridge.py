#!/usr/bin/env python3
"""Deprecated compatibility import for the Android MCP client; not an OCAF adapter."""
if __name__ == '__main__':
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from omega_mcp.storage_bridge import main
    print('Deprecated path: use scripts/omega_mcp/storage_bridge.py (MCP, not OCAF).', file=sys.stderr)
    sys.exit(main())
else:
    from omega_mcp.storage_bridge import *  # noqa: F401,F403 -- legacy public API
