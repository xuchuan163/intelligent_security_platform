# PyCharm 启动项目说明

推荐直接运行项目根目录的 `main.py`。它会自动完成数据库迁移、演示数据初始化，并同时启动后端和前端。

## 默认端口

| 服务 | 默认地址 |
| --- | --- |
| 后端 API / Swagger | `http://127.0.0.1:8011/docs` |
| 前端页面 | `http://127.0.0.1:5173/work-orders` |

前端 Vite 会通过 `VITE_API_TARGET` 代理到后端，启动器会自动设置为：

```text
VITE_API_TARGET=http://127.0.0.1:8011
```

## 启动前确认

1. 用 PyCharm 打开项目根目录：

   ```text
   E:\职业学习\python沃林\中建智慧安全平台
   ```

2. Python Interpreter 选择：

   ```text
   .venv\Scripts\python.exe
   ```

3. 确认 MySQL 已启动。启动器会优先读取 `.env` 里的 `DATABASE_URL`；如果没有配置，会尝试 `127.0.0.1:3307` 和 `127.0.0.1:3306`。

4. 如果 `frontend/node_modules` 不存在，先执行：

   ```powershell
   cd frontend
   npm install
   ```

## 方式 A：直接运行 main.py

1. 在 PyCharm 左侧找到根目录的 `main.py`
2. 右键 `main.py`
3. 点击 `Run 'main'`

启动成功后访问：

```text
http://127.0.0.1:5173/work-orders
```

后端接口文档：

```text
http://127.0.0.1:8011/docs
```

## 方式 B：使用 Run Configuration

项目提供了共享配置：

```text
.run/PyCharm Start Full Stack.run.xml
```

PyCharm 顶部运行配置选择：

```text
PyCharm Start Full Stack
```

该配置会运行：

```text
main.py --backend-port 8011
```

如果看不到该配置，执行：

```text
File -> Reload All from Disk
```

## 常见问题

### 1. 端口被占用

如果 `8011` 或 `5173` 被占用，启动器会直接提示端口占用。

优先处理：

1. 停掉 PyCharm 里上一次运行的 `main.py`
2. 关闭之前手动启动的后端/前端终端
3. 重新运行 `main.py`

如果确认旧进程就是本项目残留进程，可以在运行参数里加：

```text
--kill-ports
```

如果只想换端口，可以用：

```text
--backend-port 8011 --frontend-port 5174
```

然后访问：

```text
http://127.0.0.1:5174/work-orders
```

### 2. Node/npm 找不到

启动器会优先使用项目本地：

```text
frontend\node_modules\vite\bin\vite.js
```

正常情况下只需要能找到 `node.exe`。如果 PyCharm 找不到 Node，可以在 Run Configuration 的环境变量里配置：

```text
NODE_CMD=C:\Program Files\nodejs\node.exe
```

如果你的 Node 在其他目录，替换为实际路径。

### 3. MySQL 连接失败

检查 `.env`：

```text
DATABASE_URL=mysql+pymysql://root:275874@127.0.0.1:3306/intelligent_security_platform
```

如果使用 Docker MySQL：

```powershell
docker compose -f deploy/docker-compose.yml up -d
```

### 4. 跳过迁移或 seed

数据库已经准备好时，可以加：

```text
--skip-migrate --skip-seed
```
