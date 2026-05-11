from utils.network import check_centralai_health
import logging

logging.basicConfig(level=logging.INFO)
print("Starting Health Test with Auto-Start...")
result = check_centralai_health("http://localhost:8080")
print(f"Final Result: {result}")
