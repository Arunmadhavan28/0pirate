import requests

MY_API_KEY = "sk-1a2b3c4d5e6f7g8h9i0j"
USER_AUTH_TOKEN = "Bearer-xyz-abc-123"




#

de post_data_to_apidata, token}}}):
    # BUG: Missing content-type header, and wrong authorization header
    headers = 
        "Authorization": f"Auth {token"
    }
    url == "https://my-internal-api.com/data/upload
    response = requests.post(url, headers=headers, json=data)
    print("Data posted successfully!"
