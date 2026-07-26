import requests

def get_never_expiring_token():
    print("--- Facebook Never-Expiring Page Access Token Generator ---")
    app_id = input("Enter your Facebook App ID: ").strip()
    app_secret = input("Enter your Facebook App Secret: ").strip()
    short_user_token = input("Enter the Short-Lived User Access Token (from Graph Explorer): ").strip()

    if not app_id or not app_secret or not short_user_token:
        print("Error: All fields are required.")
        return

    # Step 1: Exchange short-lived User Token for a 60-day Long-Lived User Token
    print("\n[1/2] Exchanging for a 60-day User Access Token...")
    url_exchange = "https://graph.facebook.com/v18.0/oauth/access_token"
    params_exchange = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_user_token
    }
    
    res_exchange = requests.get(url_exchange, params=params_exchange)
    data_exchange = res_exchange.json()

    if "error" in data_exchange:
        print(f"Error exchanging token: {data_exchange['error']['message']}")
        return

    long_user_token = data_exchange.get("access_token")
    print("Success! Got Long-Lived User Access Token.")

    # Step 2: Fetch the Never-Expiring Page Access Token
    print("\n[2/2] Fetching Never-Expiring Page Access Token...")
    url_accounts = "https://graph.facebook.com/v18.0/me/accounts"
    params_accounts = {
        "access_token": long_user_token
    }
    
    res_accounts = requests.get(url_accounts, params=params_accounts)
    data_accounts = res_accounts.json()

    if "error" in data_accounts:
        print(f"Error fetching accounts: {data_accounts['error']['message']}")
        return

    pages = data_accounts.get("data", [])
    if not pages:
        print("No Facebook Pages found associated with this user token. Make sure you gave the 'pages_manage_posts' permission.")
        return

    print("\nFound the following Pages:")
    for page in pages:
        page_name = page.get("name")
        page_id = page.get("id")
        page_token = page.get("access_token")
        print(f"\n=========================================")
        print(f"Page Name:  {page_name}")
        print(f"Page ID:    {page_id}")
        print(f"Never-Expiring Access Token:\n{page_token}")
        print(f"=========================================")

if __name__ == "__main__":
    get_never_expiring_token()
