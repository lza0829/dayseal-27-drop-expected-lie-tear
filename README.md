# Dayseal（日封台）

收银流水按营业日归集，日结封账后锁定；长短款可查。

营业中途被押运走一笔现金时，在「解款」登记（时刻、金额、自动归属当前营业日）。封账口径为**解款扣减期待**：

```
现金期待额 = 当日现金流水合计 − 当日已确认解款合计
长短款     = 柜内实盘 − 现金期待额
```

实盘仍录柜内剩余现金；封账批次会快照 `cash_total / pickup_count / pickup_total / expected_cash`。已封账的营业日禁止补登记或撤销解款。

- 前端 http://127.0.0.1:5700
- API http://127.0.0.1:10700

## 启动

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 10700 --app-dir .
```

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5700
```
