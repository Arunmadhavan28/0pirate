 # Data Uploader Library for Internal API

## Introduction

This library is designed to simplify the process of uploading data to our internal API. The `post_data_to_apidata` function handles the communication with the API, allowing you to focus on preparing your data for submission.

## Key Features

- Easy data uploading via a single function call
- Automatic JSON serialization of input data
- Error handling and response logging

## API Reference

### post_data_to_apidata(data, token)

Uploads the provided `data` to the internal API using the specified `token`. The function automatically serializes the data as JSON and handles communication with the API.

#### Parameters
- **data (dict):** A dictionary containing the data to be uploaded.
- **token (str):** An authentication token for accessing the API. This should be a string in the format `"Bearer-[TOKEN]"`.

#### Returns
A response object from the API, which can be accessed via `response.content` or `response.json()`. The function also logs the response to help with debugging.

## Usage Example

```python
import json
from data_uploader import post_data_to_apidata

# Replace <SECRET_1> with your actual secret token
MY_SECRET_1 = "Your-secret-token"
USER_AUTH_TOKEN = f"Bearer-{MY_SECRET_1}"

# Sample data to upload
sample_data = {
    "key": "value",
}

# Upload the sample data using the authentication token
response = post_data_to_apidata(sample_data, USER_AUTH_TOKEN)

# If successful, the response will be printed to the console
```