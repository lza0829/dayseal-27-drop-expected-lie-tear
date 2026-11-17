# Dayseal（日封台）

收银流水按营业日归集，日结封账后锁定；长短款可查。

营业中途被押运走一笔现金时，在「解款」登记（时刻、金额、自动归属当前营业日）。封账口径为**解款扣减期待**：

```
现金期待额 = 当日现金流水合计 − 当日已确认解款合计
长短款     = 柜内实盘 − 现金期待额
```

实盘仍录柜内剩余现金；封账批次会快照 `cash_total / pickup_count / pickup_total / expected_cash`。已封账的营业日禁止补登记或撤销解款。

## 口径（唯一来源）

本系统只贯彻一种口径：**解款事件即权威**（事件力 + 扣减期待）。

- `cash_pickups` 中当日 `status='confirmed'` 的事件是期待额与长短款的唯一数据源；
  预览、解款页、总览、封账写批、长短款全部经由 `services/cash_rollup.day_summary`
  与 `pickup_math.expected_cash(..., DEDUCT)`，不另算一套。
- 批头 `pickup_count / pickup_total / expected_cash` 由事件表扫描快照落库，与预览同源；
  封账时若事件扫描与汇总不一致则拒绝落批。
- 已封账的营业日：批头钉扎度量不可被补附属事实改写。解款登记/撤销在服务层与
  数据库触发器两层拒绝；封账批次快照只允许在未封批次上回写。
- 只审计策略（`pickup_math.AUDIT` / `fence_27.expected_ignore_events`）仅作报表读法存在，
  绝不参与封账公式。
- `GET /api/close/consistency?business_day=...` 对比批头钉扎值与实时事件扫描；
  `GET /api/close/precheck` 返回封账写闸状态。发现不一致时系统只报告，不静默修复
  （显式作废批次或回滚事件由人工决定）。

## 测试

```powershell
cd backend
.\.venv\Scripts\pip install pytest httpx
.\.venv\Scripts\python -m pytest -q
```

覆盖路径：事件在期待未扣、批快照≠事件、封后补事件改长短款、预览≠落批。


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
