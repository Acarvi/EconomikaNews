import os
import re
import sys
import subprocess

# Patterns for common API Keys/Secrets
SENSITIVE_PATTERNS = [
    r'AIzaSy[A-Za-z0-9_-]{33}',  # Google/Gemini
    r'sk-[A-Za-z0-9]{48}',       # OpenAI
    r'xox[bapz]-[A-Za-z0-9-]{10,}', # Slack
    r'[0-9a-fA-F]{32,}',         # Generic MD5/Hex keys
]

IGNORED_FILES = {'.env', 'security_audit.py', 'log_sanitizer.py', 'requirements.txt'}

def check_gitignore():
    """Verify that sensitive files are listed in .gitignore."""
    mandatory_ignores = {'.env', 'client_secrets.json', '.pickle'}
    if not os.path.exists('.gitignore'):
        print("❌ CRITICAL: .gitignore not found!")
        return False
    
    content = open('.gitignore', 'r').read()
    missing = []
    for m in mandatory_ignores:
        if m not in content:
            missing.append(m)
    
    if missing:
        print(f"❌ CRITICAL: Sensitive files missing from .gitignore: {', '.join(missing)}")
        return False
    return True

def scan_for_secrets():
    """Scan all Python files for hardcoded secrets."""
    print("🔍 Scanning codebase for hardcoded secrets...")
    found_secrets = False
    
    for root, dirs, files in os.walk('.'):
        if '.git' in dirs: dirs.remove('.git')
        if '__pycache__' in dirs: dirs.remove('__pycache__')
        
        for file in files:
            if file.endswith('.py') and file not in IGNORED_FILES:
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        for i, line in enumerate(lines):
                            for pattern in SENSITIVE_PATTERNS:
                                if re.search(pattern, line):
                                    # Double check if it's not an env var lookup
                                    if 'os.environ' not in line and 'getenv' not in line:
                                        print(f"❌ SECRET EXPOSURE: {path}:{i+1}")
                                        found_secrets = True
                except:
                    pass
    return not found_secrets

def check_git_tracking():
    """Ensure sensitive files are not tracked by Git."""
    sensitive_files = ['.env', 'client_secrets.json']
    tracked_files = []
    
    try:
        # Check if files are tracked/indexed
        for f in sensitive_files:
            if os.path.exists(f):
                res = subprocess.run(['git', 'ls-files', '--error-unmatch', f], 
                                     capture_output=True, text=True)
                if res.returncode == 0:
                    tracked_files.append(f)
    except:
        pass # Git not available?
        
    if tracked_files:
        print(f"⚠️ WARNING: Sensitive files are currently tracked by Git: {', '.join(tracked_files)}")
        print("Attempting to un-track them...")
        for f in tracked_files:
            subprocess.run(['git', 'rm', '--cached', f], capture_output=True)
        print("✅ Files un-tracked. Please COMMIT these changes immediately.")
    
    return True

def validate_environment():
    """Main entry point for security check."""
    print("🛡️ Initializing Anti-Exposure Audit...")
    
    status = True
    status &= check_gitignore()
    status &= scan_for_secrets()
    status &= check_git_tracking()
    
    if not status:
        print("\n🛑 STARTUP BLOCKED: Security vulnerabilities detected.")
        print("Please resolve the issues above before running the application.")
        sys.exit(1)
    
    print("✅ Security audit passed.")

if __name__ == "__main__":
    validate_environment()
