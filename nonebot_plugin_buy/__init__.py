import json
import os
from pathlib import Path

from nonebot import get_bot, require

require("nonebot_plugin_localstore")

import datetime

import nonebot_plugin_localstore as store
from nonebot import on_command, on_message
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot, Event, MessageSegment
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
from nonebot.typing import T_State

__plugin_meta__ = PluginMetadata(
    name="团购",
    description="群内拼团和活动记录",
    usage="开团 <名称> <成团金额>\n"
    "拼团 <名称> <参与金额>\n"
    "查团 <名称>\n"
    "复团 <名称>\n"
    "删团 <名称>\n"
    "设置币数 <团购名称> <数量>\n"
    "分币 <团购名称> <币数(可选)>\n"
    "团购列表\n"
    "已付款 <团购名称> [附带付款截图]\n"
    "设置付款 <团购名称> <用户QQ号> <已付款/未付款> [管理员]\n\n"
    "添加活动 <名称>\n"
    "参加活动 <名称>\n"
    "退出活动 <名称>\n"
    "查询活动 <名称>\n"
    "重置活动 <名称>\n"
    "删除活动 <名称>\n"
    "活动列表",
    type="application",
    supported_adapters={"~onebot.v11"},
    homepage="https://github.com/Onimaimai/nonebot-plugin-buy",
)

scheduler = require("nonebot_plugin_apscheduler").scheduler


@scheduler.scheduled_job("cron", hour=13, minute=0)
async def send_groupbuy_status():
    bot = get_bot()
    data = load_data()  # 获取所有团购数据

    for group_id in data.keys():
        group_data = data[group_id]
        if not group_data:
            continue

        groupbuy_status = []
        for project_name, project in group_data.items():
            if project["total_amount"] >= project["target_amount"]:
                status = "已成团"
            else:
                status = "未成团"
            groupbuy_status.append(f"{project_name}：{status}")

        if groupbuy_status:
            status_message = "\n".join(groupbuy_status)
            query_instruction = "查询指令：查团 <团购名称>"
            full_message = f"本群团购状态：\n{status_message}\n\n{query_instruction}"

            try:
                await bot.send_group_msg(group_id=int(group_id), message=full_message)
            except Exception as e:
                # 处理发送消息时的异常
                print(f"发送群 {group_id} 状态消息失败：{e}")


plugin_data_dir: Path = store.get_plugin_data_dir()
# 文件路径
GROUPBUY_DATA_FILE = Path = store.get_plugin_data_file("groupbuy_data.json")
ACTIVITY_DATA_FILE = Path = store.get_plugin_data_file("activity_data.json")


# 创建文件（如果不存在）
for file_path in [GROUPBUY_DATA_FILE, ACTIVITY_DATA_FILE]:
    if not file_path.exists():
        file_path.write_text("{}", encoding="utf-8")


# 加载团购数据
def load_data():
    try:
        with GROUPBUY_DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
            return data if data else {}
    except FileNotFoundError:
        return {}


# 保存团购数据
def save_data(data):
    with GROUPBUY_DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


# 加载活动数据
def load_activity_data():
    try:
        with ACTIVITY_DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
            return data if data else {}
    except FileNotFoundError:
        return {}


# 保存活动数据
def save_activity_data(data):
    with ACTIVITY_DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


groupbuy_help = on_command("团购 help", aliases={"groupbuyhelp"}, priority=5)


@groupbuy_help.handle()
async def handle_groupbuy_help(bot: Bot, event: Event):
    help_message = (
        "团购 help\n"
        "开团 <名称> <成团金额>\n"
        "拼团 <名称> <参与金额>\n"
        "查团 <名称>\n"
        "复团 <名称>\n"
        "删团 <名称>\n"
        "设置币数 <团购名称> <数量>\n"
        "分币 <团购名称> <币数(可选)>\n"
        "团购列表\n"
        "已付款 <团购名称> [附带付款截图]\n"
        "设置付款 <团购名称> <用户QQ号> <已付款/未付款> [管理员]\n\n"
        "添加活动 <名称>\n"
        "参加活动 <名称>\n"
        "退出活动 <名称>\n"
        "查询活动 <名称>\n"
        "重置活动 <名称>\n"
        "删除活动 <名称>\n"
        "活动列表"
    )
    await groupbuy_help.finish(help_message)


add_groupbuy = on_command(
    "添加团购",
    aliases={"开团"},
    priority=5,
)


@add_groupbuy.handle()
async def handle_add_groupbuy(
    bot: Bot, event: Event, state: T_State, args: Message = CommandArg()
):
    args_list = args.extract_plain_text().split()
    if len(args_list) != 2:
        await add_groupbuy.finish("请输入正确的格式：开团 <名称> <成团金额>")
        return

    group_id = str(event.group_id)
    project_name = args_list[0]
    target_amount = float(args_list[1])

    data = load_data()

    if group_id not in data:
        data[group_id] = {}

    if project_name in data[group_id]:
        await add_groupbuy.finish(f"团购 '{project_name}' 已存在！")
        return

    data[group_id][project_name] = {
        "target_amount": target_amount,
        "participants": {},
        "total_amount": 0,
        "is_completed": False,
    }

    save_data(data)
    await add_groupbuy.finish(
        f"'{project_name}' 开团成功，成团金额为 {target_amount} 元！"
    )


participate_groupbuy = on_command("拼团", aliases={"参团"}, priority=5)


@participate_groupbuy.handle()
async def handle_participate_groupbuy(
    bot: Bot, event: Event, state: T_State, args: Message = CommandArg()
):
    args_list = args.extract_plain_text().split()
    if len(args_list) != 2:
        await participate_groupbuy.finish("请输入正确的格式：拼团 <名称> <参与金额>")
        return

    group_id = str(event.group_id)
    user_id = str(event.user_id)
    nickname = event.sender.card if event.sender.card else event.sender.nickname
    project_name = args_list[0]
    amount = float(args_list[1])

    data = load_data()

    if group_id not in data or project_name not in data[group_id]:
        await participate_groupbuy.finish(f"未找到团购 '{project_name}'！")
        return

    project = data[group_id][project_name]

    if project.get("is_completed", False):
        await participate_groupbuy.finish(
            f"团购 '{project_name}' 已成团，无法修改金额！"
        )
        return

    if amount == 0:
        if user_id in project["participants"]:
            project["total_amount"] -= project["participants"][user_id]["amount"]
            del project["participants"][user_id]
            save_data(data)
            await participate_groupbuy.finish(
                f"{nickname} 已从团购 '{project_name}' 中移除！"
            )
        else:
            await participate_groupbuy.finish(
                f"{nickname} 未参与团购 '{project_name}'！"
            )
    else:
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
                [
                    f"{p['nickname']}\n({p['user_id']})：{p['amount']}元"
                    for p in project["participants"].values()
                ]
            )
            await participate_groupbuy.send(
                f"团购 '{project_name}' 已成团！参与成员：\n{participant_list}\n\n请参与成员发送\"已付款\"并附带付款截图进行登记。"
            )
        elif project["total_amount"] > project["target_amount"]:
            project["total_amount"] -= amount
            del project["participants"][user_id]
            await participate_groupbuy.send(
                f"参与金额超出成团金额，{nickname} 的参与金额被移除！"
            )
        else:
            await participate_groupbuy.send(
                f"{nickname} 参与了团购 '{project_name}'，当前金额为 {project['total_amount']} 元。"
            )

        save_data(data)


reset_groupbuy = on_command(
    "重置团购",
    aliases={"复团"},
    priority=5,
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
)


@reset_groupbuy.handle()
async def handle_reset_groupbuy(
    bot: Bot, event: Event, state: T_State, args: Message = CommandArg()
):
    project_name = args.extract_plain_text().strip()

    if not project_name:
        await reset_groupbuy.finish("请输入团购名称：复团 <名称>")
        return

    group_id = str(event.group_id)
    data = load_data()

    if group_id not in data or project_name not in data[group_id]:
        await reset_groupbuy.finish(f"未找到团购 '{project_name}'！")
        return

    # Reset the project to initial state
    target_amount = data[group_id][project_name]["target_amount"]
    data[group_id][project_name] = {
        "target_amount": target_amount,
        "participants": {},
        "total_amount": 0,
        "is_completed": False,
    }

    save_data(data)
    await reset_groupbuy.finish(f"团购 '{project_name}' 已重置！")


# Delete a group-buying project
delete_groupbuy = on_command(
    "删除团购",
    aliases={"删团"},
    priority=5,
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
)


@delete_groupbuy.handle()
async def handle_delete_groupbuy(
    bot: Bot, event: Event, state: T_State, args: Message = CommandArg()
):
    project_name = args.extract_plain_text().strip()

    if not project_name:
        await delete_groupbuy.finish("请输入团购名称：删团 <名称>")
        return

    group_id = str(event.group_id)
    data = load_data()

    if group_id not in data or project_name not in data[group_id]:
        await delete_groupbuy.finish(f"未找到团购 '{project_name}'！")
        return

    del data[group_id][project_name]

    if not data[group_id]:
        del data[group_id]

    save_data(data)
    await delete_groupbuy.finish(f"团购 '{project_name}' 已删除！")


list_groupbuy = on_command("团购列表", aliases={"团表"}, priority=5)


@list_groupbuy.handle()
async def handle_list_groupbuy(bot: Bot, event: Event):
    group_id = str(event.group_id)
    data = load_data()

    if group_id not in data or not data[group_id]:
        await list_groupbuy.finish("本群尚未添加任何团购。")
        return

    # 只筛选出存在 target_amount 的团购项目
    project_list = "\n".join(
        f"- {name} (成团金额: {info['target_amount']} 元)"
        for name, info in data[group_id].items()
        if "target_amount" in info and info["target_amount"] > 0
    )

    if not project_list:
        await list_groupbuy.finish("本群没有团购。")
    else:
        await list_groupbuy.finish(f"本群的团购：\n{project_list}")


query_groupbuy = on_command("查询团购", aliases={"查团"}, priority=5)


@query_groupbuy.handle()
async def handle_query_groupbuy(
    bot: Bot, event: Event, state: T_State, args: Message = CommandArg()
):
    project_name = args.extract_plain_text().strip()

    if not project_name:
        await query_groupbuy.finish("请输入团购名称：查团 <名称>")
        return

    group_id = str(event.group_id)
    data = load_data()

    if group_id not in data or project_name not in data[group_id]:
        await query_groupbuy.finish(f"未找到团购 '{project_name}'！")
        return

    project = data[group_id][project_name]

    # 构建参与成员列表，为已付款用户添加打勾符号
    participant_list = []
    for p in project["participants"].values():
        paid_status = "✅" if p.get("paid", False) else ""
        participant_list.append(
            f"{paid_status}{p['nickname']}\n({p['user_id']})：{p['amount']}元"
        )

    participant_list_str = "\n".join(participant_list)
    remaining_amount = project["target_amount"] - project["total_amount"]

    # 添加成团状态信息
    completion_status = "已成团" if project.get("is_completed", False) else "未成团"

    response = (
        f"团购 '{project_name}' ：\n"
        f"成团金额：{project['target_amount']} 元\n"
        f"当前金额：{project['total_amount']} 元\n"
        f"剩余金额：{remaining_amount} 元\n"
        f"状态：{completion_status}\n"
        f"参与成员：\n{participant_list_str if participant_list_str else '暂无参与成员'}\n"
        f"说明：✅表示已付款"
    )

    await query_groupbuy.finish(response)


add_activity = on_command(
    "添加活动",
    aliases={"开趴"},
    priority=5,
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
)


@add_activity.handle()
async def handle_add_activity(
    bot: Bot, event: Event, state: T_State, args: Message = CommandArg()
):
    args_list = args.extract_plain_text().split()
    if len(args_list) != 1:
        await add_activity.finish("请输入正确的格式：添加活动 <名称>")
        return

    group_id = str(event.group_id)
    activity_name = args_list[0]

    data = load_activity_data()

    if group_id not in data:
        data[group_id] = {}

    if activity_name in data[group_id]:
        await add_activity.finish(f"活动 '{activity_name}' 已存在！")
        return

    data[group_id][activity_name] = {
        "participants": [],
    }

    save_activity_data(data)
    await add_activity.finish(f"活动 '{activity_name}' 添加成功！")


participate_activity = on_command("参加活动", aliases={"报名"}, priority=5)


@participate_activity.handle()
async def handle_participate_activity(
    bot: Bot, event: Event, state: T_State, args: Message = CommandArg()
):
    activity_name = args.extract_plain_text().strip()

    if not activity_name:
        await participate_activity.finish("请输入正确的格式：参加活动 <名称>")
        return

    group_id = str(event.group_id)
    user_id = str(event.user_id)
    nickname = event.sender.card if event.sender.card else event.sender.nickname

    data = load_activity_data()

    if group_id not in data or activity_name not in data[group_id]:
        await participate_activity.finish(f"未找到活动 '{activity_name}'！")
        return

    activity = data[group_id][activity_name]

    if user_id not in activity["participants"]:
        activity["participants"].append({"nickname": nickname, "user_id": user_id})

    save_activity_data(data)
    await participate_activity.finish(f"{nickname} 已参加活动 '{activity_name}'！")


quit_activity = on_command("退出活动", aliases={"退趴"}, priority=5)


@quit_activity.handle()
async def handle_quit_activity(
    bot: Bot, event: Event, state: T_State, args: Message = CommandArg()
):
    activity_name = args.extract_plain_text().strip()

    if not activity_name:
        await quit_activity.finish("请输入正确的格式：退出活动 <名称>")
        return

    group_id = str(event.group_id)
    user_id = str(event.user_id)

    data = load_activity_data()

    if group_id not in data or activity_name not in data[group_id]:
        await quit_activity.finish(f"未找到活动 '{activity_name}'！")
        return

    activity = data[group_id][activity_name]

    participants = activity["participants"]
    new_participants = [p for p in participants if p["user_id"] != user_id]

    if len(participants) == len(new_participants):
        await quit_activity.finish(f"你尚未参加活动 '{activity_name}'！")
        return

    activity["participants"] = new_participants
    save_activity_data(data)

    await quit_activity.finish(f"你已退出活动 '{activity_name}'！")


reset_activity = on_command(
    "重置活动",
    aliases={"复趴"},
    priority=5,
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
)


@reset_activity.handle()
async def handle_reset_activity(
    bot: Bot, event: Event, state: T_State, args: Message = CommandArg()
):
    activity_name = args.extract_plain_text().strip()

    if not activity_name:
        await reset_activity.finish("请输入活动名称：重置活动 <名称>")
        return

    group_id = str(event.group_id)
    data = load_activity_data()

    if group_id not in data or activity_name not in data[group_id]:
        await reset_activity.finish(f"未找到活动 '{activity_name}'！")
        return

    data[group_id][activity_name]["participants"] = []

    save_activity_data(data)
    await reset_activity.finish(f"活动 '{activity_name}' 已重置！")


delete_activity = on_command(
    "删除活动",
    aliases={"删趴"},
    priority=5,
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
)


@delete_activity.handle()
async def handle_delete_activity(
    bot: Bot, event: Event, state: T_State, args: Message = CommandArg()
):
    activity_name = args.extract_plain_text().strip()

    if not activity_name:
        await delete_activity.finish("请输入活动名称：删除活动 <名称>")
        return

    group_id = str(event.group_id)
    data = load_activity_data()

    if group_id not in data or activity_name not in data[group_id]:
        await delete_activity.finish(f"未找到活动 '{activity_name}'！")
        return

    del data[group_id][activity_name]

    if not data[group_id]:
        del data[group_id]

    save_activity_data(data)
    await delete_activity.finish(f"活动 '{activity_name}' 已删除！")


query_activity = on_command("查询活动", aliases={"查趴"}, priority=5)


@query_activity.handle()
async def handle_query_activity(
    bot: Bot, event: Event, state: T_State, args: Message = CommandArg()
):
    activity_name = args.extract_plain_text().strip()

    if not activity_name:
        await query_activity.finish("请输入活动名称：查询活动 <名称>")
        return

    group_id = str(event.group_id)
    data = load_activity_data()

    if group_id not in data or activity_name not in data[group_id]:
        await query_activity.finish(f"未找到活动 '{activity_name}'！")
        return

    activity = data[group_id][activity_name]
    participant_list = "\n".join(
        [f"{p['nickname']}\n({p['user_id']})" for p in activity["participants"]]
    )

    response = f"活动 '{activity_name}' ：\n参与成员：\n{participant_list if participant_list else '暂无参与成员'}"
    await query_activity.finish(response)


list_activity = on_command("活动列表", aliases={"趴表"}, priority=5)


@list_activity.handle()
async def handle_list_activity(bot: Bot, event: Event):
    group_id = str(event.group_id)
    data = load_activity_data()

    if group_id not in data or not data[group_id]:
        await list_activity.finish("本群尚未添加任何活动。")
        return

    activity_list = "\n".join(
        f"- {name}"
        for name, info in data[group_id].items()
        if "target_amount" not in info
    )

    if not activity_list:
        await list_activity.finish("本群没有活动。")
    else:
        await list_activity.finish(f"本群的活动：\n{activity_list}")


# 付款登记功能
payment_registration = on_message(priority=999)


@payment_registration.handle()
async def handle_payment_registration(bot: Bot, event: Event):
    # 检查消息是否包含"已付款"关键词
    message_text = event.get_plaintext()
    if "已付款" not in message_text:
        return

    # 检查是否包含图片
    message_segments = event.get_message()
    has_image = any(seg.type == "image" for seg in message_segments)

    if not has_image:
        # await payment_registration.finish("请附带付款截图进行登记！")
        return

    group_id = str(event.group_id)
    user_id = str(event.user_id)

    # 查找用户参与的已成团团购
    data = load_data()

    if group_id not in data:
        # await payment_registration.finish("本群暂无团购活动。")
        return

    # 查找用户参与的已成团团购
    completed_projects = []
    for project_name, project in data[group_id].items():
        if (
            project.get("is_completed", False)
            and user_id in project["participants"]
            and not project["participants"][user_id].get("paid", False)
        ):
            completed_projects.append(project_name)

    if not completed_projects:
        # await payment_registration.finish("您没有需要付款登记的已成团团购。")
        return

    # 如果只有一个团购，直接登记
    if len(completed_projects) == 1:
        project_name = completed_projects[0]
        data[group_id][project_name]["participants"][user_id]["paid"] = True
        save_data(data)

        nickname = data[group_id][project_name]["participants"][user_id]["nickname"]
        await payment_registration.finish(f"{nickname} 的付款登记成功！")
    if len(completed_projects) > 1:
        # 多个团购时，需要用户指定
        projects_list = "\n".join(f"- {name}" for name in completed_projects)
        await payment_registration.finish(
            f"您有多个已成团未付款的团购，请指定具体团购名称：\n{projects_list}\n\n使用格式：已付款 <团购名称>"
        )


# 指定团购的付款登记功能
payment_registration_specific = on_command("已付款", priority=5)


@payment_registration_specific.handle()
async def handle_payment_registration_specific(
    bot: Bot, event: Event, args: Message = CommandArg()
):
    project_name = args.extract_plain_text().strip()

    if not project_name:
        # await payment_registration_specific.finish("请指定团购名称：已付款 <团购名称>")
        return

    group_id = str(event.group_id)
    user_id = str(event.user_id)

    # 检查消息是否包含图片
    message_segments = event.get_message()
    has_image = any(seg.type == "image" for seg in message_segments)

    if not has_image:
        # await payment_registration_specific.finish("请附带付款截图进行登记！")
        return

    data = load_data()

    if (
        group_id not in data
        or project_name not in data[group_id]
        or not data[group_id][project_name].get("is_completed", False)
    ):
        # await payment_registration_specific.finish(f"团购 '{project_name}' 不存在或未成团。")
        return

    project = data[group_id][project_name]

    if user_id not in project["participants"]:
        # await payment_registration_specific.finish(f"您未参与团购 '{project_name}'。")
        return

    if project["participants"][user_id].get("paid", False):
        # await payment_registration_specific.finish(f"您已经完成团购 '{project_name}' 的付款登记。")
        return

    # 登记付款
    project["participants"][user_id]["paid"] = True
    save_data(data)

    nickname = project["participants"][user_id]["nickname"]
    await payment_registration_specific.finish(
        f"{nickname} 的团购 '{project_name}' 付款登记成功！"
    )


# 处理回复付款截图完成登记
reply_payment_handler = on_message(priority=999)


@reply_payment_handler.handle()
async def handle_reply_payment(bot: Bot, event: Event):
    # 检查是否是回复消息
    if not hasattr(event, "reply") or not event.reply:
        return

    # 检查回复的消息是否包含图片
    try:
        # 获取被回复的消息内容
        reply_message = event.reply.message
        reply_has_image = any(seg.type == "image" for seg in reply_message)

        if not reply_has_image:
            return

        # 检查当前消息是否包含"已付款"关键词
        message_text = event.get_plaintext()
        if "已付款" not in message_text:
            return

        group_id = str(event.group_id)
        user_id = str(event.user_id)

        # 从当前消息中提取团购名称
        message_parts = message_text.split()
        project_name = None

        # 尝试从"已付款 <团购名称>"格式中提取团购名称
        if len(message_parts) > 1:
            project_name = message_parts[1]

        data = load_data()

        if group_id not in data:
            await reply_payment_handler.finish("本群暂无团购活动。")
            return

        # 如果没有指定团购名称，尝试自动匹配
        if not project_name:
            # 查找用户参与的已成团团购
            completed_projects = []
            for proj_name, project in data[group_id].items():
                if (
                    project.get("is_completed", False)
                    and user_id in project["participants"]
                    and not project["participants"][user_id].get("paid", False)
                ):
                    completed_projects.append(proj_name)

            if len(completed_projects) == 1:
                project_name = completed_projects[0]
                data[group_id][project_name]["participants"][user_id]["paid"] = True
                save_data(data)
                nickname = data[group_id][project_name]["participants"][user_id][
                    "nickname"
                ]
                await payment_registration.finish(f"{nickname} 的付款登记成功！")
            elif len(completed_projects) > 1:
                projects_list = "\n".join(f"- {name}" for name in completed_projects)
                await reply_payment_handler.finish(
                    f"您有多个已成团未付款的团购，请指定具体团购名称：\n{projects_list}\n\n使用格式：已付款 <团购名称>"
                )
                return
            else:
                # await reply_payment_handler.finish("您没有需要付款登记的已成团团购。")
                return

        # 验证团购状态
        if project_name not in data[group_id] or not data[group_id][project_name].get(
            "is_completed", False
        ):
            # await reply_payment_handler.finish(f"团购 '{project_name}' 不存在或未成团。")
            return

        project = data[group_id][project_name]

        if user_id not in project["participants"]:
            # await reply_payment_handler.finish(f"您未参与团购 '{project_name}'。")
            return

        if project["participants"][user_id].get("paid", False):
            # await reply_payment_handler.finish(f"您已经完成团购 '{project_name}' 的付款登记。")
            return

        # 登记付款
        project["participants"][user_id]["paid"] = True
        save_data(data)

        nickname = project["participants"][user_id]["nickname"]
        await reply_payment_handler.finish(
            f"{nickname} 的团购 '{project_name}' 付款登记成功！"
        )

    except Exception:
        # 如果处理过程中出现错误，静默忽略
        return


# 管理员指定用户付款状态功能
admin_set_payment = on_command(
    "设置付款",
    aliases={"标记付款"},
    priority=5,
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
)


@admin_set_payment.handle()
async def handle_admin_set_payment(
    bot: Bot, event: Event, args: Message = CommandArg()
):
    args_list = args.extract_plain_text().split()
    if len(args_list) != 3:
        await admin_set_payment.finish(
            "请输入正确的格式：设置付款 <团购名称> <用户QQ号> <已付款/未付款>"
        )
        return

    group_id = str(event.group_id)
    project_name = args_list[0]
    target_user_id = args_list[1]
    payment_status = args_list[2]

    # 验证付款状态参数
    if payment_status not in ["已付款", "未付款"]:
        await admin_set_payment.finish("付款状态只能设置为：已付款 或 未付款")
        return

    # 验证用户ID是否为数字
    if not target_user_id.isdigit():
        await admin_set_payment.finish("用户QQ号必须是数字")
        return

    data = load_data()

    if group_id not in data or project_name not in data[group_id]:
        # await admin_set_payment.finish(f"未找到团购 '{project_name}'！")
        return

    project = data[group_id][project_name]

    if target_user_id not in project["participants"]:
        # await admin_set_payment.finish(f"用户 {target_user_id} 未参与团购 '{project_name}'！")
        return

    # 设置付款状态
    is_paid = payment_status == "已付款"
    project["participants"][target_user_id]["paid"] = is_paid
    save_data(data)

    nickname = project["participants"][target_user_id]["nickname"]
    status_text = "已付款" if is_paid else "未付款"

    await admin_set_payment.finish(
        f"已将用户 {nickname}({target_user_id}) 在团购 '{project_name}' 中的付款状态设置为：{status_text}"
    )


# 设置币数
set_coins = on_command(
    "设置币数",
    priority=5,
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
)


@set_coins.handle()
async def handle_set_coins(bot: Bot, event: Event, args: Message = CommandArg()):
    args_list = args.extract_plain_text().split()
    if len(args_list) != 2:
        await set_coins.finish("请输入正确的格式：设置币数 <团购名称> <数量>")
        return

    group_id = str(event.group_id)
    project_name = args_list[0]

    try:
        coins = int(args_list[1])  # 或者 float，视你的币种需求而定
    except ValueError:
        await set_coins.finish("币数必须是数字！")
        return

    data = load_data()

    if group_id not in data or project_name not in data[group_id]:
        await set_coins.finish(f"未找到团购 '{project_name}'！")
        return

    # 保存默认币数到团购数据中
    data[group_id][project_name]["default_coins"] = coins
    save_data(data)

    await set_coins.finish(f"团购 '{project_name}' 的默认币数已设置为：{coins}")


# 分币
distribution_coins = on_command("分币", priority=5)


@distribution_coins.handle()
async def handle_distribution_coins(
    bot: Bot, event: Event, args: Message = CommandArg()
):
    args_list = args.extract_plain_text().split()
    if len(args_list) < 1 or len(args_list) > 2:
        await distribution_coins.finish("格式：分币 <团购名称> [总币数]")
        return

    group_id = str(event.group_id)
    project_name = args_list[0]

    data = load_data()
    if group_id not in data or project_name not in data[group_id]:
        await distribution_coins.finish(f"未找到团购 '{project_name}'！")
        return

    project = data[group_id][project_name]

    total_coins = 0
    if len(args_list) == 2:
        # 1：用户输入总币数
        try:
            total_coins = float(args_list[1])
        except ValueError:
            await distribution_coins.finish("总币数必须是数字")
            return
    else:
        # 2：未输入，读取已设置的默认币数
        if "default_coins" in project:
            total_coins = float(project["default_coins"])
        else:
            await distribution_coins.finish(
                f"团购 '{project_name}' 未设置默认币数，请使用：分币 <名称> <数量>，先进行设置。"
            )
            return

    # 检查成团金额即分母是否合法
    target_amount = project["target_amount"]
    if target_amount <= 0:
        await distribution_coins.finish(
            f"团购 '{project_name}' 成团金额配置错误(<=0)，无法计算！"
        )
        return

    # 剩余成团所需金额
    current_total = project["total_amount"]
    remaining_needed = target_amount - current_total
    remaining_msg = (
        f"还差 {remaining_needed:.2f} 元成团"
        if remaining_needed > 0
        else "已达到成团金额"
    )

    result = []

    # 计算分币
    for user_id, info in project["participants"].items():
        user_amount = info["amount"]

        # 占比为出资与成团金额比
        ratio = user_amount / target_amount
        user_coins = ratio * total_coins
        result.append(f"{info['nickname']}: {user_coins:.2f}币 (出资:{user_amount}元)")

    result_str = "\n".join(result)

    response = (
        f"团购 '{project_name}' 分币结果：\n"
        f"目标金额：{target_amount}元\n"
        f"当前金额：{current_total}元 ({remaining_msg})\n"
        f"分配总币数：{total_coins}\n"
        f"----------------\n"
        f"{result_str}"
    )

    await distribution_coins.finish(response)
