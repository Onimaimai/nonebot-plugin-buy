# astrbot_plugin_buy

群内团购与活动管理插件（AstrBot 版本）。

## 功能

- 团购管理：开团、拼团、查团、复团、删团、团购列表
- 活动管理：添加活动、参加活动、退出活动、查询活动、重置活动、删除活动、活动列表
- 付款登记：发送 `已付款` 并附带截图自动登记
- 每日播报：每天 13:00 自动播报本群团购状态

## 命令

- `团购 help`
- `开团 <名称> <成团金额>`
- `拼团 <名称> <参与金额>`
- `查团 <名称>`
- `复团 <名称>`（管理员）
- `删团 <名称>`（管理员）
- `团购列表`
- `已付款 <团购名称>`（需附图片）
- `添加活动 <名称>`（管理员）
- `参加活动 <名称>`
- `退出活动 <名称>`
- `查询活动 <名称>`
- `重置活动 <名称>`（管理员）
- `删除活动 <名称>`（管理员）
- `活动列表`

## 数据存储

插件数据保存在 `main.py` 同级目录：

- `data/groupbuy_data.json`
- `data/activity_data.json`
- `data/group_umo_map.json`

## 安装（WebUI 上传）

1. 将 `astrbot_plugin_buy` 文件夹压缩为 zip，确保 zip 顶层为单一目录 `astrbot_plugin_buy/`。
2. 在 AstrBot WebUI 的插件上传页面选择该 zip 安装。

## 目录结构

```text
astrbot_plugin_buy/
  main.py
  metadata.yaml
  requirements.txt
  README.md
```
