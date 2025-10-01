import os, sys, json, requests, time, argparse
from datetime import datetime

def enableWindowsAnsi():
    """Enable ANSI escape sequences on Windows."""
    if os.name != 'nt':
        return True
    try:
        import colorama
        colorama.justFixWindowsConsole()
        return True
    except Exception:
        pass
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)) == 0:
            return False
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        if (mode.value & ENABLE_VIRTUAL_TERMINAL_PROCESSING) == 0:
            if kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING) == 0:
                return False
        return True
    except Exception:
        return False

def sgr(*codes):
    """Generate ANSI SGR escape sequence."""
    return f"\033[{';'.join(map(str, codes))}m"

# Color constants
RESET = sgr(0)
BOLD = sgr(1)
DIM = sgr(2)
RED = sgr(31)
GREEN = sgr(32)
YELLOW = sgr(33)
BLUE = sgr(34)
MAGENTA = sgr(35)
CYAN = sgr(36)
WHITE = sgr(37)

# Enable ANSI colors
enableWindowsAnsi()

# Global verbose flag
VERBOSE = False

def logInfo(message):
    """Print info message with timestamp and color."""
    if VERBOSE:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{DIM}[{timestamp}]{RESET} {BLUE}ℹ{RESET} {message}")

def logSuccess(message):
    """Print success message with timestamp and color."""
    if VERBOSE:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{DIM}[{timestamp}]{RESET} {GREEN}✓{RESET} {message}")

def logWarning(message):
    """Print warning message with timestamp and color."""
    if VERBOSE:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{DIM}[{timestamp}]{RESET} {YELLOW}⚠{RESET} {message}")

def logError(message):
    """Print error message with timestamp and color."""
    if VERBOSE:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{DIM}[{timestamp}]{RESET} {RED}✗{RESET} {message}", file=sys.stderr)

def logCriticalError(message):
    """Print critical error message (always shown)."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{DIM}[{timestamp}]{RESET} {RED}✗{RESET} {message}", file=sys.stderr)

def logProgress(message):
    """Print progress message with spinner."""
    if VERBOSE:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{DIM}[{timestamp}]{RESET} {CYAN}⟳{RESET} {message}")

# Parse command line arguments
parser = argparse.ArgumentParser(description="Check ALCF model availability and status")
parser.add_argument("--verbose", "-v", action="store_true",
                   help="Enable verbose logging with detailed progress information")
parser.add_argument("--live-only", "-l", action="store_true",
                   help="Show only live/running models in the output")
args = parser.parse_args()

VERBOSE = args.verbose

# If you used the helper from the docs:
logInfo("Initializing ALCF API client...")
try:
    from inference_auth_token import get_access_token  # from the doc's script
    logProgress("Getting access token from inference_auth_token module...")
    accessToken = get_access_token()
    logSuccess("Access token obtained successfully")
except Exception as e:
    logWarning(f"Failed to get token from inference_auth_token: {e}")
    logProgress("Falling back to environment variable...")
    accessToken = os.environ.get("ALCF_ACCESS_TOKEN")
    if not accessToken:
        logCriticalError("Set ALCF_ACCESS_TOKEN or install/use inference_auth_token.py")
        sys.exit(1)
    logSuccess("Access token obtained from environment variable")

base = "https://inference-api.alcf.anl.gov"
headers = {"Authorization": f"Bearer {accessToken}"}

def safeGet(url, description="API call"):
    """Make a safe GET request with detailed logging and error handling."""
    logProgress(f"{description}: {url}")
    startTime = time.time()
    
    try:
        r = requests.get(url, headers=headers, timeout=30)
        elapsedTime = time.time() - startTime
        
        if r.status_code == 200:
            logSuccess(f"{description} completed in {elapsedTime:.2f}s")
        else:
            logWarning(f"{description} returned status {r.status_code} in {elapsedTime:.2f}s")
        
        r.raise_for_status()
        data = r.json()
        
        # Log some basic info about the response
        if isinstance(data, list):
            logInfo(f"Retrieved {len(data)} items")
        elif isinstance(data, dict):
            if 'items' in data:
                logInfo(f"Retrieved {len(data['items'])} items from response")
            else:
                logInfo(f"Retrieved response with {len(data.keys())} keys")
        
        return data
        
    except requests.exceptions.Timeout:
        elapsedTime = time.time() - startTime
        logError(f"{description} timed out after {elapsedTime:.2f}s")
        raise
    except requests.exceptions.RequestException as e:
        elapsedTime = time.time() - startTime
        logError(f"{description} failed after {elapsedTime:.2f}s: {e}")
        raise
    except json.JSONDecodeError as e:
        elapsedTime = time.time() - startTime
        logError(f"{description} returned invalid JSON after {elapsedTime:.2f}s: {e}")
        raise
    except Exception as e:
        elapsedTime = time.time() - startTime
        logError(f"{description} encountered unexpected error after {elapsedTime:.2f}s: {e}")
        raise

def getAvailableModels(endpoint="https://inference-api.alcf.anl.gov/resource_server"):
    """Get list of available models using multiple endpoint strategies."""
    modelEndpoints = [
        f"{endpoint}/list-endpoints",
        f"{endpoint}/models", 
        f"{endpoint}/v1/models"
    ]
    
    allModels = []
    
    for modelUrl in modelEndpoints:
        try:
            logProgress(f"Checking models endpoint: {modelUrl}")
            data = safeGet(modelUrl, f"Available models query")
            models = []
            
            if "clusters" in data:
                logInfo("Found clusters structure in response")
                for clusterName, clusterInfo in data["clusters"].items():
                    if "frameworks" in clusterInfo:
                        for frameworkName, frameworkInfo in clusterInfo["frameworks"].items():
                            if "models" in frameworkInfo and isinstance(frameworkInfo["models"], list):
                                for model in frameworkInfo["models"]:
                                    baseUrl = clusterInfo.get("base_url", "")
                                    endpoints = frameworkInfo.get("endpoints", {})
                                    chatEndpoint = endpoints.get("chat", "")
                                    fullChatUrl = f"https://inference-api.alcf.anl.gov{baseUrl}{chatEndpoint}".rstrip('/') if chatEndpoint else None
                                    models.append({
                                        "name": model,
                                        "cluster": clusterName,
                                        "framework": frameworkName,
                                        "chat_url": fullChatUrl,
                                        "source": "clusters"
                                    })
            elif "endpoints" in data and isinstance(data["endpoints"], list):
                logInfo("Found endpoints list structure in response")
                for endpointItem in data["endpoints"]:
                    if isinstance(endpointItem, dict):
                        modelName = endpointItem.get("model", endpointItem.get("name", "Unknown"))
                        models.append({
                            "name": modelName,
                            "cluster": "default",
                            "framework": "default", 
                            "chat_url": None,
                            "source": "endpoints"
                        })
            elif "data" in data and isinstance(data["data"], list):
                logInfo("Found data list structure in response")
                for model in data["data"]:
                    if isinstance(model, dict):
                        modelId = model.get("id", model.get("name", "Unknown"))
                        models.append({
                            "name": modelId,
                            "cluster": "default",
                            "framework": "default",
                            "chat_url": None,
                            "source": "data"
                        })
            elif isinstance(data, list):
                logInfo("Found direct list structure in response")
                for item in data:
                    if isinstance(item, dict):
                        name, _ = guessFields(item)
                        if name:
                            models.append({
                                "name": name,
                                "cluster": "default", 
                                "framework": "default",
                                "chat_url": None,
                                "source": "direct_list"
                            })
            
            if models:
                logSuccess(f"Found {len(models)} models from {modelUrl}")
                allModels.extend(models)
            else:
                logWarning(f"No models found in response from {modelUrl}")
                
        except Exception as e:
            logWarning(f"Failed to fetch models from {modelUrl}: {e}")
            continue
    
    return allModels

logInfo("Starting ALCF endpoint status check...")
print()

# 1) Get available models (configured and ready to use)
logInfo("Fetching available models...")
availableModels = getAvailableModels()

# 2) What's actually running/queued right now
logInfo("Fetching current jobs status...")
jobs = safeGet(f"{base}/resource_server/sophia/jobs", "Jobs status query")

# Debug: show raw jobs response structure
if isinstance(jobs, dict):
    logInfo(f"Jobs response keys: {list(jobs.keys())}")
    if 'items' in jobs:
        logInfo(f"Jobs items count: {len(jobs.get('items', []))}")
        if jobs.get('items'):
            logInfo(f"First job sample keys: {list(jobs['items'][0].keys())}")
    else:
        # Check other possible keys
        for key in jobs.keys():
            if isinstance(jobs[key], list):
                logInfo(f"Found list under key '{key}' with {len(jobs[key])} items")

# 3) Full catalog, including Offline
logInfo("Fetching full endpoint catalog...")
endpoints = safeGet(f"{base}/resource_server/list-endpoints", "Endpoints catalog query")

# Debug: show raw endpoints response structure  
if isinstance(endpoints, dict):
    logInfo(f"Endpoints response keys: {list(endpoints.keys())}")
    if 'items' in endpoints:
        logInfo(f"Endpoints items count: {len(endpoints.get('items', []))}")
    # Check clusters structure which we know exists
    if 'clusters' in endpoints:
        logInfo("Found clusters in endpoints response")
        for clusterName, clusterInfo in endpoints['clusters'].items():
            if 'frameworks' in clusterInfo:
                for frameworkName, frameworkInfo in clusterInfo['frameworks'].items():
                    if 'status' in frameworkInfo or 'state' in frameworkInfo:
                        status = frameworkInfo.get('status') or frameworkInfo.get('state')
                        logInfo(f"Framework {frameworkName} in {clusterName} has status: {status}")
                    
                    # Check for status at cluster or framework level
                    if 'endpoints' in frameworkInfo:
                        endpoints_data = frameworkInfo['endpoints']
                        logInfo(f"Framework {frameworkName} has endpoints data: {list(endpoints_data.keys()) if isinstance(endpoints_data, dict) else type(endpoints_data)}")
                    
                    if 'models' in frameworkInfo:
                        modelList = frameworkInfo['models']
                        if isinstance(modelList, list):
                            logInfo(f"Framework {frameworkName} has {len(modelList)} models configured")
                            # Check if any models have status info
                            for i, model in enumerate(modelList[:3]):  # Check first 3
                                if isinstance(model, dict):
                                    logInfo(f"Model {i} is dict with keys: {list(model.keys())}")
                                else:
                                    logInfo(f"Model {i} is string: {model}")
                        elif isinstance(modelList, dict):
                            logInfo(f"Framework {frameworkName} has models as dict with keys: {list(modelList.keys())}")
            
            # Check cluster-level status
            if 'status' in clusterInfo or 'state' in clusterInfo:
                status = clusterInfo.get('status') or clusterInfo.get('state')  
                logInfo(f"Cluster {clusterName} has status: {status}")
            
            # Look for other status-indicating fields
            statusFields = ['running', 'active', 'live', 'online', 'available']
            for field in statusFields:
                if field in clusterInfo:
                    logInfo(f"Cluster {clusterName} has {field}: {clusterInfo[field]}")

def guessFields(item):
    """Robust field guessing since schema may evolve."""
    name = item.get("model") or item.get("name") or item.get("endpoint") or item.get("id")
    status = item.get("status") or item.get("state") or item.get("endpoint_status") or item.get("lifecycle")
    
    # Handle job structure with Models, Framework, Cluster
    if not name and "Models" in item:
        models = item.get("Models")
        framework = item.get("Framework", "")
        cluster = item.get("Cluster", "")
        
        if isinstance(models, list) and models:
            # If multiple models, show the first one with count
            if len(models) == 1:
                name = models[0]
            else:
                name = f"{models[0]} (+{len(models)-1} others)"
        elif isinstance(models, str):
            name = models
        else:
            name = f"{framework} on {cluster}" if framework and cluster else None
        
        # For job items, check specific job status fields 
        if not status:
            # Check Model Status first (more specific), then Job State
            status = item.get("Model Status") or item.get("Job State")
            
            # If job has "Estimated Start Time", it's probably not live yet
            if "Estimated Start Time" in item:
                status = "Starting"  # Override to indicate not fully live
                
    # Log if we couldn't find expected fields (but less verbosely now)
    if not name:
        logWarning(f"Could not determine name for item: {list(item.keys())[:3]}...")
    
    return name, (status or "").strip()

def formatStatus(status):
    """Format status with appropriate color."""
    if status in {"Live", "Running", "Loaded"}:
        return f"{GREEN}{status}{RESET}"
    elif status == "Starting":
        return f"{YELLOW}{status}{RESET}"
    elif status == "Queued":
        return f"{BLUE}{status}{RESET}"
    elif status in {"Offline", "Stopped", "Failed"}:
        return f"{RED}{status}{RESET}"
    else:
        return f"{DIM}{status}{RESET}"

# First, show available models
if VERBOSE:
    print()
    logInfo("Processing available models...")
    print(f"\n{BOLD}=== AVAILABLE MODELS (Configured & Ready) ==={RESET}")

# Remove duplicates by model name
uniqueModels = {}
for model in availableModels:
    modelName = model["name"]
    if modelName not in uniqueModels:
        uniqueModels[modelName] = model

if uniqueModels:
    if VERBOSE:
        # Group by source for better organization
        bySource = {}
        for modelName, modelInfo in uniqueModels.items():
            source = modelInfo["source"]
            if source not in bySource:
                bySource[source] = []
            bySource[source].append(modelInfo)
        
        for source, models in bySource.items():
            print(f"\n{CYAN}From {source} endpoint:{RESET}")
            for model in sorted(models, key=lambda x: x["name"]):
                clusterInfo = f" ({model['cluster']}/{model['framework']})" if model['cluster'] != 'default' else ""
                print(f"  {GREEN}✓{RESET} {model['name']}{clusterInfo}")
    
    logSuccess(f"Found {len(uniqueModels)} total available models")
else:
    if VERBOSE:
        print(f"{DIM}  No available models found{RESET}")
        logWarning("This might indicate an API access issue")

activeStatuses = {"Live", "Running", "Starting", "Loaded"}   # treat these as "active"
logInfo("Processing active jobs...")
if VERBOSE:
    print(f"\n{BOLD}=== ACTIVE (Live/Running/Starting/Loaded) FROM /jobs ==={RESET}")
activeCount = 0
activeModels = []  # Collect active model names
startingModels = []  # Collect starting model names
queuedModels = []  # Collect queued model names

# Handle different job response structures - only consider 'running' section as truly live
if isinstance(jobs, list):
    jobItems = jobs
    activeCount = len(jobs)
elif isinstance(jobs, dict):
    jobItems = []
    # Process jobs from running and queued sections
    if 'running' in jobs and isinstance(jobs['running'], list):
        logInfo(f"Processing {len(jobs['running'])} jobs from 'running' section")
        for item in jobs['running']:
            jobItems.append(item)
    
    # Also check other sections - some might be live with status "running"
    sections_to_check = ['queued', 'others', 'private-batch-running']
    for section in sections_to_check:
        if section in jobs and isinstance(jobs[section], list):
            logInfo(f"Processing {len(jobs[section])} jobs from '{section}' section")
            for item in jobs[section]:
                jobItems.append(item)
            
    # activeCount reflects total jobs processed (will be filtered by status later)
    activeCount = sum(len(jobs.get(section, [])) for section in ['running'] + sections_to_check)
        
    # In verbose mode, show info about sections we're not processing
    if VERBOSE:
        for key in ['private-batch-queued']:
            if key in jobs and isinstance(jobs[key], list) and len(jobs[key]) > 0:
                logInfo(f"Found {len(jobs[key])} jobs in '{key}' section (not processed)")
        
        # Debug: check what's in sections we are processing
        for key in ['queued', 'others', 'private-batch-running']:
            if key in jobs and isinstance(jobs[key], list) and len(jobs[key]) > 0:
                for item in jobs[key]:
                    name, status = guessFields(item)
                    logInfo(f"{key.capitalize()} job: '{name}' with status: '{status}'")
    
    # Fallback to items if it exists
    if not jobItems and 'items' in jobs:
        jobItems = jobs['items']
        activeCount = len(jobItems)
else:
    jobItems = []
    activeCount = 0

# Only collect models from running jobs as "live" - but be more selective
for it in jobItems:
    name, status = guessFields(it)
    
    # Debug: show what we're actually parsing
    if VERBOSE:
        logInfo(f"Job item keys: {list(it.keys())}")
        logInfo(f"Parsed name: '{name}', status: '{status}'")
    
    # Include both running, starting, and queued jobs
    if status.lower() in {"live", "running", "loaded", "starting", "queued"}:
        displayStatus = status if status else "Running"  # Default to Running for items in running array
        if VERBOSE:
            print(f"{formatStatus(displayStatus):20}  {name or 'Unknown Job'}")

        # Collect model names for summary, handle comma-separated models
        if name and name != 'Unknown Job':
            if ',' in name:
                # Split comma-separated models
                models = [m.strip() for m in name.split(',')]
                if status.lower() == "starting":
                    startingModels.extend(models)
                elif status.lower() == "queued":
                    queuedModels.extend(models)
                else:
                    activeModels.extend(models)
            else:
                if status.lower() == "starting":
                    startingModels.append(name)
                elif status.lower() == "queued":
                    queuedModels.append(name)
                else:
                    activeModels.append(name)

if VERBOSE:
    if activeCount == 0:
        print(f"{DIM}  No active jobs found{RESET}")
    else:
        totalJobs = len(activeModels) + len(startingModels) + len(queuedModels)
        jobParts = []
        if len(activeModels) > 0:
            jobParts.append(f"{len(activeModels)} running")
        if len(startingModels) > 0:
            jobParts.append(f"{len(startingModels)} starting")
        if len(queuedModels) > 0:
            jobParts.append(f"{len(queuedModels)} queued")
        logSuccess(f"Found {totalJobs} active jobs ({', '.join(jobParts)})")

if VERBOSE:
    print()
    logInfo("Analyzing endpoint configuration data...")
    print(f"\n{BOLD}=== ENDPOINT CONFIGURATION INFO ==={RESET}")
    
    if isinstance(endpoints, dict) and 'clusters' in endpoints:
        for clusterName, clusterInfo in endpoints['clusters'].items():
            if 'frameworks' in clusterInfo:
                print(f"\n{CYAN}Cluster: {clusterName}{RESET}")
                for frameworkName, frameworkInfo in clusterInfo['frameworks'].items():
                    modelCount = len(frameworkInfo.get('models', []))
                    endpoints_data = frameworkInfo.get('endpoints', {})
                    endpoint_types = list(endpoints_data.keys()) if isinstance(endpoints_data, dict) else []
                    print(f"  {frameworkName}: {modelCount} models, endpoints: {', '.join(endpoint_types)}")
    else:
        print(f"{DIM}  No cluster configuration found{RESET}")
        
    logInfo("Note: This shows configuration only, not live status")

# Final summary with all models listed (active in green, inactive in default)
print(f"\n{BOLD}=== SUMMARY ==={RESET}")
print(f"📊 Available models (configured): {GREEN}{len(uniqueModels)}{RESET}")
totalActive = len(set(activeModels)) + len(set(startingModels)) + len(set(queuedModels))
print(f"🚀 Active models: {GREEN}{totalActive}{RESET}")

# List all models with active ones highlighted
if uniqueModels:
    print(f"\n{BOLD}{'Live Models:' if args.live_only else 'All Models:'}{RESET}")
    uniqueActiveModels = set(activeModels) if activeModels else set()
    uniqueStartingModels = set(startingModels) if startingModels else set()
    sortedModelNames = sorted(uniqueModels.keys())

    uniqueQueuedModels = set(queuedModels) if queuedModels else set()

    for modelName in sortedModelNames:
        if modelName in uniqueActiveModels:
            print(f"  {GREEN}● {modelName}{RESET}")
        elif modelName in uniqueStartingModels:
            print(f"  {YELLOW}● {modelName}{RESET}")
        elif modelName in uniqueQueuedModels:
            print(f"  {BLUE}● {modelName} (Queued){RESET}")
        elif not args.live_only:
            print(f"  {RED}● {modelName} (Stopped){RESET}")
    
    totalLive = len(uniqueActiveModels) + len(uniqueStartingModels) + len(uniqueQueuedModels)
    if totalLive > 0:
        runningCount = len(uniqueActiveModels)
        startingCount = len(uniqueStartingModels)
        queuedCount = len(uniqueQueuedModels)

        statusParts = []
        if runningCount > 0:
            statusParts.append(f"{GREEN}{runningCount} running{RESET}")
        if startingCount > 0:
            statusParts.append(f"{YELLOW}{startingCount} starting{RESET}")
        if queuedCount > 0:
            statusParts.append(f"{BLUE}{queuedCount} queued{RESET}")

        if len(statusParts) > 1:
            print(f"\n  {' + '.join(statusParts)} = {totalLive} models active / {len(uniqueModels)} total configured")
        else:
            print(f"\n  {statusParts[0]} / {len(uniqueModels)} total configured")

if VERBOSE:
    print(f"\n{YELLOW}ℹ{RESET} {BOLD}Technical Note:{RESET}")
    runningCount = len(set(activeModels)) if activeModels else 0
    startingCount = len(set(startingModels)) if startingModels else 0
    queuedCount = len(set(queuedModels)) if queuedModels else 0
    print(f"  • /jobs API shows live models ({runningCount} running, {startingCount} starting, {queuedCount} queued)")
    print(f"  • /list-endpoints API shows configured endpoints (not live status)")
    print(f"  • Live status comes from actual job execution, not endpoint configuration")

print(f"\n{DIM}Analysis completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")