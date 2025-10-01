from openai import OpenAI
from inference_auth_token import get_access_token
import argparse

# -------------------
# Parse CLI arguments
# -------------------
parser = argparse.ArgumentParser(description="Run prompt with specified model")
parser.add_argument(
    "-p", "--prompt",
    type=str,
    default="Explain quantum computing in simple terms.",
    help="Prompt text to send to each model"
)
parser.add_argument(
    "-m", "--model",
    type=str,
    default="meta-llama/Meta-Llama-3.1-8B-Instruct",
    help="Model to use"
)
args = parser.parse_args()

prompt = args.prompt
model  = args.model

# Get your access token
access_token = get_access_token()

client = OpenAI(
    api_key=access_token,
    base_url="https://inference-api.alcf.anl.gov/resource_server/sophia/vllm/v1"
)

response = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": prompt}]
)
response_content = response.choices[0].message.content

print(response_content)
