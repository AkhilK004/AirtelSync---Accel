import os

# no artificial latency in tests (set before app modules import settings)
os.environ["MOCK_LATENCY_MS_MIN"] = "0"
os.environ["MOCK_LATENCY_MS_MAX"] = "0"
os.environ["LLM_PROVIDER"] = "fake"
os.environ["STORAGE"] = "memory"
os.environ["RATE_LIMIT_ENABLED"] = "false"  # limiter has its own tests; the suite makes hundreds of calls from one client
