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

    # 在写入新数据前，先清空整张表的历史数据
    _clear_all_records(app_token, table_id, token)

    # 准备写入的数据
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    records_to_insert = []

    for r in results:
        if not r.has_diffs:
            continue
            
        # 根据用户要求，过滤掉意大利的数据，只把中国数据倒进飞书多维表格
        if "italy" in r.location.lower() or "意大利" in r.location:
            continue
            
        for d in r.diffs:
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


def _clear_all_records(app_token: str, table_id: str, token: str):
    """清空整张表的所有数据"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. 循环获取现存所有的记录 ID (因为单页最多只能返回 500)
    record_ids = []
    page_token = ""
    while True:
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
            
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code != 200:
            logger.error(f"无法读取现有表格数据，跳过清理流程: {resp.text}")
            return
            
        data = resp.json().get("data", {})
        items = data.get("items", [])
        record_ids.extend([item["record_id"] for item in items])
        
        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
        
    if not record_ids:
        logger.info("云表格已经是空的，不需要排空清理。")
        return
        
    # 2. 分批猛烈删除旧记录
    delete_url = f"{url}/batch_delete"
    logger.info(f"🧹 开始做大扫除：发现 {len(record_ids)} 条旧数据，开始清理清空...")
    
    for i in range(0, len(record_ids), 500):
        batch = record_ids[i:i+500]
        resp = requests.post(delete_url, headers=headers, json={"records": batch}, timeout=30)
        if resp.status_code != 200:
            logger.error(f"删除失败 (Chunk {i}): {resp.text}")
        else:
            logger.info(f"  扫除完毕批次 {i+1} ~ {i+len(batch)}")
            
    logger.info("✅ 旧数据大扫除完毕！一张干净的白纸准备就绪。")
