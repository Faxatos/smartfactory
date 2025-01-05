import requests
import time
import os

from dotenv import load_dotenv

load_dotenv()

def get_druid_latency(druid_query_endpoint, datasource):
    """
    Queries Druid to calculate end-to-end latency.
    
    Args:
        druid_query_endpoint (str): Druid broker/router endpoint.
        datasource (str): Druid datasource name.

    Returns:
        float: Latency in seconds, or None if the query fails.
    """
    query = {
        "query": f"""
        SELECT MAX("__time") AS latest_kafka_timestamp, CURRENT_TIMESTAMP AS query_time
        FROM "{datasource}"
        """
    }
    try:
        response = requests.post(f"{druid_query_endpoint}", json=query)
        response.raise_for_status()
        result = response.json()
        
        if result:
            latest_timestamp = result[0]['latest_kafka_timestamp']
            query_time = result[0]['query_time']
            
            # Convert timestamps to epoch times
            latest_timestamp_epoch = time.mktime(time.strptime(latest_timestamp, "%Y-%m-%dT%H:%M:%S.%fZ"))
            query_time_epoch = time.mktime(time.strptime(query_time, "%Y-%m-%dT%H:%M:%S.%fZ"))
            
            # Calculate latency in seconds
            return query_time_epoch - latest_timestamp_epoch
    except Exception as e:
        print(f"Error querying Druid: {e}")
    
    return None

def monitor_latency(druid_query_endpoint, datasource, time_error):
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

    print(f"Monitoring latency for datasource '{datasource}' every {time_error} ms...")
    
    while True:
        latency = get_druid_latency(druid_query_endpoint, datasource)
        
        if latency is not None:
            # Update latest latency and check conditions
            previous_latency = latest_latency
            latest_latency = latency
            
            # Compare latest and previous latency, handling None case for previous_latency
            if previous_latency is None or latest_latency < previous_latency:
                best_latency = latest_latency
            
                print(f"Best Latency: {best_latency:.3f} seconds")
        
        # Wait for the specified time_error before the next check
        time.sleep(time_error / 1000)

if __name__ == "__main__":
    # Druid host, datasource, and time error in milliseconds
    druid_query_endpoint = os.getenv('DRUID_QUERY_ENDPOINT')
    datasource = os.getenv('DATASOURCE')
    time_error = int(os.getenv('TIME_ERROR'))

    monitor_latency(druid_query_endpoint, datasource, time_error)
