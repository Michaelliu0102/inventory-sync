import requests, yaml
from feishu_reader import get_tenant_access_token

with open("config.yaml") as f: config = yaml.safe_load(f)
app_id = config["feishu_bitable"]["app_id"]
app_secret = config["feishu_bitable"]["app_secret"]
token = get_tenant_access_token(app_id, app_secret)

app_token = "FtsbbD2wtaky1sskjhGcFpiun2f"
table_id = "tblumX6y0v5EFuiV"
url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"

headers = {"Authorization": f"Bearer {token}"}

resp = requests.get(url, headers=headers)
print("TOTAL RECORDS FETCHED:", resp.json().get('data', {}).get('total'))

post_url = f"{url}/batch_create"
payload = {"records": [{"fields": {"Date": "Test", "Location": "TestLoc", "SKU": "T123"}}]}
post_resp = requests.post(post_url, headers=headers, json=payload)
print("POST RESULT:", post_resp.status_code, post_resp.json())

