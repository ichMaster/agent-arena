"""Agent Client package — CLI event loop, the ``LLMClient`` seam, prompt/memory/profile.

A pure external client: imports nothing from ``server/``; talks to the server only over HTTP/WS.
The model API key lives only in this process.
"""
