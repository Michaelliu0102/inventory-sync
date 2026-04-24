"""
库存对比逻辑 - 按 Display Name 精确匹配，比较数量差异
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DiffItem:
    name: str
    netsuite_qty: float | None
    excel_qty: float | None
    diff_type: str  # "mismatch" | "netsuite_only" | "excel_only"

    @property
    def difference(self) -> float:
        ns = self.netsuite_qty or 0
        ex = self.excel_qty or 0
        return ns - ex


@dataclass
class CompareResult:
    location: str
    diffs: list[DiffItem]
    netsuite_count: int
    excel_count: int

    @property
    def has_diffs(self) -> bool:
        return len(self.diffs) > 0

    @property
    def summary(self) -> str:
        if not self.has_diffs:
            return f"✅ {self.location}: 完全一致 ({self.netsuite_count} SKUs)"

        mismatches = [d for d in self.diffs if d.diff_type == "mismatch"]
        ns_only = [d for d in self.diffs if d.diff_type == "netsuite_only"]
        ex_only = [d for d in self.diffs if d.diff_type == "excel_only"]

        parts = [f"⚠️ {self.location}: {len(self.diffs)} 项差异"]
        if mismatches:
            parts.append(f"  数量不一致: {len(mismatches)}")
        if ns_only:
            parts.append(f"  仅NetSuite有: {len(ns_only)}")
        if ex_only:
            parts.append(f"  仅Excel有: {len(ex_only)}")
        return "\n".join(parts)


def compare(
    netsuite_inv: dict[str, float],
    excel_inv: dict[str, float],
    location: str,
) -> CompareResult:
    """
    对比 NetSuite 与 Excel 的库存。

    Args:
        netsuite_inv: {display_name: quantity}
        excel_inv: {display_name: quantity}
        location: 仓库名称

    Returns:
        CompareResult
    """
    diffs = []
    
    # 将字典的 key 全部转为大写，以实现大小写不敏感匹配 (比如 J01 和 j01 会被判定为同一个 SKU)
    ns_inv_upper = {k.upper(): v for k, v in netsuite_inv.items()}
    ex_inv_upper = {k.upper(): v for k, v in excel_inv.items()}
    
    # 保留它原本的名字用于最终的 Excel 报告显示（优先保留 NetSuite 里的原来写法）
    original_names = {}
    for k in excel_inv.keys():
        original_names[k.upper()] = k
    for k in netsuite_inv.keys():
        original_names[k.upper()] = k

    all_names_upper = set(ns_inv_upper.keys()) | set(ex_inv_upper.keys())

    for upper_name in sorted(all_names_upper):
        ns_qty = ns_inv_upper.get(upper_name)
        ex_qty = ex_inv_upper.get(upper_name)
        disp_name = original_names[upper_name]

        if ns_qty is not None and ex_qty is not None:
            if abs(ns_qty - ex_qty) >= 1.0:  # 重点容错：差异小于1（即只有小数部分不同）时不报错
                diffs.append(DiffItem(disp_name, ns_qty, ex_qty, "mismatch"))
        elif ns_qty is not None:
            if abs(ns_qty) >= 1.0:  # 仅当 NetSuite 中确实有 1 件或以上实物库存时，才报差异
                diffs.append(DiffItem(disp_name, ns_qty, None, "netsuite_only"))
        else:
            if abs(ex_qty) >= 1.0:  # 同理，如果 Excel 里只有零点几的边角料差额，也忽略
                diffs.append(DiffItem(disp_name, None, ex_qty, "excel_only"))

    result = CompareResult(
        location=location,
        diffs=diffs,
        netsuite_count=len(netsuite_inv),
        excel_count=len(excel_inv),
    )

    logger.info(result.summary)
    return result
