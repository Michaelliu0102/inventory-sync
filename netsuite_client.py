"""
NetSuite SuiteQL 客户端 - 通过 REST API 查询库存数据
使用 Token-Based Authentication (OAuth 1.0a)
"""

import logging
from requests_oauthlib import OAuth1Session

logger = logging.getLogger(__name__)

SUITEQL_ENDPOINT = "https://{account_id}.suitetalk.api.netsuite.com/services/rest/query/v1/suiteql"

INVENTORY_QUERY = """
SELECT
    item.displayname AS name,
    SUM(agg.quantityonhand) AS quantity,
    loc.name AS location
FROM aggregateitemlocation agg
    JOIN item ON agg.item = item.id
    JOIN location loc ON agg.location = loc.id
WHERE loc.name IN ('{china_loc}', '{italy_loc}')
GROUP BY item.displayname, loc.name
ORDER BY loc.name, item.displayname
"""


def fetch_inventory(config: dict) -> dict:
    """
    从 NetSuite 获取库存数据，按 location 分组返回。

    Returns:
        {
            "China - Jiaxing": {"DisplayName1": 10, "DisplayName2": 5, ...},
            "Italy - Grandate": {"DisplayName3": 20, ...}
        }
    """
    ns = config["netsuite"]
    account_id = ns["account_id"].replace("_", "-")  # SuiteTalk URL 用连字符
    url = SUITEQL_ENDPOINT.format(account_id=account_id)

    oauth = OAuth1Session(
        client_key=ns["consumer_key"],
        client_secret=ns["consumer_secret"],
        resource_owner_key=ns["token_id"],
        resource_owner_secret=ns["token_secret"],
        realm=ns["account_id"],
        signature_method="HMAC-SHA256",
    )

    china_loc = ns["locations"]["china"]
    italy_loc = ns["locations"]["italy"]
    query = INVENTORY_QUERY.format(china_loc=china_loc, italy_loc=italy_loc)

    result = {china_loc: {}, italy_loc: {}}
    offset = 0
    limit = 1000

    while True:
        logger.info(f"Querying NetSuite inventory (offset={offset})...")
        resp = oauth.post(
            url,
            json={"q": query},
            headers={
                "Content-Type": "application/json",
                "Prefer": "transient",
            },
            params={"limit": limit, "offset": offset},
        )

        if resp.status_code != 200:
            raise RuntimeError(
                f"NetSuite API error {resp.status_code}: {resp.text}"
            )

        data = resp.json()
        items = data.get("items", [])

        if not items:
            break

        for row in items:
            name = (row.get("name") or "").strip()
            location = (row.get("location") or "").strip()
            quantity = float(row.get("quantity") or 0)

            if name and location in result:
                result[location][name] = result[location].get(name, 0) + quantity

        # 检查是否还有更多数据
        if data.get("hasMore", False):
            offset += limit
        else:
            break

    for loc, items in result.items():
        logger.info(f"  {loc}: {len(items)} SKUs loaded from NetSuite")

    return result
