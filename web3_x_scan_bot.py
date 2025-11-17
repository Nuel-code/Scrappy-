import os
import requests
import json
from datetime import datetime

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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

# Quick helper for sending Telegram messages
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    })
    return resp.ok

# Query Apify's X (Twitter) actor
def apify_twitter_search(keywords, since_date, max_results=600):
    actor_id = "apify/twitter-scraper"
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
    # Run the actor task
    start_url = f"https://api.apify.com/v2/acts/{actor_id}/runs"
    run_resp = requests.post(start_url, json={"input": data}, headers=headers)
    run_info = run_resp.json()
    run_id = run_info["id"]
    # Wait for run completion
    status_url = f"https://api.apify.com/v2/acts/{actor_id}/runs/{run_id}"
    while True:
        resp = requests.get(status_url, headers=headers)
        status = resp.json()["status"]
        if status in ["SUCCEEDED", "FAILED", "TIMED-OUT"]:
            break
        import time; time.sleep(10)
    if status != "SUCCEEDED":
        raise Exception("Apify actor failed.")
    # Fetch dataset
    dataset_id = resp.json()["defaultDatasetId"]
    dataset_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?clean=true"
    result_resp = requests.get(dataset_url, headers=headers)
    tweets = result_resp.json()
    return tweets

def is_project_tweet(tweet):
    # Simple filter: projects usually have a non-personal username, description
    user = tweet.get('user', {})
    username = user.get('screenName', '')
    description = user.get('description', '').lower()
    followers = user.get('followersCount', 0)
    # Filter out low-follower and non-org/account presentations
    personal_signals = [
        "developer",
        "enthusiast",
        "me",
        "student",
        "investor",
        "trader",
        "father",
        "mother",
        "personal",
        "author"
    ]
  
    if any(ps in description for ps in personal_signals):
        return False
    # Must mention a launch/creation
    text = tweet.get("fullText", "").lower()
    if "launch" in text or "introducing" in text or "we are proud to announce" in text or "now live" in text:
        return True
    return False

def format_tweet_summary(tweet):
    url = f"https://x.com/{tweet['user']['screenName']}/status/{tweet['id']}"
    project_name = tweet['user'].get('name', '')
    followers = tweet['user']['followersCount']
    description = tweet['user'].get('description', '')
    created_at = tweet['createdAt']
    summary = f"*{project_name}* ({followers} followers)\n[{url}]({url})\n_About:_ {description}\n_Tweeted_: {created_at}\n"
    return summary

def main():
    print("Starting Web3 X scan...")
    try:
        tweets = apify_twitter_search(KEYWORDS, SINCE_DATE)
        print(f"Total found: {len(tweets)}")
        # Filter project tweets
        filtered = [t for t in tweets if is_project_tweet(t)]
        print(f"Filtered to projects: {len(filtered)}")
        # Send results in batches to Telegram (to prevent message overflow)
        batch_size = 15
        for i in range(0, min(600, len(filtered)), batch_size):
            batch = filtered[i:i+batch_size]
            msg = "\n\n".join([format_tweet_summary(t) for t in batch])
            sent = send_telegram_message(msg[:4096])
            print(f"Sent batch {i//batch_size + 1}: {sent}")
    except Exception as ex:
        print(f"Error: {ex}")
        send_telegram_message(f"Web3 X scan failed: {ex}")

if __name__ == "__main__":
    main()
