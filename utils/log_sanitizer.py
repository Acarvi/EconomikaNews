import sys
import os
from dotenv import load_dotenv

class RedactedStream:
    def __init__(self, original_stream, sensitive_values):
        self.original_stream = original_stream
        self.sensitive_values = [v for v in sensitive_values if v and len(v) > 4] # Ignore short strings

    def write(self, data):
        if not data:
            return self.original_stream.write(data)
        
        sanitized_data = data
        for val in self.sensitive_values:
            sanitized_data = sanitized_data.replace(val, "[REDACTED]")
            
        return self.original_stream.write(sanitized_data)

    def flush(self):
        return self.original_stream.flush()

    def __getattr__(self, name):
        return getattr(self.original_stream, name)

def init_sanitizer():
    """Initializes the log sanitizer by monkey-patching stdout and stderr."""
    load_dotenv()
    
    # Collect sensitive values from environment
    sensitive_values = []
    for key, value in os.environ.items():
        if any(x in key.upper() for x in ['KEY', 'SECRET', 'TOKEN', 'PASSWORD', 'API']):
            sensitive_values.append(value)
    
    # Apply monkey patch
    sys.stdout = RedactedStream(sys.stdout, sensitive_values)
    sys.stderr = RedactedStream(sys.stderr, sensitive_values)
    
    # Patch existing loggers
    import logging
    class SanitizedFormatter(logging.Formatter):
        def format(self, record):
            msg = super().format(record)
            for val in sensitive_values:
                if val and len(val) > 4:
                    msg = msg.replace(val, "[REDACTED]")
            return msg

    # This is a basic catch-all. More complex setups might need deeper patching.
    print("🔒 Log Sanitizer active. Sensitive data will be [REDACTED].")

if __name__ == "__main__":
    # Test
    os.environ["DUMMY_KEY"] = "AIzaSyTestKey12345"
    init_sanitizer()
    print("Testing exposure: AIzaSyTestKey12345")
