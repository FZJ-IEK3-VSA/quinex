
# Use Quinex via API

## Installation
Clone this repo and install the quinex package with the `[api]` extra dependencies.

## Getting started
To start the API, make sure you are in the repository root folder. Then, you can start the API with:
```bash
uvicorn services/quinex_api/api:app --reload --port 5000
```
This starts the API on port 5000. The API is documented using OpenAPI and can be accessed at `http://localhost:5000/docs`. The API loads the models once when starting and keeps them in memory. Thus, subsequent requests are processed quickly. However, loading the models may take a few minutes depending on your hardware.

Test if the API is running:
```bash
curl -X 'GET' 'http://localhost:5000/api/is_alive/' -H 'accept: application/json'
```

You should get the following response:
```json
{"detail": "Alive and kicking!"}
```
You can now send requests to the API. For example, using `curl`:
```bash
curl -X 'POST' 'http://localhost:5000/api/process_text/?skip_imprecise_quantities=true' \ -H 'accept: application/json' -H 'Content-Type: application/json' -d '"The quick brown fox has an eigenfrequency of 5 Hz."'
```

Or using Python:
```python
import requests                        

endpoint = "http://localhost:5000/text/annotate?skip_imprecise_quantities=true"
text = "The quick brown fox has an eigenfrequency of 5 Hz."

response = requests.post(endpoint, json=text)
if response.status_code == 200:
    predictions = response.json()["predictions"]
else:
    ...
```