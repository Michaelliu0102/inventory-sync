#!/usr/bin/env python3
"""
NetSuite vs Excel 库存自动对比系统
主入口脚本

用法:
    python main.py                  # 正常运行，对比并推送到飞书
    python main.py --dry-run        # 仅对比并输出结果，不推送飞书
    python main.py --china-only     # 仅对比中国仓库
    python main.py --italy-only     # 仅对比意大利仓库
"""

import argparse
import logging
import sys
from pathlib import Path

import yaml

import netsuite_client
import sheets_reader
import wps_reader
import comparator
import feishu_notifier

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> dict:
    """加载配置文件"""
    p = Path(config_path)
    if not p.exists():
        logger.error(f"Config file not found: {config_path}")
        logger.error("Please copy config.example.yaml to config.yaml and fill in your values")
        sys.exit(1)

    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run(config: dict, dry_run: bool = False, china_only: bool = False, italy_only: bool = False):
    """执行库存对比"""

    # 1. 获取 NetSuite 库存
    logger.info("=" * 60)
    logger.info("Fetching NetSuite inventory...")
    ns_inventory = netsuite_client.fetch_inventory(config)

    china_loc = config["netsuite"]["locations"]["china"]
    italy_loc = config["netsuite"]["locations"]["italy"]

    results = []

    # 2. 对比意大利库存 (Google Sheets)
    if not china_only:
        logger.info("-" * 60)
        logger.info("Comparing Italy inventory (Google Sheets)...")
        italy_excel = sheets_reader.read_inventory(config)
        italy_result = comparator.compare(
            netsuite_inv=ns_inventory.get(italy_loc, {}),
            excel_inv=italy_excel,
            location=italy_loc,
        )
        results.append(italy_result)

    # 3. 对比中国库存 (WPS Docs)
    if not italy_only:
        logger.info("-" * 60)
        logger.info("Comparing China inventory (WPS Docs)...")
        china_excel = wps_reader.read_inventory(config)
        china_result = comparator.compare(
            netsuite_inv=ns_inventory.get(china_loc, {}),
            excel_inv=china_excel,
            location=china_loc,
        )
        results.append(china_result)

    # 4. 输出结果
    logger.info("=" * 60)
    logger.info("COMPARISON RESULTS:")
    for r in results:
        print()
        print(r.summary)
        if r.has_diffs:
            print(f"  差异详情:")
            
            # 先按类型排个序，把数字对不上的情况放最前面
            sorted_diffs = sorted(r.diffs, key=lambda x: {"mismatch": 0, "excel_only": 1, "netsuite_only": 2}[x.diff_type])
            
            for d in sorted_diffs:
                def fmt_qty(q):
                    if q is None: return "N/A"
                    return f"{q:.2f}".rstrip('0').rstrip('.')

                ns_str = fmt_qty(d.netsuite_qty)
                ex_str = fmt_qty(d.excel_qty)
                diff_label = {"mismatch": "数量不一致", "netsuite_only": "只在NS存在", "excel_only": "只在Excel存在"}[d.diff_type]
                print(f"    [{diff_label}] {d.name}: NS={ns_str}, Excel={ex_str}  (Delta={fmt_qty(d.difference)})")

    # 5. 导出为本地 Excel 报告
    try:
        import datetime
        from openpyxl import Workbook

        date_str = datetime.datetime.now().strftime("%Y%m%d")
        
        # 用不同后缀标识文件
        file_suffix = ""
        if italy_only and not china_only:
            file_suffix = "_Italy"
        elif china_only and not italy_only:
            file_suffix = "_China"
            
        report_filename = f"inventory_diff{file_suffix}_{date_str}.xlsx"
        
        wb = Workbook()
        ws = wb.active
        
        # 表格名字和表头统一设为中英双语或纯英文，以适应意大利主管查看
        ws.title = "Diff Report"
        ws.append(["Location", "Status", "SKU", "NS Qty", "Excel Qty", "Delta(NS-Excel)"])
        
        has_data = False
        for r in results:
            if not r.has_diffs:
                continue
                
            sorted_diffs = sorted(r.diffs, key=lambda x: {"mismatch": 0, "excel_only": 1, "netsuite_only": 2}[x.diff_type])
            for d in sorted_diffs:
                has_data = True
                
                # 判断如果仓库名字里有 Italy，则输出英文状态
                if "Italy" in r.location or "italy" in r.location.lower():
                    diff_label = {"mismatch": "Qty Mismatch", "netsuite_only": "Only in NS", "excel_only": "Only in Excel"}[d.diff_type]
                else:
                    diff_label = {"mismatch": "数量不一致", "netsuite_only": "只在NS存在", "excel_only": "只在Excel存在"}[d.diff_type]
                
                ws.append([
                    r.location,
                    diff_label,
                    d.name,
                    d.netsuite_qty if d.netsuite_qty is not None else "N/A",
                    d.excel_qty if d.excel_qty is not None else "N/A",
                    d.difference
                ])
                
        if has_data:
            ws.column_dimensions['A'].width = 18
            ws.column_dimensions['B'].width = 15
            ws.column_dimensions['C'].width = 25
            wb.save(report_filename)
            logger.info(f"💾 本地差异报告已保存至: {report_filename}")
        else:
            logger.info("🎉 没有任何差异，无需生成 Excel 报告文件。")
            
    except Exception as e:
        logger.error(f"生成本地 Excel 报告失败: {e}")

    # 6. 推送到飞书
    if dry_run:
        logger.info("Dry-run mode: skipping Feishu notification")
    else:
        webhook_url = config["feishu"]["webhook_url"]
        feishu_notifier.send_results(webhook_url, results)

    logger.info("Done!")
    return results


def main():
    parser = argparse.ArgumentParser(description="NetSuite vs Excel 库存对比")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--dry-run", action="store_true", help="仅对比，不推送飞书")
    parser.add_argument("--china-only", action="store_true", help="仅对比中国仓库")
    parser.add_argument("--italy-only", action="store_true", help="仅对比意大利仓库")
    args = parser.parse_args()

    config = load_config(args.config)
    run(config, dry_run=args.dry_run, china_only=args.china_only, italy_only=args.italy_only)


if __name__ == "__main__":
    main()
