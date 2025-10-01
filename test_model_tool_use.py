#!/usr/bin/env python3
"""
Test Tool Use Capabilities Across Hot Models

This script tests which of the hot ALCF models can properly use tools
through function calling in JSON format.
"""

import json
import requests
import time
import os
from typing import Dict, List, Any

class ModelToolUseTester:
    """Test tool use capabilities across different models"""

    def __init__(self, base_url: str, access_token: str):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        # Hot models to test
        self.models = [
            ("qwen2.57bi", "Qwen/Qwen2.5-7B-Instruct"),
            ("llama318bi", "meta-llama/Meta-Llama-3.1-8B-Instruct"),
            ("llama3170bi", "meta-llama/Meta-Llama-3.1-70B-Instruct"),
            ("llama31405bi", "meta-llama/Meta-Llama-3.1-405B-Instruct"),
            ("mistral7bi", "mistralai/Mistral-7B-Instruct-v0.3")
        ]

    def create_tool_system_prompt(self) -> str:
        """Create system prompt with tool definitions"""
        return """You are a helpful AI assistant with access to tools. You can call functions to help users.

Available Functions:
Function: calculate_math
Description: Perform mathematical calculations
Parameters: {
  "type": "object",
  "properties": {
    "expression": {
      "type": "string",
      "description": "Mathematical expression to evaluate"
    },
    "operation": {
      "type": "string",
      "description": "Type of math operation",
      "enum": ["add", "multiply", "factorial", "power"]
    }
  },
  "required": ["expression"]
}

Function: get_time
Description: Get current time information
Parameters: {
  "type": "object",
  "properties": {
    "format": {
      "type": "string",
      "description": "Time format to return",
      "enum": ["12hour", "24hour", "iso"]
    }
  }
}

To call a function, respond with a JSON object in this exact format:
{
    "function_call": {
        "name": "function_name",
        "parameters": {
            "param1": "value1"
        }
    }
}

Always include your reasoning before the function call."""

    def test_model_tool_use(self, model_short: str, model_name: str) -> Dict[str, Any]:
        """Test a single model's tool use capability"""

        test_prompt = "Calculate 15 * 23 using the math tool"

        messages = [
            {"role": "system", "content": self.create_tool_system_prompt()},
            {"role": "user", "content": test_prompt}
        ]

        payload = {
            "model": model_name,
            "messages": messages,
            "max_tokens": 800,
            "temperature": 0.3,
            "stream": False
        }

        try:
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            elapsed = time.time() - start_time

            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]

                # Check if response contains function call
                has_function_call = self.parse_function_call(content)

                return {
                    "success": True,
                    "response_time": elapsed,
                    "content": content,
                    "has_function_call": has_function_call is not None,
                    "function_call": has_function_call,
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "response_time": elapsed,
                    "content": None,
                    "has_function_call": False,
                    "function_call": None,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }

        except Exception as e:
            return {
                "success": False,
                "response_time": -1,
                "content": None,
                "has_function_call": False,
                "function_call": None,
                "error": str(e)
            }

    def parse_function_call(self, response: str) -> Dict[str, Any]:
        """Parse function call from model response"""
        try:
            if "function_call" in response:
                # Find JSON block
                start = response.find("{")
                end = response.rfind("}") + 1
                if start >= 0 and end > start:
                    json_str = response[start:end]
                    parsed = json.loads(json_str)
                    if "function_call" in parsed:
                        return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    def evaluate_tool_capability(self, result: Dict[str, Any]) -> str:
        """Evaluate tool use capability level"""
        if not result["success"]:
            return "❌ FAILED"

        if result["has_function_call"]:
            func_call = result["function_call"]
            if (func_call and
                "function_call" in func_call and
                "name" in func_call["function_call"] and
                "parameters" in func_call["function_call"]):
                return "✅ EXCELLENT"
            else:
                return "⚠️  PARTIAL"
        else:
            # Check if it at least mentions tools or functions
            content = result["content"].lower()
            if any(word in content for word in ["function", "tool", "call", "calculate"]):
                return "🔶 AWARE"
            else:
                return "❌ NO TOOLS"

    def run_all_tests(self):
        """Test all hot models for tool use capability"""
        print("🛠️  TESTING TOOL USE CAPABILITIES ACROSS HOT MODELS")
        print("=" * 70)
        print("Testing which models can properly use function calling...\n")

        results = []

        for model_short, model_name in self.models:
            print(f"🔍 Testing: {model_name}")
            print(f"   Short name: {model_short}")

            result = self.test_model_tool_use(model_short, model_name)
            capability = self.evaluate_tool_capability(result)

            print(f"   Response time: {result['response_time']:.1f}s")
            print(f"   Tool capability: {capability}")

            if result["has_function_call"]:
                func_call = result["function_call"]["function_call"]
                print(f"   Function called: {func_call['name']}")
                print(f"   Parameters: {func_call.get('parameters', {})}")
            elif result["success"]:
                # Show first 100 chars of response
                preview = result["content"][:100] + "..." if len(result["content"]) > 100 else result["content"]
                print(f"   Response preview: {preview}")
            else:
                print(f"   Error: {result['error']}")

            results.append({
                "model_short": model_short,
                "model_name": model_name,
                "capability": capability,
                "result": result
            })

            print()
            time.sleep(1)  # Brief pause between tests

        # Summary
        print("📊 TOOL USE CAPABILITY SUMMARY")
        print("-" * 40)

        excellent = [r for r in results if "EXCELLENT" in r["capability"]]
        partial = [r for r in results if "PARTIAL" in r["capability"]]
        aware = [r for r in results if "AWARE" in r["capability"]]
        no_tools = [r for r in results if "NO TOOLS" in r["capability"]]
        failed = [r for r in results if "FAILED" in r["capability"]]

        print(f"✅ Excellent tool use: {len(excellent)}")
        for r in excellent:
            print(f"   • {r['model_short']} ({r['model_name']})")

        print(f"\n⚠️  Partial tool use: {len(partial)}")
        for r in partial:
            print(f"   • {r['model_short']} ({r['model_name']})")

        print(f"\n🔶 Tool aware: {len(aware)}")
        for r in aware:
            print(f"   • {r['model_short']} ({r['model_name']})")

        print(f"\n❌ No tool use: {len(no_tools)}")
        for r in no_tools:
            print(f"   • {r['model_short']} ({r['model_name']})")

        print(f"\n❌ Failed tests: {len(failed)}")
        for r in failed:
            print(f"   • {r['model_short']} ({r['model_name']})")

        return results


def main():
    """Main function"""
    # Configuration
    BASE_URL = "https://inference-api.alcf.anl.gov/resource_server/sophia/vllm"

    # Get access token
    try:
        from inference_auth_token import get_access_token
        ACCESS_TOKEN = get_access_token()
    except ImportError:
        ACCESS_TOKEN = os.environ.get("ALCF_ACCESS_TOKEN")
        if not ACCESS_TOKEN:
            print("❌ Error: Set ALCF_ACCESS_TOKEN or install inference_auth_token.py")
            return

    # Run tests
    tester = ModelToolUseTester(BASE_URL, ACCESS_TOKEN)
    results = tester.run_all_tests()

    print(f"\n🎉 Tool use testing complete!")
    print(f"📝 Tested {len(results)} hot models for function calling capabilities")


if __name__ == "__main__":
    main()