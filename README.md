# AI Internship Hunter Agent

一个面向实习求职场景的本地 AI 助手。项目把岗位发现、JD 导入与确认、候选人匹配、求职材料准备和投递跟进串成一套可运行的工作流。

当前版本为 **V1.0.1 本地 MVP**。它适合作为个人求职管理与 AI 应用工程示例，但不是生产级招聘平台。

## 已实现功能

- **岗位发现**：通过 Tavily 搜索公开招聘页面，并进行基础过滤、质量判断与去重。
- **岗位导入与重复检测**：支持粘贴 JD、解析并人工确认岗位字段；保存前按 URL 或公司、岗位名和 JD 内容识别疑似重复。
- **岗位匹配**：结合完整 JD 与本地候选人资料，通过 LLM 生成结构化匹配分、优势、差距和准备建议。
- **岗位管理**：使用 SQLite 持久化岗位和分析结果，支持筛选、查看详情和更新状态。
- **简历优化**：针对已保存岗位生成基于事实的简历调整建议，并缓存结果。
- **面试准备**：结合 JD、候选人资料和匹配结果生成结构化面试准备材料，并缓存结果。
- **投递工作台**：集中管理待投递岗位、材料准备和投递后跟进。
- **申请状态机**：支持 `saved / planned → applied → written_test / interview → offer / rejected / abandoned` 的受控流转。
- **Dashboard 2.0**：汇总投递阶段、关键指标、待办事项、近期变化和重点岗位。

## 当前限制与未实现范围

- **JD 跨平台自动抓取仍不稳定**：动态渲染、登录、反爬、聚合页和页面结构差异都可能导致正文不完整；系统保留人工粘贴和确认 JD 的 fallback。
- **自动投递未实现**：不会登录招聘平台，也不会代替用户提交申请。
- **RAG 未实现**：当前候选人事实来源是本地 Markdown 文件。
- **正式云部署未实现**：当前以本地运行和 Docker Compose 开发体验为主。
- 该项目不应描述为生产级招聘系统，AI 输出也需要用户复核。

## 技术栈

- Python 3.9+
- FastAPI、Pydantic、SQLAlchemy、SQLite
- Streamlit
- DeepSeek API（兼容 OpenAI 接口规范的 Python SDK）
- Tavily API
- pytest

## 首次配置（Windows PowerShell）

### 1. 创建环境并安装依赖

```powershell
py -3.9 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

如果 PowerShell 阻止激活脚本，可仅为当前终端调整策略：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 2. 创建本地私有候选人资料

仓库只提交匿名示例。真实的 `data/profile.md` 和 `data/projects.md` 已被 Git 忽略，首次 clone 后请复制模板：

```powershell
Copy-Item data/profile.example.md data/profile.md
Copy-Item data/projects.example.md data/projects.md
```

然后编辑这两个本地文件，替换为自己确认过的事实：

- `data/profile.md`：教育、技能、经历、求职方向和能力边界。
- `data/projects.md`：项目背景、角色、技术栈、已完成工作、结果和证据边界。

程序始终优先且仅读取这两个本地私有文件。文件缺失或为空时会返回明确错误，不会静默把匿名示例当作真实候选人资料。

### 3. 配置环境变量

```powershell
Copy-Item .env.example .env
```

按需填写：

- `DEEPSEEK_API_KEY`：岗位匹配、简历优化和面试准备所需。
- `TAVILY_API_KEY`：岗位发现所需。
- `BACKEND_URL`：前端访问后端的地址，默认 `http://127.0.0.1:8000`。
- `DATABASE_URL`：默认使用 `storage/database/app.db`。

`.env`、本地候选人资料和数据库文件都不应提交到版本库。

## 启动项目

先启动后端：

```powershell
uvicorn backend.main:app --reload
```

- 后端：<http://127.0.0.1:8000>
- 健康检查：<http://127.0.0.1:8000/health>
- API 文档：<http://127.0.0.1:8000/docs>

另开一个已激活虚拟环境的终端，启动前端：

```powershell
streamlit run frontend/app.py
```

前端默认地址：<http://localhost:8501>

也可以使用 Docker Compose：

```powershell
docker compose up --build
```

## 测试

```powershell
pytest
python -m compileall backend frontend
```

自动化测试覆盖 API、Service、Repository、候选人资料加载、LLM Gateway、Schema、缓存、岗位重复检测、投递队列、状态迁移、Dashboard 和前端 BackendClient。测试通过 Mock 隔离外部模型调用。

## 项目结构

```text
backend/    FastAPI 接口、业务服务、数据访问、解析器与 AI 网关
frontend/   Streamlit 多页面应用
data/       可公开的匿名模板；真实候选人资料仅保存在本地
storage/    本地数据库、简历和导出文件
tests/      单元、集成、API 与前端客户端测试
scripts/    数据库初始化与数据导出脚本
docs/       需求、架构、接口和隐私文档
```

## 隐私说明

请勿把真实姓名、学校、联系方式、履历、奖项、求职偏好、API Key、数据库或生成的简历提交到公开仓库。若真实资料曾进入 Git 历史，仅新增 `.gitignore` 不足以清除它们；公开前必须重建或过滤历史，并重新创建指向干净提交的标签。
