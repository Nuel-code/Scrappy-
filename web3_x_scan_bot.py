import os
import requests
import time

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
ACTOR_ID = "igolaizola~x-twitter-scraper-ppe"   # This is the ONLY correct form

def run_actor():
    run_url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs?token={APIFY_TOKEN}"
    payload = {
        "queries": [
            {
                "q": "crypto",
                "mode": "top"
            }
        ],
        "includeTweetReplies": False,
        "maxTweets": 50
    }

    response = requests.post(run_url, json=payload)
    response.raise_for_status()

    data = response.json()
    return data["data"]["id"]

def wait_for_run(run_id):
    status_url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs/{run_id}?token={APIFY_TOKEN}"

    while True:
        response = requests.get(status_url)
        response.raise_for_status()
        data = response.json()

        status = data["data"]["status"]
        print("Status:", status)

        if status in ["SUCCEEDED", "FAILED", "ABORTED"]:
            return data["data"]
        
        time.sleep(3)

def fetch_dataset(dataset_id):
    dataset_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_TOKEN}"
    
    response = requests.get(dataset_url)
    response.raise_for_status()
    return response.json()

def main():
    print("Running Apify actor...")
    run_id = run_actor()

    print("Waiting for actor to finish...")
    run_data = wait_for_run(run_id)

    if "defaultDatasetId" not in run_data:
        print("No dataset returned.")
        return

    dataset_id = run_data["defaultDatasetId"]
    print("Fetching dataset:", dataset_id)

    results = fetch_dataset(dataset_id)
    print("Results:", results)

if __name__ == "__main__":
    main()
