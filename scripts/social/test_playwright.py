import time
from playwright.sync_api import sync_playwright

def parse_netscape_cookies(file_path):
    cookies = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.strip().split('\t')
            if len(parts) >= 7:
                domain, flag, path, secure, expiry, name, value = parts[:7]
                # Only load Facebook cookies to keep it clean
                if "facebook.com" in domain:
                    cookies.append({
                        "name": name,
                        "value": value,
                        "domain": domain,
                        "path": path,
                        "secure": secure.upper() == "TRUE"
                    })
    return cookies

def run():
    print("Loading cookies from fbcookies.txt...")
    fb_cookies = parse_netscape_cookies("/home/phxlm/Downloads/fbcookies.txt")
    print(f"Loaded {len(fb_cookies)} Facebook cookies.")

    with sync_playwright() as p:
        # Launch headed so you can see it!
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        
        # Inject the cookies
        context.add_cookies(fb_cookies)
        
        page = context.new_page()
        print("Navigating to Facebook...")
        
        # Go to one of your posts (the one we fixed earlier)
        page.goto("https://www.facebook.com/1216097278244158/posts/122108125371372333")
        page.wait_for_load_state("networkidle")
        
        print("Page loaded! Pausing execution...")
        print("The Playwright Inspector should pop up. You can now use your keyboard in the browser to count your tabs.")
        print("When you're done, just close the browser or the inspector window to kill the script.")
        
        # This will pause the script indefinitely and open the Playwright Inspector, 
        # allowing you to interact with the page manually.
        page.pause()
        
        browser.close()

if __name__ == "__main__":
    run()
