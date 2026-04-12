import os
import sys
import pytest
import io
from utils.log_sanitizer import init_sanitizer
from utils.security_audit import scan_for_secrets, check_gitignore

def test_log_sanitization(capsys):
    """Verify that sensitive environment variables are redacted in stdout."""
    # Set a dummy secret in environment
    os.environ["TEST_SECRET_KEY"] = "AIzaSy_MOCK_SECRET_12345"
    
    # Initialize sanitizer (this monkey-patches sys.stdout)
    init_sanitizer()
    
    # Print the secret
    print("My secret is AIzaSy_MOCK_SECRET_12345")
    
    # Capture output
    captured = capsys.readouterr()
    assert "AIzaSy_MOCK_SECRET_12345" not in captured.out
    assert "[REDACTED]" in captured.out

def test_security_audit_gitignore():
    """Verify gitignore check logic."""
    # This assumes .gitignore exists in the repo root
    assert check_gitignore() is True

def test_secret_scanner_fail():
    """Verify that the scanner detects hardcoded keys in dummy files."""
    dummy_file = "scratch/fake_exposure.py"
    os.makedirs("scratch", exist_ok=True)
    with open(dummy_file, "w") as f:
        f.write('API_KEY = "AIzaSyBzKk3iLoYKlcr-eZJGV_AXMEfPatxC6io"')
    
    # scan_for_secrets scans the current directory
    # We expect it to find the secret in the scratch folder
    assert scan_for_secrets() is False
    
    # Cleanup
    os.remove(dummy_file)

if __name__ == "__main__":
    pytest.main([__file__])
