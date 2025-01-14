import requests
import time
from datetime import datetime
import os

from dotenv import load_dotenv

load_dotenv()

def parse_iso8601_with_ms(timestamp):
    """
    Parse ISO 8601 timestamps with millisecond precision.
    """
    try:
        return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")

def get_druid_latency(druid_query_endpoint, datasource, retries=3, retry_delay=5):
    """
    Queries Druid to calculate end-to-end latency with retry mechanism.
    
    Args:
        druid_query_endpoint (str): Druid broker/router endpoint.
        datasource (str): Druid datasource name.
        retries (int): Number of retry attempts in case of failure.
        retry_delay (int): Delay between retries in seconds.

    Returns:
        float: Latency in milliseconds, or None if the query ultimately fails.
    """
    query = {
        "query": f"""
        SELECT MAX("__time") AS latest_kafka_timestamp, CURRENT_TIMESTAMP AS query_time
        FROM "{datasource}"
        """
    }
    attempts = 0
    while attempts <= retries:
        try:
            response = requests.post(f"{druid_query_endpoint}", json=query, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result:
                latest_timestamp = result[0]['latest_kafka_timestamp']
                query_time = result[0]['query_time']

                # Parse timestamps
                latest_time_obj = parse_iso8601_with_ms(latest_timestamp)
                query_time_obj = parse_iso8601_with_ms(query_time)
                
                # Calculate latency in milliseconds
                latency = (query_time_obj - latest_time_obj).total_seconds() * 1000
                return latency
        except Exception as e:
            print(f"Attempt {attempts + 1}/{retries} failed: {e} (Broker still not ready)")
            if attempts < retries:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            attempts += 1

    return None

def monitor_latency(druid_query_endpoint, datasource, time_error, trial_count):
    """
    Monitors Druid latency, printing the latency for each data ingestion
    
    Args:
        druid_query_endpoint (str): Druid broker/router endpoint.
        datasource (str): Druid datasource name.
        time_error (int): Time interval in milliseconds to check for latency.
    """
    best_latency = None
    previous_latency = None
    latest_latency = None
    cumulative_latency = 0  # Cumulative sum of latencies
    total_trials = 0

    print(f"Monitoring latency for datasource '{datasource}' every {time_error} ms...")

    # Skip the first trial
    first_trial_skipped = False
    
    while True:
        latency = get_druid_latency(druid_query_endpoint, datasource)
        
        if latency is not None:

            if not first_trial_skipped:
                first_trial_skipped = True
                continue
            # Update latest latency and check conditions
            previous_latency = latest_latency
            latest_latency = latency
            
            # Compare latest and previous latency, handling None case for previous_latency
            if previous_latency is None or latest_latency < previous_latency:
                best_latency = latest_latency
            
                print(f"Latency: {best_latency} ms", flush=True)

                # Update cumulative latency and trial count
                cumulative_latency += latency
                total_trials += 1
                
                # Print the average latency every `trial_count` trials
                if total_trials % trial_count == 0:
                    avg_latency = cumulative_latency / total_trials
                    print(f"Average Latency after {total_trials} trials: {avg_latency:.2f} ms")
            #print(f"Debug print: Best Latency = {best_latency} ms, latest_latency = {latest_latency} ms, previous_latency = {previous_latency} ms")

        # Wait for the specified time_error before the next check
        time.sleep(time_error / 1000)

if __name__ == "__main__":
    # Druid host, datasource, and time error in milliseconds
    druid_query_endpoint = os.getenv('DRUID_QUERY_ENDPOINT')
    datasource = os.getenv('DATASOURCE')
    time_error = int(os.getenv('TIME_ERROR'))
    trial_count = int(os.getenv('TRIAL_COUNT', 25))

    monitor_latency(druid_query_endpoint, datasource, time_error, trial_count)
