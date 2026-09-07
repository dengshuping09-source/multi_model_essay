# Alembic migrations

先在 `backend/.env` 配置 `DATABASE_URL`，再在 `backend` 目录运行迁移：

```powershell
alembic upgrade head
```

模型变更后创建新迁移：

```powershell
alembic revision --autogenerate -m "describe change"
```
