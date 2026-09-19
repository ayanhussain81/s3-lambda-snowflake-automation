import os
import json
import boto3
import requests
from datetime import datetime, timezone
from snowflake_provider import Provider


def s3_client(json_data, timestamp):
    '''
    Dumping response to S3 as json file.
    '''
    dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
    year = dt.strftime('%Y')
    month = dt.strftime('%m')
    day = dt.strftime('%d')
    hour = dt.strftime('%H')

    s3_key = f"exchange_rates/{year}/{month}/{day}/exchange-rates-{hour}.json"
    s3_bucket_name = os.environ.get('s3_bucket_name')

    s3 = boto3.client("s3")
    s3.put_object(Bucket=s3_bucket_name, Key=s3_key, Body=json_data)


def load_to_snowflake(json_data, timestamp):
    '''
    Calling stored procedure to load data into Snowflake.
    '''
    provider = Provider(
        region_name=os.environ.get('region_name'),
        aws_db_creds_secret_id='db/currency-exchange-rate',
        aws_db_creds_secret_value='fusion_snowflake',
        snowflake_db=os.environ.get('snowflake_db'),
        snowflake_role=os.environ.get('snowflake_role'),
        snowflake_wh=os.environ.get('snowflake_wh'),
    )

    sql = "CALL CURRENCY.SP_EXCHANGE_RATE_LOADING(%s, %s)"
    provider.exe_query(sql, (json_data, timestamp))


def fetch_exchange_rates():
    '''
    1. Getting data from API.
    2. Dumping raw JSON into S3.
    3. Loading data into Snowflake.
    '''
    base_url = os.environ.get("oer_base_url")
    app_id = os.environ.get("oer_app_id")
    base_currency = os.environ.get("oer_base_currency", "USD")

    url = f"{base_url}?app_id={app_id}&base={base_currency}"

    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        timestamp = datetime.fromtimestamp(data['timestamp'], tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        json_data = json.dumps(data)

        s3_client(json_data, timestamp)
        load_to_snowflake(json_data, timestamp)
    else:
        raise Exception(f"API request failed with status code {response.status_code}")


def lambda_handler(event, context):
    fetch_exchange_rates()

    return {'statusCode': 200}