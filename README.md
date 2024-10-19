<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <p><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText"></p>
</div>

<div align="center">


# nonebot-plugin-buy

_✨ NoneBot 拼团活动记录插件 ✨_


<a href="./LICENSE">
    <img src="https://img.shields.io/github/license/Onimaimai/nonebot-plugin-buy.svg" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-buy">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-buy.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="python">

</div>

这是一个基于JSON文件的 nonebot2 拼团活动人员记录插件

## 📖 介绍

用于群内拼团和活动记录

## 💿 安装

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot-plugin-buy

</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details>
<summary>pip</summary>

    pip install nonebot-plugin-buy
</details>
<details>
<summary>pdm</summary>

    pdm add nonebot-plugin-buy
</details>
<details>
<summary>poetry</summary>

    poetry add nonebot-plugin-buy
</details>
<details>
<summary>conda</summary>

    conda install nonebot-plugin-buy
</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = ["nonebot_plugin_buy"]

</details>

## 🎉 使用
### 指令表
| 指令 | 权限 | 需要@ | 范围 |
|:-----:|:----:|:----:|:----:|
| 开团<名称><成团金额> | 主人、群管 | 否 | 群聊 
| 拼团<名称><参与金额> | 群员 | 否 | 群聊 
| 查团<名称> | 群员 | 否 | 群聊 
| 复团<名称> | 主人、群管 | 否 | 群聊 
| 删团<名称> | 主人、群管 | 否 | 群聊 
| 团购列表 | 群员 | 否 | 群聊 
### 效果图
![1](https://github.com/user-attachments/assets/06f2fa74-7272-49a2-bb9c-ca6325dcabc5)


