import os
import requests
import json
from datetime import datetime

# --- Configuration ---
# Load secrets from environment variables
APIFY_TOKEN = os.getenv("APIFY_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Keywords and Date Filter
KEYWORDS = [
    "defi protocol",
    "dex aggregator",
    "web3 project",
    "launch",
    "IDO",
    "defi platform",
    "dex platform",
    "blockchain protocol",
    "crypto dapp"
]
SINCE_DATE = "2025-07-01"  # YYYY-MM-DD
ACTOR_ID = "apify/twitter-scraper"

# --- Helper Functions ---

def send_telegram_message(text):
    """Sends a message to a Telegram chat."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram tokens not set. Cannot send message.")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # Ensure text is not too long for Telegram (4096 characters max)
    resp = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text[:4096], 
        "parse_mode": "Markdown"
    })
    
    if resp.status_code != 200:
        print(f"Failed to send Telegram message. Status: {resp.status_code}, Response: {resp.text}")
        return False
        
    return True

def apify_twitter_search(keywords, since_date, max_results=600):
    """Queries Apify's X (Twitter) actor with robust error checking."""
    print(f"Starting Apify Actor run for {len(keywords)} keywords...")
    
    search_queries = [f'"{kw}" since:{since_date}' for kw in keywords]
    data = {
        "queries": search_queries,
        "maxTweets": max_results,
        "addUserInfo": True,
        "includeReplies": False,
        "includeRetweets": False,
        "tweetsLanguage": "en"
    }
    headers = {"Authorization": f"Bearer {APIFY_TOKEN}"}
    
    # 1. Run the actor task
    start_url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs"
    run_resp = requests.post(start_url, json={"input": data}, headers=headers)
    
    # **IMPROVEMENT 1: Check HTTP Status Code for successful run start**
    if run_resp.status_code not in [201, 200]:
        error_msg = f"Failed to start Apify Actor ({ACTOR_ID}). Status: {run_resp.status_code}. Response: {run_resp.text}"
        raise Exception(error_msg)
        
    run_info = run_resp.json()
    
    # **IMPROVEMENT 2: Gracefully check for 'id' key existence**
    run_id = run_info.get("data", {}).get("id")
    if not run_id:
        # Fallback for non-standard response structure
        run_id = run_info.get("id")
        
    if not run_id:
        raise Exception(f"Could not retrieve a valid run ID from Apify response: {run_info}")

    print(f"Actor run started successfully. Run ID: {run_id}")
    
    # 2. Wait for run completion
    status_url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs/{run_id}"
    while True:
        resp = requests.get(status_url, headers=headers)
        
        # Check status of the status check request
        if resp.status_code != 200:
            raise Exception(f"Failed to check Actor status. Status: {resp.status_code}. Response: {resp.text}")
            
        status = resp.json().get("data", {}).get("status")
        if status in ["SUCCEEDED", "FAILED", "TIMED-OUT"]:
            break
        import time; time.sleep(10)
        
    if status != "SUCCEEDED":
        raise Exception(f"Apify actor run failed or timed out. Final status: {status}")
        
    # 3. Fetch dataset
    dataset_id = resp.json().get("data", {}).get("defaultDatasetId")
    if not dataset_id:
        raise Exception(f"Could not retrieve defaultDatasetId after run succeeded.")
        
    dataset_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?clean=true"
    result_resp = requests.get(dataset_url, headers=headers)
    
    if result_resp.status_code != 200:
        raise Exception(f"Failed to fetch dataset items. Status: {result_resp.status_code}")
        
    tweets = result_resp.json()
    return tweets

# --- Filtering and Formatting ---

def is_project_tweet(tweet):
    """Applies simple logic to filter for project launch announcements."""
    user = tweet.get('user', {})
    description = user.get('description', '').lower()
    
    # List of signals often found in personal/non-organizational accounts
    personal_signals = [
        "developer", "enthusiast", "me", "student", "investor", 
        "trader", "father", "mother", "personal", "author", "trader"
    ]
  
    if any(ps in description for ps in personal_signals):
        return False
        
    # Must mention a launch/creation/announcement
    text = tweet.get("fullText", "").lower()
    if any(phrase in text for phrase in ["launch", "introducing", "we are proud to announce", "now live", "we present", "created"]):
        return True
        
    return False

def format_tweet_summary(tweet):
    """Formats a single tweet into a summary suitable for Telegram Markdown."""
    url = f"https://x.com/{tweet['user']['screenName']}/status/{tweet['id']}"
    project_name = tweet['user'].get('name', 'N/A')
    followers = tweet['user'].get('followersCount', 0)
    description = tweet['user'].get('description', 'No description provided.')
    # Format date more cleanly
    created_at = datetime.strptime(tweet['createdAt'][:19], '%Y-%m-%dT%H:%M:%S').strftime('%b %d, %Y')
    
    summary = (
        f"**{project_name}** ({followers:,} followers)\n"
        f"[[View Tweet]]({url})\n"
        f"_About:_ {description}\n"
        f"_Tweeted_: {created_at}"
    )
    return summary

# --- Main Logic ---

def main():
    """Main function to run the scanner and send results."""
    print("Starting Web3 X scan...")
    
    # **IMPROVEMENT 3: Environment Variable Check**
    if not APIFY_TOKEN:
        print("FATAL: APIFY_TOKEN environment variable is not set. Exiting.")
        return
    
    try:
        tweets = apify_twitter_search(KEYWORDS, SINCE_DATE)
        print(f"Total tweets found: {len(tweets)}")
        
        # Filter project tweets
        filtered = [t for t in tweets if is_project_tweet(t)]
        print(f"Filtered to potential projects: {len(filtered)}")
        
        if not filtered:
            send_telegram_message("🤖 **Web3 Scan Results:** No new relevant project announcements found.")
            return

        # Send results in batches to Telegram (max 4096 chars per message)
        batch_size = 5 # Reduced batch size for safer formatting
        
        # Send a header message first
        send_telegram_message(f"🚨 **New Web3 Project Announcements** 🚨\nFound {len(filtered)} potential launches since {SINCE_DATE}.")
        
        for i in range(0, len(filtered), batch_size):
            batch = filtered[i:i+batch_size]
            
            # Join summaries, separating with a clear visual break
            msg = "\n\n---\n\n".join([format_tweet_summary(t) for t in batch])
            
            sent = send_telegram_message(msg)
            print(f"Sent batch {i//batch_size + 1}/{len(filtered)//batch_size + 1}: {sent}")
            
    except Exception as ex:
        # Catch and report any failure
        print(f"FATAL Error: {ex}")
        send_telegram_message(f"❌ **Web3 X Scan Failed!** ❌\nError details: `{ex}`")

if __name__ == "__main__":
    main()
        
