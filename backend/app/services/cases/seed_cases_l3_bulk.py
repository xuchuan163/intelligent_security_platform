"""Phase 5 L3-B.6 bulk accident case seeds (AC-MVP-051 .. 200)."""

from __future__ import annotations

from typing import Any

# Synthetic, desensitized templates cycled to reach the L3 gate (200 active cases).
_BULK_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "accident_type": "高处坠落",
        "severity": "一般事故",
        "project_type": "housing",
        "operation_scene": "主体结构临边作业",
        "direct_cause": "临边防护缺失，作业人员未正确使用安全带。",
        "indirect_cause": "班前交底不到位，现场巡检未及时发现防护缺口。",
        "warning_indicators": [
            {"metric_code": "HAZARD_OVERDUE_COUNT", "value": 2},
            {"metric_code": "WORKER_VIOLATION_30D", "value": 1},
        ],
        "tags": ["高处作业", "临边防护", "班前教育"],
    },
    {
        "accident_type": "物体打击",
        "severity": "险情",
        "project_type": "housing",
        "operation_scene": "塔吊吊装作业",
        "direct_cause": "吊装半径内警戒隔离不足，零散材料绑扎不牢。",
        "indirect_cause": "起重吊装旁站不到位，交叉作业协调不足。",
        "warning_indicators": [{"metric_code": "CROSS_OPERATION_COUNT", "value": 3}],
        "tags": ["吊装", "交叉作业", "物体打击"],
    },
    {
        "accident_type": "触电",
        "severity": "近失",
        "project_type": "infrastructure",
        "operation_scene": "临时用电检修",
        "direct_cause": "配电箱接地保护失效，检修前未验电。",
        "indirect_cause": "临电巡检记录不完整，电工复核机制不足。",
        "warning_indicators": [{"metric_code": "TEMP_ELECTRICITY_HAZARD_COUNT", "value": 1}],
        "tags": ["临时用电", "触电", "特种作业"],
    },
    {
        "accident_type": "机械伤害",
        "severity": "一般事故",
        "project_type": "infrastructure",
        "operation_scene": "钢筋加工区作业",
        "direct_cause": "钢筋加工设备防护罩缺失，操作人员手部进入危险区域。",
        "indirect_cause": "设备点检流于形式，作业区安全隔离不足。",
        "warning_indicators": [{"metric_code": "EQUIPMENT_ABNORMAL_COUNT", "value": 1}],
        "tags": ["机械伤害", "设备点检", "防护"],
    },
    {
        "accident_type": "坍塌",
        "severity": "一般事故",
        "project_type": "municipal",
        "operation_scene": "深基坑支护区",
        "direct_cause": "支护变形监测滞后，局部土体失稳引发坍塌险情。",
        "indirect_cause": "专项方案复核不足，雨季施工应对不到位。",
        "warning_indicators": [{"metric_code": "MAJOR_HAZARD_OVERDUE_COUNT", "value": 1}],
        "tags": ["坍塌", "专项方案", "雨季施工"],
    },
    {
        "accident_type": "火灾",
        "severity": "险情",
        "project_type": "mep",
        "operation_scene": "动火作业区",
        "direct_cause": "易燃材料堆码靠近动火点，监护人员离岗。",
        "indirect_cause": "动火作业票审批不严，消防器材配置不足。",
        "warning_indicators": [{"metric_code": "HOT_WORK_PERMIT_COUNT", "value": 2}],
        "tags": ["火灾", "易燃材料", "作业票"],
    },
    {
        "accident_type": "起重伤害",
        "severity": "一般事故",
        "project_type": "housing",
        "operation_scene": "装配式构件吊装",
        "direct_cause": "吊索具检验超期仍使用，构件摆动撞击作业人员。",
        "indirect_cause": "分包队伍培训不足，旁站监管缺位。",
        "warning_indicators": [{"metric_code": "RIGGING_INSPECTION_OVERDUE", "value": 1}],
        "tags": ["起重伤害", "吊索具", "分包管理"],
    },
    {
        "accident_type": "夜间施工",
        "severity": "近失",
        "project_type": "municipal",
        "operation_scene": "道路管网夜间抢修",
        "direct_cause": "夜间照明不足，作业人员误入开挖区域。",
        "indirect_cause": "赶工期导致夜间方案交底简化，巡检频次下降。",
        "warning_indicators": [{"metric_code": "NIGHT_WORK_PERMIT_COUNT", "value": 1}],
        "tags": ["夜间施工", "照明", "赶工期"],
    },
    {
        "accident_type": "分包管理失控",
        "severity": "一般事故",
        "project_type": "housing",
        "operation_scene": "多分包交叉区域",
        "direct_cause": "分包队伍未培训即进场，违章操作引发险情升级。",
        "indirect_cause": "分包准入审核不严，总包统一协调机制失效。",
        "warning_indicators": [{"metric_code": "SUBCONTRACTOR_VIOLATION_30D", "value": 4}],
        "tags": ["分包管理", "培训", "违规"],
    },
    {
        "accident_type": "文明施工",
        "severity": "险情",
        "project_type": "municipal",
        "operation_scene": "临街围挡外侧",
        "direct_cause": "围挡基础松动倾倒，砸中市政人行道设施。",
        "indirect_cause": "日常巡检未发现围挡沉降，极端天气应对不足。",
        "warning_indicators": [{"metric_code": "SITE_ENCROACHMENT_RISK", "value": 1}],
        "tags": ["文明施工", "巡检", "大风"],
    },
)

_SCENES: tuple[str, ...] = (
    "地下室底板浇筑",
    "屋面防水施工",
    "钢结构安装",
    "幕墙打胶作业",
    "市政顶管施工",
    "桥梁墩柱施工",
    "隧道盾构区间",
    "机电管线预埋",
    "装饰装修阶段",
    "外脚手架拆除",
)


def build_l3_bulk_seeds(*, start_index: int = 51, count: int = 150) -> list[dict[str, Any]]:
    seeds: list[dict[str, Any]] = []
    for offset in range(count):
        index = start_index + offset
        template = _BULK_TEMPLATES[offset % len(_BULK_TEMPLATES)]
        scene = _SCENES[offset % len(_SCENES)]
        seeds.append(
            {
                "accident_case_id": f"AC-MVP-{index:03d}",
                "tenant_id": "CSCEC",
                "accident_type": template["accident_type"],
                "severity": template["severity"],
                "project_type": template["project_type"],
                "operation_scene": f"{scene}（合成案例 {index:03d}）",
                "direct_cause": template["direct_cause"],
                "indirect_cause": template["indirect_cause"],
                "involved_subjects": {"subjects": ["project", "subcontractor", "worker"]},
                "warning_indicators": list(template["warning_indicators"]),
                "rectification_measures": "按标准整改闭环，组织专项复盘与再培训。",
                "tags": list(template["tags"]),
            }
        )
    return seeds


ACCIDENT_CASE_SEEDS_L3_BULK: list[dict] = build_l3_bulk_seeds()
