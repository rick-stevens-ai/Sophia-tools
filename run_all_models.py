import requests
from openai import OpenAI, APIConnectionError, APITimeoutError
import time
import re
from inference_auth_token import get_access_token
import argparse

# -------------------
# Parse CLI arguments
# -------------------
parser = argparse.ArgumentParser(description="Run prompt across all running models")
parser.add_argument(
    "-p", "--prompt",
    type=str,
    default="Explain quantum computing in simple terms.",
    help="Prompt text to send to each model"
)
parser.add_argument(
    "-d", "--displaylength",
    type=int,
    default=80,
    help="Number of characters to display from each model's response"
)
parser.add_argument(
    "-t", "--timeout",
    type=int,
    default=30,
    help="Timeout in seconds"
)
parser.add_argument(
    "-b", "--brief",
    action="store_true",
    help="Do not show responses"
)
args = parser.parse_args()

prompt = args.prompt
length = args.displaylength
timeout= args.timeout
brief  = args.brief

# -------------------
# Helper function
# -------------------
def retrieve_model_list(j, key):
    l = j[key]
    models = [m['Models'] for m in l]
    all_models = [name.strip() for s in models for name in s.split(",")]
    all_models = sorted(list(set(all_models)))
    return all_models

# -------------------
# Main logic
# -------------------
# Get your access token
access_token = get_access_token()

# Retrieve information about inference service models
url = "https://inference-api.alcf.anl.gov/resource_server/sophia/jobs"
headers = {"Authorization": f"Bearer {access_token}"}
response = requests.get(url, headers=headers)

if not response.ok:
    print(f"Error {response.status_code}: {response.text}")
    exit(1)

j = response.json()
models = retrieve_model_list(j, 'running')
max_length = len(max(models, key=len))

client = OpenAI(
    api_key=access_token,
    base_url="https://inference-api.alcf.anl.gov/resource_server/sophia/vllm/v1"
)

print(f'Running {len(models)} models', end='')
print() if brief else print(f': {", ".join(map(str, models))}\nPrompt: {prompt}\nResponses (first {length} characters):')

for model in models:
    start = time.time()

    try:
        response = client.with_options(timeout=timeout).chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
    except APITimeoutError:
        # request exceeded your timeout
        print(f'  {model:<{max_length}}: Timeout after {timeout} seconds')
        continue
    except APIConnectionError as e:
        # network problems, DNS, etc.
        print(f'  {model:<{max_length}}: Connection error')
        continue

    if response.choices == None:
        print(f"  {model:<{max_length}}: {response.error['message']}")
        continue
    response_time = response.response_time

    response_content = response.choices[0].message.content
    end = time.time()
    content_length = len(response_content)
    request_time = end - start
    clean_text = re.sub(r"\s+", " ", response_content).strip()
    suffix = '' if content_length <= length else '...'

    print(f'  {model:<{max_length}}: {content_length:4d} bytes in {request_time:5.2f} ({response_time:5.2f}) secs', end='')
    print() if brief else print(f'\n    {clean_text[:length]}{suffix}')

