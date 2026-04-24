"""
飞书多维表格 (Feishu Bitable) 读取器 - 获取中国区库存数据
"""

import logging
import requests

logger = logging.getLogger(__name__)

def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    resp = requests.post(
        url,
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取飞书 Token 失败: {data}")
    return data["tenant_access_token"]


def read_inventory(config: dict) -> dict:
    """
    从飞书多维表格读取数据
    Returns:
        {"DisplayName1": 10, "DisplayName2": 5, ...}
    """
    feishu_bitable = config.get("feishu_bitable", {})
    
    app_id = feishu_bitable.get("app_id")
    app_secret = feishu_bitable.get("app_secret")
    app_token = feishu_bitable.get("app_token")
    table_id = feishu_bitable.get("table_id")
    sku_field_name = feishu_bitable.get("sku_field_name", "货品")
    qty_field_name = feishu_bitable.get("quantity_field_name", "最新系统库存")

    if not all([app_id, app_secret, app_token, table_id]):
        logger.error("Missing Feishu Bitable configuration!")
        return {}

    logger.info(f"Authenticating with Feishu OpenAPI...")
    token = get_tenant_access_token(app_id, app_secret)

    logger.info(f"Fetching records from Feishu Bitable ({app_token} - {table_id})...")
    
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    inventory = {}
    page_token = None
    
    while True:
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
            
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("code") != 0:
            raise RuntimeError(f"读取飞书多维表格记录失败: {data}")
            
        items = data["data"].get("items", [])
        
        for item in items:
            fields = item.get("fields", {})
            name = fields.get(sku_field_name)
            qty_raw = fields.get(qty_field_name)
            
            if not name:
                continue
                
            name = str(name).strip()
            
            try:
                quantity = float(str(qty_raw).replace(",", "").strip()) if qty_raw is not None else 0
            except (ValueError, TypeError):
                logger.warning(f"  Cannot parse quantity '{qty_raw}' for '{name}', skipping")
                continue
                
            inventory[name] = inventory.get(name, 0) + quantity
            
        page_token = data["data"].get("page_token")
        has_more = data["data"].get("has_more")
        
        if not has_more or not page_token:
            break

    logger.info(f"  Feishu Bitable: {len(inventory)} SKUs loaded")
    return inventory
