import http.cookiejar
import os
import base64
import tempfile

def get_cookies(filename="x.com_cookies.txt"):
    """
    Get cookies from environment variable (cloud) or file (local).
    For cloud: set TWITTER_COOKIES env var with base64-encoded cookie file content.
    """
    # Check for environment variable first (cloud deployment)
    env_cookies = os.environ.get("TWITTER_COOKIES")
    if env_cookies:
        try:
            # Decode base64 and write to temp file
            decoded = base64.b64decode(env_cookies).decode('utf-8')
            temp_path = os.path.join(tempfile.gettempdir(), "x_cookies.txt")
            with open(temp_path, 'w') as f:
                f.write(decoded)
            return netscape_to_dict(temp_path)
        except Exception as e:
            print(f"Error loading cookies from env: {e}")
    
    # Fallback to local file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, filename)
    if os.path.exists(file_path):
        return netscape_to_dict(file_path)
    
    return {}

def netscape_to_dict(filename):
    """
    Parses a Netscape format cookies file and returns a dictionary.
    """
    cookies = {}
    try:
        # We use MozillaCookieJar because it natively understands the Netscape format
        jar = http.cookiejar.MozillaCookieJar(filename)
        # ignore_discard=True, ignore_expires=True helps to get more cookies
        jar.load(ignore_discard=True, ignore_expires=True)
        for cookie in jar:
            cookies[cookie.name] = cookie.value
        return cookies
    except Exception as e:
        print(f"Error parsing cookies: {e}")
        # Manual fallback for files that might lack the proper header
        try:
            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.startswith('#') or not line.strip():
                        continue
                    parts = line.strip().split('\t')
                    if len(parts) >= 7:
                        # Name is at 6 (0-indexed), Value is at 7 (sometimes)
                        # Part indexes: 0: domain, 1: flag, 2: path, 3: secure, 4: expiration, 5: name, 6: value
                        name = parts[5]
                        value = parts[6]
                        cookies[name] = value
            return cookies
        except:
            return {}

if __name__ == "__main__":
    # Test with x.com_cookies.txt
    import sys
    fname = sys.argv[1] if len(sys.argv) > 1 else "cookies.txt"
    if os.path.exists(fname):
        d = netscape_to_dict(fname)
        print(f"Parsed {len(d)} cookies.")
        if 'auth_token' in d:
             print("Found auth_token! Ready for Twikit.")
        else:
             print("auth_token not found. Login might fail.")
    else:
        print(f"File {fname} not found.")
