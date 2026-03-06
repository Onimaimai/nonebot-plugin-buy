import asyncio
import datetime
import json
from pathlib import Path
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star, register


@register(
    "buy",
    "Onimaimai",
    "群内拼团和活动记录",
    "2.0.0",
    "https://github.com/Onimaimai/nonebot-plugin-buy",
)
class BuyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_dir = Path(__file__).resolve().parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.groupbuy_file = self.data_dir / "groupbuy_data.json"
        self.activity_file = self.data_dir / "activity_data.json"
        self.umo_map_file = self.data_dir / "group_umo_map.json"

        self._ensure_json_file(self.groupbuy_file)
        self._ensure_json_file(self.activity_file)
        self._ensure_json_file(self.umo_map_file)

        self._daily_status_task: asyncio.Task | None = None

    async def terminate(self):
        if self._daily_status_task and not self._daily_status_task.done():
            self._daily_status_task.cancel()
            try:
                await self._daily_status_task
            except asyncio.CancelledError:
                pass

    @filter.on_astrbot_loaded()
    async def _on_astrbot_loaded(self):
        if self._daily_status_task is None or self._daily_status_task.done():
            self._daily_status_task = asyncio.create_task(self._daily_status_loop())
            logger.info("buy: daily status task started")

    @filter.command_group("团购", alias={"groupbuy"})
    def groupbuy(self):
        pass

    @groupbuy.command("help", alias={"帮助", "groupbuyhelp"})
    async def groupbuy_help(self, event: AstrMessageEvent):
        """团购帮助"""
        help_message = (
            "团购 help\n"
            "开团 <名称> <成团金额>\n"
            "拼团 <名称> <参与金额>\n"
            "查团 <名称>\n"
            "复团 <名称>\n"
            "删团 <名称>\n"
            "团购列表\n"
            "已付款 <团购名称> [附带付款截图]\n\n"
            "添加活动 <名称>\n"
            "参加活动 <名称>\n"
            "退出活动 <名称>\n"
            "查询活动 <名称>\n"
            "重置活动 <名称>\n"
            "删除活动 <名称>\n"
            "活动列表"
        )
        yield event.plain_result(help_message)

    @filter.command("开团", alias={"添加团购"})
    async def add_groupbuy(self, event: AstrMessageEvent):
        """开团 <名称> <成团金额>"""
        group_id = self._group_id_or_none(event)
        if not group_id:
            yield event.plain_result("请在群聊中使用该命令。")
            return

        self._record_group_umo(group_id, event.unified_msg_origin)
        args = self._extract_args(event, {"开团", "添加团购"}).split()
        if len(args) != 2:
            yield event.plain_result("请输入正确的格式：开团 <名称> <成团金额>")
            return

        project_name = args[0]
        try:
            target_amount = float(args[1])
        except ValueError:
            yield event.plain_result("成团金额必须是数字。")
            return

        data = self._load_json(self.groupbuy_file)
        group_data = data.setdefault(group_id, {})

        if project_name in group_data:
            yield event.plain_result(f"团购 '{project_name}' 已存在！")
            return

        group_data[project_name] = {
            "target_amount": target_amount,
            "participants": {},
            "total_amount": 0,
            "is_completed": False,
        }
        self._save_json(self.groupbuy_file, data)
        yield event.plain_result(f"'{project_name}' 开团成功，成团金额为 {target_amount} 元！")

    @filter.command("拼团", alias={"参团"})
    async def participate_groupbuy(self, event: AstrMessageEvent):
        """拼团 <名称> <参与金额>"""
        group_id = self._group_id_or_none(event)
        if not group_id:
            yield event.plain_result("请在群聊中使用该命令。")
            return

        self._record_group_umo(group_id, event.unified_msg_origin)
        args = self._extract_args(event, {"拼团", "参团"}).split()
        if len(args) != 2:
            yield event.plain_result("请输入正确的格式：拼团 <名称> <参与金额>")
            return

        project_name = args[0]
        try:
            amount = float(args[1])
        except ValueError:
            yield event.plain_result("参与金额必须是数字。")
            return

        data = self._load_json(self.groupbuy_file)
        if group_id not in data or project_name not in data[group_id]:
            yield event.plain_result(f"未找到团购 '{project_name}'！")
            return

        project = data[group_id][project_name]
        if project.get("is_completed", False):
            yield event.plain_result(f"团购 '{project_name}' 已成团，无法修改金额！")
            return

        user_id = str(event.get_sender_id())
        nickname = event.get_sender_name()

        if amount == 0:
            if user_id in project["participants"]:
                project["total_amount"] -= project["participants"][user_id]["amount"]
                del project["participants"][user_id]
                self._save_json(self.groupbuy_file, data)
                yield event.plain_result(f"{nickname} 已从团购 '{project_name}' 中移除！")
            else:
                yield event.plain_result(f"{nickname} 未参与团购 '{project_name}'！")
            return

        if user_id in project["participants"]:
            project["total_amount"] -= project["participants"][user_id]["amount"]

        project["participants"][user_id] = {
            "nickname": nickname,
            "user_id": user_id,
            "amount": amount,
            "paid": False,
        }
        project["total_amount"] += amount

        if project["total_amount"] == project["target_amount"]:
            project["is_completed"] = True
            participant_list = "\n".join(
                f"{p['nickname']}\n({p['user_id']})：{p['amount']}元"
                for p in project["participants"].values()
            )
            self._save_json(self.groupbuy_file, data)
            yield event.plain_result(
                f"团购 '{project_name}' 已成团！参与成员：\n{participant_list}\n\n"
                "请参与成员发送\"已付款\"并附带付款截图进行登记。"
            )
            return

        if project["total_amount"] > project["target_amount"]:
            project["total_amount"] -= amount
            del project["participants"][user_id]
            self._save_json(self.groupbuy_file, data)
            yield event.plain_result(f"参与金额超出成团金额，{nickname} 的参与金额被移除！")
            return

        self._save_json(self.groupbuy_file, data)
        yield event.plain_result(
            f"{nickname} 参与了团购 '{project_name}'，当前金额为 {project['total_amount']} 元。"
        )

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("复团", alias={"重置团购"})
    async def reset_groupbuy(self, event: AstrMessageEvent):
        """复团 <名称>"""
        group_id = self._group_id_or_none(event)
        if not group_id:
            yield event.plain_result("请在群聊中使用该命令。")
            return

        self._record_group_umo(group_id, event.unified_msg_origin)
        project_name = self._extract_args(event, {"复团", "重置团购"}).strip()
        if not project_name:
            yield event.plain_result("请输入团购名称：复团 <名称>")
            return

        data = self._load_json(self.groupbuy_file)
        if group_id not in data or project_name not in data[group_id]:
            yield event.plain_result(f"未找到团购 '{project_name}'！")
            return

        target_amount = data[group_id][project_name]["target_amount"]
        data[group_id][project_name] = {
            "target_amount": target_amount,
            "participants": {},
            "total_amount": 0,
            "is_completed": False,
        }
        self._save_json(self.groupbuy_file, data)
        yield event.plain_result(f"团购 '{project_name}' 已重置！")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("删团", alias={"删除团购"})
    async def delete_groupbuy(self, event: AstrMessageEvent):
        """删团 <名称>"""
        group_id = self._group_id_or_none(event)
        if not group_id:
            yield event.plain_result("请在群聊中使用该命令。")
            return

        self._record_group_umo(group_id, event.unified_msg_origin)
        project_name = self._extract_args(event, {"删团", "删除团购"}).strip()
        if not project_name:
            yield event.plain_result("请输入团购名称：删团 <名称>")
            return

        data = self._load_json(self.groupbuy_file)
        if group_id not in data or project_name not in data[group_id]:
            yield event.plain_result(f"未找到团购 '{project_name}'！")
            return

        del data[group_id][project_name]
        if not data[group_id]:
            del data[group_id]

        self._save_json(self.groupbuy_file, data)
        yield event.plain_result(f"团购 '{project_name}' 已删除！")

    @filter.command("团购列表", alias={"团表"})
    async def list_groupbuy(self, event: AstrMessageEvent):
        """团购列表"""
        group_id = self._group_id_or_none(event)
        if not group_id:
            yield event.plain_result("请在群聊中使用该命令。")
            return

        self._record_group_umo(group_id, event.unified_msg_origin)
        data = self._load_json(self.groupbuy_file)

        if group_id not in data or not data[group_id]:
            yield event.plain_result("本群尚未添加任何团购。")
            return

        project_list = "\n".join(
            f"- {name} (成团金额: {info['target_amount']} 元)"
            for name, info in data[group_id].items()
            if "target_amount" in info and info["target_amount"] > 0
        )
        if not project_list:
            yield event.plain_result("本群没有团购。")
            return

        yield event.plain_result(f"本群的团购：\n{project_list}")

    @filter.command("查团", alias={"查询团购"})
    async def query_groupbuy(self, event: AstrMessageEvent):
        """查团 <名称>"""
        group_id = self._group_id_or_none(event)
        if not group_id:
            yield event.plain_result("请在群聊中使用该命令。")
            return

        self._record_group_umo(group_id, event.unified_msg_origin)
        project_name = self._extract_args(event, {"查团", "查询团购"}).strip()
        if not project_name:
            yield event.plain_result("请输入团购名称：查团 <名称>")
            return

        data = self._load_json(self.groupbuy_file)
        if group_id not in data or project_name not in data[group_id]:
            yield event.plain_result(f"未找到团购 '{project_name}'！")
            return

        project = data[group_id][project_name]
        participant_list = []
        for p in project["participants"].values():
            paid_status = "✅" if p.get("paid", False) else ""
            participant_list.append(f"{paid_status}{p['nickname']}\n({p['user_id']})：{p['amount']}元")

        remaining_amount = project["target_amount"] - project["total_amount"]
        completion_status = "已成团" if project.get("is_completed", False) else "未成团"
        response = (
            f"团购 '{project_name}' ：\n"
            f"成团金额：{project['target_amount']} 元\n"
            f"当前金额：{project['total_amount']} 元\n"
            f"剩余金额：{remaining_amount} 元\n"
            f"状态：{completion_status}\n"
            f"参与成员：\n{chr(10).join(participant_list) if participant_list else '暂无参与成员'}\n"
            "说明：✅表示已付款"
        )
        yield event.plain_result(response)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("添加活动", alias={"开趴"})
    async def add_activity(self, event: AstrMessageEvent):
        """添加活动 <名称>"""
        group_id = self._group_id_or_none(event)
        if not group_id:
            yield event.plain_result("请在群聊中使用该命令。")
            return

        self._record_group_umo(group_id, event.unified_msg_origin)
        args = self._extract_args(event, {"添加活动", "开趴"}).split()
        if len(args) != 1:
            yield event.plain_result("请输入正确的格式：添加活动 <名称>")
            return

        activity_name = args[0]
        data = self._load_json(self.activity_file)
        group_data = data.setdefault(group_id, {})

        if activity_name in group_data:
            yield event.plain_result(f"活动 '{activity_name}' 已存在！")
            return

        group_data[activity_name] = {"participants": []}
        self._save_json(self.activity_file, data)
        yield event.plain_result(f"活动 '{activity_name}' 添加成功！")

    @filter.command("参加活动", alias={"报名"})
    async def participate_activity(self, event: AstrMessageEvent):
        """参加活动 <名称>"""
        group_id = self._group_id_or_none(event)
        if not group_id:
            yield event.plain_result("请在群聊中使用该命令。")
            return

        self._record_group_umo(group_id, event.unified_msg_origin)
        activity_name = self._extract_args(event, {"参加活动", "报名"}).strip()
        if not activity_name:
            yield event.plain_result("请输入正确的格式：参加活动 <名称>")
            return

        data = self._load_json(self.activity_file)
        if group_id not in data or activity_name not in data[group_id]:
            yield event.plain_result(f"未找到活动 '{activity_name}'！")
            return

        user_id = str(event.get_sender_id())
        nickname = event.get_sender_name()
        activity = data[group_id][activity_name]

        if user_id not in [p["user_id"] for p in activity["participants"]]:
            activity["participants"].append({"nickname": nickname, "user_id": user_id})

        self._save_json(self.activity_file, data)
        yield event.plain_result(f"{nickname} 已参加活动 '{activity_name}'！")

    @filter.command("退出活动", alias={"退趴"})
    async def quit_activity(self, event: AstrMessageEvent):
        """退出活动 <名称>"""
        group_id = self._group_id_or_none(event)
        if not group_id:
            yield event.plain_result("请在群聊中使用该命令。")
            return

        self._record_group_umo(group_id, event.unified_msg_origin)
        activity_name = self._extract_args(event, {"退出活动", "退趴"}).strip()
        if not activity_name:
            yield event.plain_result("请输入正确的格式：退出活动 <名称>")
            return

        data = self._load_json(self.activity_file)
        if group_id not in data or activity_name not in data[group_id]:
            yield event.plain_result(f"未找到活动 '{activity_name}'！")
            return

        user_id = str(event.get_sender_id())
        participants = data[group_id][activity_name]["participants"]
        new_participants = [p for p in participants if p["user_id"] != user_id]

        if len(participants) == len(new_participants):
            yield event.plain_result(f"你尚未参加活动 '{activity_name}'！")
            return

        data[group_id][activity_name]["participants"] = new_participants
        self._save_json(self.activity_file, data)
        yield event.plain_result(f"你已退出活动 '{activity_name}'！")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("重置活动", alias={"复趴"})
    async def reset_activity(self, event: AstrMessageEvent):
        """重置活动 <名称>"""
        group_id = self._group_id_or_none(event)
        if not group_id:
            yield event.plain_result("请在群聊中使用该命令。")
            return

        self._record_group_umo(group_id, event.unified_msg_origin)
        activity_name = self._extract_args(event, {"重置活动", "复趴"}).strip()
        if not activity_name:
            yield event.plain_result("请输入活动名称：重置活动 <名称>")
            return

        data = self._load_json(self.activity_file)
        if group_id not in data or activity_name not in data[group_id]:
            yield event.plain_result(f"未找到活动 '{activity_name}'！")
            return

        data[group_id][activity_name]["participants"] = []
        self._save_json(self.activity_file, data)
        yield event.plain_result(f"活动 '{activity_name}' 已重置！")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("删除活动", alias={"删趴"})
    async def delete_activity(self, event: AstrMessageEvent):
        """删除活动 <名称>"""
        group_id = self._group_id_or_none(event)
        if not group_id:
            yield event.plain_result("请在群聊中使用该命令。")
            return

        self._record_group_umo(group_id, event.unified_msg_origin)
        activity_name = self._extract_args(event, {"删除活动", "删趴"}).strip()
        if not activity_name:
            yield event.plain_result("请输入活动名称：删除活动 <名称>")
            return

        data = self._load_json(self.activity_file)
        if group_id not in data or activity_name not in data[group_id]:
            yield event.plain_result(f"未找到活动 '{activity_name}'！")
            return

        del data[group_id][activity_name]
        if not data[group_id]:
            del data[group_id]

        self._save_json(self.activity_file, data)
        yield event.plain_result(f"活动 '{activity_name}' 已删除！")

    @filter.command("查询活动", alias={"查趴"})
    async def query_activity(self, event: AstrMessageEvent):
        """查询活动 <名称>"""
        group_id = self._group_id_or_none(event)
        if not group_id:
            yield event.plain_result("请在群聊中使用该命令。")
            return

        self._record_group_umo(group_id, event.unified_msg_origin)
        activity_name = self._extract_args(event, {"查询活动", "查趴"}).strip()
        if not activity_name:
            yield event.plain_result("请输入活动名称：查询活动 <名称>")
            return

        data = self._load_json(self.activity_file)
        if group_id not in data or activity_name not in data[group_id]:
            yield event.plain_result(f"未找到活动 '{activity_name}'！")
            return

        participants = data[group_id][activity_name]["participants"]
        participant_list = "\n".join(f"{p['nickname']}\n({p['user_id']})" for p in participants)
        yield event.plain_result(
            f"活动 '{activity_name}' ：\n参与成员：\n"
            f"{participant_list if participant_list else '暂无参与成员'}"
        )

    @filter.command("活动列表", alias={"趴表"})
    async def list_activity(self, event: AstrMessageEvent):
        """活动列表"""
        group_id = self._group_id_or_none(event)
        if not group_id:
            yield event.plain_result("请在群聊中使用该命令。")
            return

        self._record_group_umo(group_id, event.unified_msg_origin)
        data = self._load_json(self.activity_file)
        if group_id not in data or not data[group_id]:
            yield event.plain_result("本群尚未添加任何活动。")
            return

        activity_list = "\n".join(f"- {name}" for name in data[group_id].keys())
        if not activity_list:
            yield event.plain_result("本群没有活动。")
            return

        yield event.plain_result(f"本群的活动：\n{activity_list}")

    @filter.command("已付款")
    async def payment_registration_specific(self, event: AstrMessageEvent):
        """已付款 <团购名称>，并附带付款截图"""
        group_id = self._group_id_or_none(event)
        if not group_id:
            return

        self._record_group_umo(group_id, event.unified_msg_origin)
        if not self._has_image(event):
            return

        project_name = self._extract_args(event, {"已付款"}).strip()
        user_id = str(event.get_sender_id())
        data = self._load_json(self.groupbuy_file)
        if group_id not in data:
            return

        if not project_name:
            pending = self._find_pending_payment_projects(data, group_id, user_id)
            if len(pending) == 1:
                project_name = pending[0]
            elif len(pending) > 1:
                projects_list = "\n".join(f"- {name}" for name in pending)
                yield event.plain_result(
                    "您有多个已成团未付款的团购，请指定具体团购名称：\n"
                    f"{projects_list}\n\n使用格式：已付款 <团购名称>"
                )
                return
            else:
                return

        if (
            project_name not in data[group_id]
            or not data[group_id][project_name].get("is_completed", False)
        ):
            return

        project = data[group_id][project_name]
        if user_id not in project["participants"]:
            return
        if project["participants"][user_id].get("paid", False):
            return

        project["participants"][user_id]["paid"] = True
        self._save_json(self.groupbuy_file, data)
        nickname = project["participants"][user_id]["nickname"]
        yield event.plain_result(f"{nickname} 的团购 '{project_name}' 付款登记成功！")

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def payment_registration(self, event: AstrMessageEvent):
        """消息中包含“已付款”时自动尝试登记，需带图片。"""
        if "已付款" not in (event.message_str or ""):
            return
        if not self._has_image(event):
            return

        group_id = self._group_id_or_none(event)
        if not group_id:
            return

        self._record_group_umo(group_id, event.unified_msg_origin)
        user_id = str(event.get_sender_id())
        data = self._load_json(self.groupbuy_file)
        if group_id not in data:
            return

        pending = self._find_pending_payment_projects(data, group_id, user_id)
        if len(pending) == 1:
            project_name = pending[0]
            data[group_id][project_name]["participants"][user_id]["paid"] = True
            self._save_json(self.groupbuy_file, data)
            nickname = data[group_id][project_name]["participants"][user_id]["nickname"]
            yield event.plain_result(f"{nickname} 的付款登记成功！")
        elif len(pending) > 1:
            projects_list = "\n".join(f"- {name}" for name in pending)
            yield event.plain_result(
                "您有多个已成团未付款的团购，请指定具体团购名称：\n"
                f"{projects_list}\n\n使用格式：已付款 <团购名称>"
            )

    async def _daily_status_loop(self):
        while True:
            now = datetime.datetime.now()
            target = now.replace(hour=13, minute=0, second=0, microsecond=0)
            if now >= target:
                target += datetime.timedelta(days=1)

            await asyncio.sleep((target - now).total_seconds())
            await self._send_groupbuy_status()

    async def _send_groupbuy_status(self):
        data = self._load_json(self.groupbuy_file)
        umo_map = self._load_json(self.umo_map_file)

        for group_id, group_data in data.items():
            if not group_data:
                continue
            umo = umo_map.get(group_id)
            if not umo:
                continue

            status_lines = []
            for project_name, project in group_data.items():
                if not isinstance(project, dict) or "target_amount" not in project:
                    continue
                status = "已成团" if project.get("total_amount", 0) >= project.get("target_amount", 0) else "未成团"
                status_lines.append(f"{project_name}：{status}")

            if not status_lines:
                continue

            full_message = (
                "本群团购状态：\n"
                f"{'\\n'.join(status_lines)}\n\n"
                "查询指令：查团 <团购名称>"
            )
            chain = MessageChain().message(full_message)
            try:
                await self.context.send_message(umo, chain)
            except Exception as exc:
                logger.warning(f"buy: send scheduled status failed for group {group_id}: {exc}")

    def _find_pending_payment_projects(
        self,
        data: dict[str, Any],
        group_id: str,
        user_id: str,
    ) -> list[str]:
        pending = []
        for project_name, project in data.get(group_id, {}).items():
            if not isinstance(project, dict):
                continue
            participants = project.get("participants", {})
            if (
                project.get("is_completed", False)
                and user_id in participants
                and not participants[user_id].get("paid", False)
            ):
                pending.append(project_name)
        return pending

    def _has_image(self, event: AstrMessageEvent) -> bool:
        for seg in event.message_obj.message:
            seg_type = getattr(seg, "type", "")
            seg_name = seg.__class__.__name__.lower()
            if str(seg_type).lower() == "image" or seg_name == "image":
                return True
        return False

    def _group_id_or_none(self, event: AstrMessageEvent) -> str | None:
        group_id = event.get_group_id()
        if group_id is None:
            return None
        group_id_str = str(group_id).strip()
        return group_id_str if group_id_str else None

    def _record_group_umo(self, group_id: str, umo: str):
        if not group_id or not umo:
            return
        data = self._load_json(self.umo_map_file)
        if data.get(group_id) == umo:
            return
        data[group_id] = umo
        self._save_json(self.umo_map_file, data)

    def _extract_args(self, event: AstrMessageEvent, commands: set[str]) -> str:
        text = (event.message_str or "").strip()
        if not text:
            return ""

        if text and text[0] in {"/", "!", "。"}:
            text = text[1:].lstrip()

        sorted_cmds = sorted(commands, key=len, reverse=True)
        for cmd in sorted_cmds:
            if text.startswith(cmd):
                return text[len(cmd) :].strip()

        return text

    @staticmethod
    def _ensure_json_file(file_path: Path):
        if not file_path.exists():
            file_path.write_text("{}", encoding="utf-8")

    @staticmethod
    def _load_json(file_path: Path) -> dict[str, Any]:
        try:
            raw = file_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _save_json(file_path: Path, data: dict[str, Any]):
        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
