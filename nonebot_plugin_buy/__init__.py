import json
import os
from pathlib import Path
from nonebot import get_bot, require

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store

import datetime
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, Event
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.typing import T_State
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata

__plugin_meta__ = PluginMetadata(
    name="团购",
    description="群内拼团和活动记录",
    usage="发送 团购 help 查看帮助",
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
            if project['total_amount'] >= project['target_amount']:
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
        file_path.write_text('{}', encoding='utf-8')
            
# 加载团购数据
def load_data():
    try:
        with GROUPBUY_DATA_FILE.open('r', encoding='utf-8') as file:
            data = json.load(file)
            return data if data else {}
    except FileNotFoundError:
        return {}

# 保存团购数据
def save_data(data):
    with GROUPBUY_DATA_FILE.open('w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

# 加载活动数据
def load_activity_data():
    try:
        with ACTIVITY_DATA_FILE.open('r', encoding='utf-8') as file:
            data = json.load(file)
            return data if data else {}
    except FileNotFoundError:
        return {}

# 保存活动数据
def save_activity_data(data):
    with ACTIVITY_DATA_FILE.open('w', encoding='utf-8') as file:
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
        "团购列表\n\n"
        "添加活动 <名称>\n"
        "参加活动 <名称>\n"
        "退出活动 <名称>\n"
        "查询活动 <名称>\n"
        "重置活动 <名称>\n"
        "删除活动 <名称>\n"
        "活动列表"
    )
    await groupbuy_help.finish(help_message)
        
        
add_groupbuy = on_command("添加团购", aliases={"开团"}, priority=5, permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER)

@add_groupbuy.handle()
async def handle_add_groupbuy(bot: Bot, event: Event, state: T_State, args: Message = CommandArg()):
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
        "total_amount": 0
    }

    save_data(data)(data)
    await add_groupbuy.finish(f"'{project_name}' 开团成功，成团金额为 {target_amount} 元！")


participate_groupbuy = on_command("拼团", aliases={"参团"}, priority=5)

@participate_groupbuy.handle()
async def handle_participate_groupbuy(bot: Bot, event: Event, state: T_State, args: Message = CommandArg()):
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

    if amount == 0:
        if user_id in project['participants']:
            project['total_amount'] -= project['participants'][user_id]['amount']
            del project['participants'][user_id]
            save_data(data)(data)
            await participate_groupbuy.finish(f"{nickname} 已从团购 '{project_name}' 中移除！")
        else:
            await participate_groupbuy.finish(f"{nickname} 未参与团购 '{project_name}'！")
    else:
        if user_id in project['participants']:
            project['total_amount'] -= project['participants'][user_id]['amount']

        project['participants'][user_id] = {
            "nickname": nickname,
            "user_id": user_id,
            "amount": amount
        }
        project['total_amount'] += amount

        if project['total_amount'] == project['target_amount']:
            participant_list = "\n".join(
                [f"{p['nickname']}\n({p['user_id']})：{p['amount']}元" for p in project['participants'].values()])
            await participate_groupbuy.send(f"团购 '{project_name}' 已成团！参与成员：\n{participant_list}")
        elif project['total_amount'] > project['target_amount']:
            project['total_amount'] -= amount
            del project['participants'][user_id]
            await participate_groupbuy.send(f"参与金额超出成团金额，{nickname} 的参与金额被移除！")
        else:
            await participate_groupbuy.send(f"{nickname} 参与了团购 '{project_name}'，当前金额为 {project['total_amount']} 元。")

        save_data(data)(data)


reset_groupbuy = on_command("重置团购", aliases={"复团"}, priority=5, permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER)

@reset_groupbuy.handle()
async def handle_reset_groupbuy(bot: Bot, event: Event, state: T_State, args: Message = CommandArg()):
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
    target_amount = data[group_id][project_name]['target_amount']
    data[group_id][project_name] = {
        "target_amount": target_amount,
        "participants": {},
        "total_amount": 0
    }

    save_data(data)(data)
    await reset_groupbuy.finish(f"团购 '{project_name}' 已重置！")

# Delete a group-buying project
delete_groupbuy = on_command("删除团购", aliases={"删团"}, priority=5, permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER)

@delete_groupbuy.handle()
async def handle_delete_groupbuy(bot: Bot, event: Event, state: T_State, args: Message = CommandArg()):
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

    save_data(data)(data)
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
        for name, info in data[group_id].items() if 'target_amount' in info and info['target_amount'] > 0
    )

    if not project_list:
        await list_groupbuy.finish("本群没有团购。")
    else:
        await list_groupbuy.finish(f"本群的团购：\n{project_list}")


query_groupbuy = on_command("查询团购", aliases={"查团"}, priority=5)

@query_groupbuy.handle()
async def handle_query_groupbuy(bot: Bot, event: Event, state: T_State, args: Message = CommandArg()):
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
    participant_list = "\n".join(
        [f"{p['nickname']}\n({p['user_id']})：{p['amount']}元" for p in project['participants'].values()]
    )
    remaining_amount = project['target_amount'] - project['total_amount']
    
    response = (
        f"团购 '{project_name}' ：\n"
        f"成团金额：{project['target_amount']} 元\n"
        f"当前金额：{project['total_amount']} 元\n"
        f"剩余金额：{remaining_amount} 元\n"
        f"参与成员：\n{participant_list if participant_list else '暂无参与成员'}"
    )

    await query_groupbuy.finish(response)

    
    
    
    
add_activity = on_command("添加活动", aliases={"开趴"}, priority=5, permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER)

@add_activity.handle()
async def handle_add_activity(bot: Bot, event: Event, state: T_State, args: Message = CommandArg()):
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
async def handle_participate_activity(bot: Bot, event: Event, state: T_State, args: Message = CommandArg()):
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

    if user_id not in activity['participants']:
        activity['participants'].append({"nickname": nickname, "user_id": user_id})

    save_activity_data(data)
    await participate_activity.finish(f"{nickname} 已参加活动 '{activity_name}'！")

    
quit_activity = on_command("退出活动", aliases={"退趴"}, priority=5)

@quit_activity.handle()
async def handle_quit_activity(bot: Bot, event: Event, state: T_State, args: Message = CommandArg()):
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

    participants = activity['participants']
    new_participants = [p for p in participants if p['user_id'] != user_id]

    if len(participants) == len(new_participants):
        await quit_activity.finish(f"你尚未参加活动 '{activity_name}'！")
        return

    activity['participants'] = new_participants
    save_activity_data(data)
    
    await quit_activity.finish(f"你已退出活动 '{activity_name}'！")
    
    
reset_activity = on_command("重置活动", aliases={"复趴"}, priority=5, permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER)

@reset_activity.handle()
async def handle_reset_activity(bot: Bot, event: Event, state: T_State, args: Message = CommandArg()):
    activity_name = args.extract_plain_text().strip()

    if not activity_name:
        await reset_activity.finish("请输入活动名称：重置活动 <名称>")
        return
    
    group_id = str(event.group_id)
    data = load_activity_data()

    if group_id not in data or activity_name not in data[group_id]:
        await reset_activity.finish(f"未找到活动 '{activity_name}'！")
        return

    data[group_id][activity_name]['participants'] = []

    save_activity_data(data)
    await reset_activity.finish(f"活动 '{activity_name}' 已重置！")

    
delete_activity = on_command("删除活动", aliases={"删趴"}, priority=5, permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER)

@delete_activity.handle()
async def handle_delete_activity(bot: Bot, event: Event, state: T_State, args: Message = CommandArg()):
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
async def handle_query_activity(bot: Bot, event: Event, state: T_State, args: Message = CommandArg()):
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
        [f"{p['nickname']}\n({p['user_id']})" for p in activity['participants']]
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
        for name, info in data[group_id].items() if 'target_amount' not in info
    )

    if not activity_list:
        await list_activity.finish("本群没有活动。")
    else:
        await list_activity.finish(f"本群的活动：\n{activity_list}")

