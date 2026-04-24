"""
将生成的差异报告推送到飞书的多维表格子表中
"""

import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

def write_results_to_bitable(config: dict, results):
    feishu_out = config.get("feishu_bitable_output", {})
    # 共用应用读取的 app_id 和 secret
    app_id = config.get("feishu_bitable", {}).get("app_id")
    app_secret = config.get("feishu_bitable", {}).get("app_secret")
    
    app_token = feishu_out.get("app_token")
    table_id = feishu_out.get("table_id")

    if not app_token or not table_id:
        logger.warning("未配置结果输出云表格，跳过写入。")
        return

    from feishu_reader import get_tenant_access_token
    token = get_tenant_access_token(app_id, app_secret)

    # 准备写入的数据
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    records_to_insert = []

    for r in results:
        if not r.has_diffs:
            continue
            
        for d in r.diffs:
            if "italy" in r.location.lower() or "意大利" in r.location:
                diff_label = {"mismatch": "Qty Mismatch", "netsuite_only": "Only in NS", "excel_only": "Only in Excel"}[d.diff_type]
            else:
                diff_label = {"mismatch": "数量不一致", "netsuite_only": "只在NS存在", "excel_only": "只在Excel存在"}[d.diff_type]

            records_to_insert.append({
                "fields": {
                    "Date": date_str,
                    "Location": r.location,
                    "Status": diff_label,
                    "SKU": d.name,
                    "NS Qty": d.netsuite_qty if d.netsuite_qty is not None else 0,
                    "Excel Qty": d.excel_qty if d.excel_qty is not None else 0,
                    "Delta": d.difference
                }
            })

    if not records_to_insert:
        logger.info("🎉 没有任何差异，无需写入云表格。")
        return

    logger.info(f"Writing {len(records_to_insert)} records to Feishu Bitable output ({table_id})...")
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    # 飞书要求一次最多写入 500 条记录
    batch_size = 500
    for i in range(0, len(records_to_insert), batch_size):
        batch = records_to_insert[i:i + batch_size]
        resp = requests.post(url, headers=headers, json={"records": batch}, timeout=30)
        
        if resp.status_code != 200:
            logger.error(f"写入表格失败 (Chunk {i}): {resp.text}")
        else:
            data = resp.json()
            if data.get("code") != 0:
                logger.error(f"飞书 API 报错 (Chunk {i}): {data}")
            else:
                logger.info(f"  成功写入批次 {i+1} ~ {i+len(batch)}")

    logger.info("成功完成所有云端数据的导入！")
