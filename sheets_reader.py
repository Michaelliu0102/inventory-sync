"""
Google Sheets 读取器 - 读取意大利库存数据
使用 Service Account 认证
"""

import logging
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def read_inventory(config: dict) -> dict:
    """
    从 Google Sheets 读取库存数据。

    Returns:
        {"DisplayName1": 10, "DisplayName2": 5, ...}
    """
    gs = config["google_sheets"]
    creds_file = gs["credentials_file"]
    spreadsheet_id = gs["spreadsheet_id"]
    sheet_name = gs.get("sheet_name", "")
    name_col = gs.get("name_column", 2)       # 默认 B 列
    qty_col = gs.get("quantity_column", 3)     # 默认 C 列
    header_rows = gs.get("header_rows", 1)

    creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    sheets_api = service.spreadsheets()

    # 获取所有 sheet 的名称
    meta = sheets_api.get(spreadsheetId=spreadsheet_id).execute()
    
    if sheet_name:
        sheets_to_read = [sheet_name]
    else:
        # 留空则读取所有 sheet (Tab)
        sheets_to_read = [s["properties"]["title"] for s in meta.get("sheets", [])]

    inventory = {}

    for s_name in sheets_to_read:
        logger.info(f"Reading Google Sheet tab: {s_name}")
        range_str = f"'{s_name}'"
        
        try:
            result = sheets_api.values().get(
                spreadsheetId=spreadsheet_id,
                range=range_str,
            ).execute()
        except Exception as e:
            logger.error(f"  Failed to read sheet '{s_name}': {e}")
            continue

        rows = result.get("values", [])

        for i, row in enumerate(rows):
            if i < header_rows:
                continue

            # 列号从 1 开始，列表索引从 0 开始
            if len(row) < max(name_col, qty_col):
                continue

            name = str(row[name_col - 1]).strip()
            qty_raw = row[qty_col - 1]

            if not name:
                continue

            try:
                quantity = float(str(qty_raw).replace(",", "").strip())
            except (ValueError, TypeError):
                logger.warning(f"  [{s_name}] Row {i + 1}: cannot parse quantity '{qty_raw}' for '{name}', skipping")
                continue

            inventory[name] = inventory.get(name, 0) + quantity

    logger.info(f"  Google Sheets: {len(inventory)} SKUs loaded in total (from {len(sheets_to_read)} tabs)")
    return inventory
