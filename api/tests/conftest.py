import os

# no artificial latency in tests (set before app modules import settings)
os.environ["MOCK_LATENCY_MS_MIN"] = "0"
os.environ["MOCK_LATENCY_MS_MAX"] = "0"
