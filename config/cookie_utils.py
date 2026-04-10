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
    Ensures that for each cookie name, only the first one found is kept to avoid 'Multiple cookies' errors.
    """
    cookies = {}
    seen_names = set()
    
    # 1. First, attempt to clean the file physically if it has duplicates
    try:
        if os.path.exists(filename):
            clean_cookie_file(filename)
    except Exception as e:
        print(f"Warning: Failed to physically clean cookie file {filename}: {e}")

    try:
        # Load entries into a list to sort them for prioritization
        jar = http.cookiejar.MozillaCookieJar(filename)
        jar.load(ignore_discard=True, ignore_expires=True)
        
        # Prioritization: .x.com > x.com > .twitter.com
        def domain_priority(domain):
            if domain == '.x.com': return 0
            if 'x.com' in domain: return 1
            if 'twitter.com' in domain: return 2
            return 3

        all_cookies = sorted(list(jar), key=lambda c: domain_priority(c.domain))
        
        for cookie in all_cookies:
            if cookie.name not in seen_names:
                cookies[cookie.name] = cookie.value
                seen_names.add(cookie.name)
        return cookies
    except Exception as e:
        print(f"Error parsing cookies with MozillaCookieJar: {e}")
        # Manual fallback for files that might lack the proper header or have issues
        try:
            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.startswith('#') or not line.strip():
                        continue
                    parts = line.strip().split('\t')
                    if len(parts) >= 7:
                        # Part indexes: 0: domain, 1: flag, 2: path, 3: secure, 4: expiration, 5: name, 6: value
                        name = parts[5]
                        value = parts[6]
                        if name not in seen_names:
                            cookies[name] = value
                            seen_names.add(name)
            return cookies
        except:
            return {}

def clean_cookie_file(filename):
    """
    Reads a Netscape cookie file and rewrites it, keeping only the first occurrence of each cookie name.
    This fixes 'Multiple cookies exist with name=twid' errors in scraper libraries.
    """
    if not os.path.exists(filename):
        return

    try:
        lines = []
        with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        cleaned_lines = []
        seen_names = set()
        header_lines = []
        
        # 1. Separate headers and cookie entries
        cookie_entries = []
        for line in lines:
            if line.startswith('#'):
                header_lines.append(line)
                continue
            if not line.strip():
                continue
            parts = line.strip().split('\t')
            if len(parts) >= 6:
                cookie_entries.append({'line': line, 'domain': parts[0], 'name': parts[5]})
            else:
                cleaned_lines.append(line)

        # 2. Sort entries by domain priority: .x.com > x.com > .twitter.com
        def domain_priority(domain):
            if domain == '.x.com': return 0
            if 'x.com' in domain: return 1
            if 'twitter.com' in domain: return 2
            return 3
        
        cookie_entries.sort(key=lambda x: domain_priority(x['domain']))

        # 3. Deduplicate by name
        for entry in cookie_entries:
            if entry['name'] not in seen_names:
                cleaned_lines.append(entry['line'])
                seen_names.add(entry['name'])

        # Only write back if we actually removed something
        if len(cleaned_lines) + len(header_lines) < len(lines):
            # To be extra safe, write to a temp file then rename
            temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(filename))
            try:
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    f.writelines(header_lines)
                    f.writelines(cleaned_lines)
                os.replace(temp_path, filename)
                print(f"✅ Cleaned cookie file {filename}: removed duplicates.")
            except Exception as e:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise e
    except Exception as e:
        print(f"Error cleaning cookie file {filename}: {e}")

import json

def netscape_to_json(txt_path, json_path=None):
    """
    Parses a Netscape cookie file and saves it as a Twikit-compatible JSON file.
    Returns the dictionary used.
    """
    if not json_path:
        json_path = txt_path.replace('.txt', '.json')
    
    cookies = netscape_to_dict(txt_path)
    if cookies:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, indent=4)
        print(f"✅ Created Twikit JSON cookies: {json_path}")
    return cookies

if __name__ == "__main__":
    # Test with x.com_cookies.txt
    import sys
    fname = sys.argv[1] if len(sys.argv) > 1 else "cookies.txt"
    if os.path.exists(fname):
        clean_cookie_file(fname)
        # Use JSON for Twikit
        json_fname = fname.replace('.txt', '.json')
        d = netscape_to_json(fname, json_fname)
        print(f"Parsed {len(d)} cookies and saved to {json_fname}.")
        if 'auth_token' in d:
             print("Found auth_token! Ready for Twikit.")
        else:
             print("auth_token not found. Login might fail.")
    else:
        print(f"File {fname} not found.")
