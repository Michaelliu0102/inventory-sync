# NetSuite vs Excel 库存自动对比系统

每日自动对比 NetSuite 中的库存与在线表格（意大利→Google Sheets，中国→WPS Docs）中的库存，差异通过飞书推送。

## 快速开始

### 1. 安装依赖

```bash
cd inventory-sync
pip install -r requirements.txt
```

### 2. 配置

```bash
cp config.example.yaml config.yaml
```

编辑 `config.yaml`，填入以下信息：

#### NetSuite TBA 凭证（需在 NetSuite 管理后台设置）

1. `Setup > Company > Enable Features > SuiteCloud`
   - ✅ 勾选 **TOKEN-BASED AUTHENTICATION**
   - ✅ 勾选 **REST WEB SERVICES**

2. `Setup > Company > Company Information` → 记录 **Account ID**

3. `Setup > Integration > Manage Integrations > New`
   - 名称：`Inventory Sync`
   - ✅ 勾选 **Token-Based Authentication**
   - ❌ 取消勾选 OAuth 2.0 下的 **AUTHORIZATION CODE GRANT**（否则会报错 Invalid Redirect URI）
   - 保存后**立即复制** Consumer Key + Consumer Secret（只显示一次！）

4. `Setup > Users/Roles > Manage Roles > New`
   - 名称填写（如 `Inventory Sync Role`），**Center Type**（中心类型）推荐选择 **`Classic Centre`**。
   - 为该角色添加以下权限（在页面下方的 **Permissions** 选项卡中）：
     - **Lists** 子标签：
       - `Items` (Level: View)
       - `Locations` (Level: View)
     - **Setup** 子标签：
       - `REST Web Services` (Level: Full)
       - `Login Using Access Tokens` (Level: Full)
     - **Reports** 或 **Analytics** 子标签（取决于版本）：
       - `SuiteAnalytics Workbook` (Level: Edit)

5. 将角色分配给你的用户
   - 菜单路径：`Setup > Users/Roles > Manage Users`
   - 找到并点击你当前的账号，点击 **Edit**
   - 滚动到底部，点击 **Access**（访问权限）选项卡
   - 在 **Roles**（角色）列表中，添加你刚刚创建的 `Inventory Sync Role`
   - 点击 **Save** 保存

6. `Setup > Users/Roles > Access Tokens > New`
   - 保存后**立即复制** Token ID + Token Secret

#### Google Sheets Service Account

1. 在 [Google Cloud Console](https://console.cloud.google.com/) 创建项目
2. 启用 **Google Sheets API**
3. 创建 **Service Account**（服务账号）并下载 JSON 密钥：
   - （从你的截图那个页面点击左侧侧边栏的 **Credentials**）
   - 点击页面顶部的 **+ CREATE CREDENTIALS**，选择 **Service account**
   - 随便填一个名称，点击 **Create and Continue**，然后一直点 **Done** 完成创建。
   - 创建好后，在列表里点击这个新服务账号的**邮箱地址**
   - 顶部切换到 **KEYS** 选项卡
   - 点击 **ADD KEY** -> **Create new key**
   - 选择 **JSON** 格式并点击 **Create**，这时会自动下载一个 JSON 文件。
   > **⚠️ 常见错误：Service account key creation is disabled**
   > 这是因为你的 Google Cloud 组织默认禁止了创建密钥。解决方法：
   > 1. 在左侧菜单中（IAM and admin 菜单下）找到并点击 **Organisation policies** (组织策略)。*注意：如果你在这个页面无法修改，可能需要点击页面正上方的项目名称（如 My First Project），在弹出的窗口中选择你的整个组织（如 xmk-liu-org）而不是单个项目。*
   > 2. **进入 Organisation policies 页面后**，在这个**页面内部**的列表中（Filter 表格那里，**不要用网页最顶部的全局搜索框！**）搜索 `disableServiceAccountKeyCreation` 并点击弹出的策略名称进行编辑。
   > 3. 点击顶部的 **Manage Policy** (管理策略) 或 **Edit**。
   > 4. 将 Enforcement (强制执行) 设置为 **Off** 取消强制执行并点击 **Save**。
   > 5. 等待 1-2 分钟后，重新尝试创建 JSON 密钥。（创建完成后你可以选择将策略重新开启）
4. 将 JSON 文件保存为 `service_account.json` 到项目目录
5. 将 Google Sheet **分享**给 Service Account 的邮箱（如 `xxx@xxx.iam.gserviceaccount.com`）

#### WPS Docs

- 获取 WPS 文档的**可下载分享链接**，填入 `config.yaml` 的 `wps.download_url`

#### 飞书 Webhook

1. 在飞书群 → 设置 → 群机器人 → 添加自定义机器人
2. 复制 Webhook URL 到 `config.yaml`

### 3. 运行

```bash
# 正常运行（对比 + 推送飞书）
python main.py

# 仅对比，不推送（调试用）
python main.py --dry-run

# 仅对比中国仓库
python main.py --china-only

# 仅对比意大利仓库
python main.py --italy-only
```

### 4. 定时执行（OpenClaw）

在 OpenClaw 中创建定时任务：
> "每天早上 9 点执行 `python /path/to/inventory-sync/main.py`"

或使用 Cron 表达式：`0 9 * * *`

## Excel 表格要求

- **WPS 中国库存**：B 列 = Display Name（与 NetSuite 一致），C 列 = 数量
- **Google Sheets 意大利库存**：配置中指定的列 = Display Name（与 NetSuite 一致），指定列 = 数量
- 两个表格的第一行都是表头

> ⚠️ Excel 中的产品名称必须与 NetSuite 的 Display Name 完全一致才能匹配

## 项目结构

```
inventory-sync/
├── main.py               # 主入口
├── netsuite_client.py     # NetSuite API 客户端
├── sheets_reader.py       # Google Sheets 读取
├── wps_reader.py          # WPS xlsx 下载+解析
├── comparator.py          # 库存对比逻辑
├── feishu_notifier.py     # 飞书推送
├── test_comparator.py     # 单元测试
├── config.example.yaml    # 配置文件模板
├── config.yaml            # 你的配置（不要提交到 git）
└── requirements.txt       # Python 依赖
```
