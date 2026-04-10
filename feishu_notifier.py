"""
飞书通知 - 通过自定义机器人 Webhook 推送库存对比结果
"""

import json
import logging
from datetime import datetime

import requests

from comparator import CompareResult

logger = logging.getLogger(__name__)


def send_results(webhook_url: str, results: list[CompareResult]) -> None:
    """
    将对比结果发送到飞书群。

    Args:
        webhook_url: 飞书自定义机器人 Webhook URL
        results: 所有 location 的对比结果
    """
    has_any_diff = any(r.has_diffs for r in results)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 构建飞书富文本消息
    content = _build_message(results, now, has_any_diff)

    payload = {
        "msg_type": "interactive",
        "card": content,
    }

    logger.info("Sending results to Feishu...")
    resp = requests.post(
        webhook_url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )

    if resp.status_code != 200:
        logger.error(f"Feishu webhook error {resp.status_code}: {resp.text}")
        raise RuntimeError(f"Feishu webhook failed: {resp.text}")

    result = resp.json()
    if result.get("code") != 0:
        logger.error(f"Feishu API error: {result}")
        raise RuntimeError(f"Feishu API error: {result.get('msg', 'unknown')}")

    logger.info("Results sent to Feishu successfully!")


def _build_message(results: list[CompareResult], timestamp: str, has_diff: bool) -> dict:
    """构建飞书卡片消息"""
    title = "⚠️ 库存差异报告" if has_diff else "✅ 库存核对通过"

    elements = []

    for r in results:
        # Location 标题
        elements.append({
            "tag": "markdown",
            "content": f"**📍 {r.location}**  |  NetSuite: {r.netsuite_count} SKUs  |  Excel: {r.excel_count} SKUs",
        })

        if not r.has_diffs:
            elements.append({
                "tag": "markdown",
                "content": "✅ 完全一致，无差异",
            })
        else:
            # 差异表格
            lines = _format_diff_table(r.diffs)
            elements.append({
                "tag": "markdown",
                "content": lines,
            })

        elements.append({"tag": "hr"})

    # 时间戳
    elements.append({
        "tag": "note",
        "elements": [
            {"tag": "plain_text", "content": f"对比时间: {timestamp}"},
        ],
    })

    return {
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": "red" if has_diff else "green",
        },
        "elements": elements,
    }


def _format_diff_table(diffs: list) -> str:
    """将差异列表格式化为 Markdown 表格"""
    if not diffs:
        return "无差异"

    lines = ["| 产品名称 | NetSuite | Excel | 差异 | 类型 |",
             "| --- | ---: | ---: | ---: | --- |"]

    for d in diffs[:50]:  # 飞书消息有长度限制，最多显示50条
        ns_str = f"{d.netsuite_qty:.0f}" if d.netsuite_qty is not None else "—"
        ex_str = f"{d.excel_qty:.0f}" if d.excel_qty is not None else "—"
        diff_str = f"{d.difference:+.0f}" if d.netsuite_qty is not None and d.excel_qty is not None else "—"

        type_map = {
            "mismatch": "❌ 数量不一致",
            "netsuite_only": "🔵 仅NetSuite",
            "excel_only": "🟠 仅Excel",
        }
        type_str = type_map.get(d.diff_type, d.diff_type)

        # 截断过长的名称
        name = d.name if len(d.name) <= 30 else d.name[:27] + "..."
        lines.append(f"| {name} | {ns_str} | {ex_str} | {diff_str} | {type_str} |")

    if len(diffs) > 50:
        lines.append(f"\n*...还有 {len(diffs) - 50} 条差异未显示*")

    return "\n".join(lines)
