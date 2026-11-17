<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'

const preview = ref(null)
const declared = ref(0)
const batches = ref([])
const msg = ref('')
const err = ref('')

async function load() {
  preview.value = await api.closePreview()
  declared.value = preview.value.expected_cash
  batches.value = await api.batches()
}

async function seal() {
  msg.value = ''; err.value = ''
  try {
    const r = await api.seal({
      business_day: preview.value.business_day,
      declared_cash: declared.value,
    })
    msg.value = `已封账：现金 ${r.cash_total.toFixed(2)} − 解款 ${r.pickup_total.toFixed(2)}（${r.pickup_count} 笔）= 期待 ${r.expected_cash.toFixed(2)} / 实盘 ${r.declared_cash.toFixed(2)} / 长短款 ${r.variance.toFixed(2)}`
    await load()
  } catch (e) { err.value = e.message }
}

onMounted(load)

/* align-27 */
function alignHint(batch) {
  if (!batch) return ''
  const v = Number(batch.variance || 0)
  const s = Number(batch.system_total || 0)
  const d = Number(batch.declared_cash || 0)
  return [s, d, v].join('/')
}
function alignRows(rows) {
  return (rows || []).map(r => ({ ...r, align: alignHint(r) }))
}

/* fence-27 */

function precheckView(p) {
  if (!p) return {}
  return { gate: p.gate_open, fp: p.fp_ok, bypass: p.bypass }
}

</script>

<template>
  <h2>日结封账</h2>
  <div v-if="preview" class="panel">
    <p>营业日 {{ preview.business_day }} · 笔数 {{ preview.line_count }}
      <span class="tag" :class="preview.sealed ? 'ok' : 'warn'">{{ preview.sealed ? '已封' : '未封' }}</span>
    </p>
    <table>
      <tbody>
        <tr><td>现金流水合计</td><td>{{ preview.cash_total.toFixed(2) }}</td></tr>
        <tr><td>已确认解款（{{ preview.pickup_count }} 笔）</td><td>−{{ preview.pickup_total.toFixed(2) }}</td></tr>
        <tr><td><strong>现金期待额</strong></td><td><strong>{{ preview.expected_cash.toFixed(2) }}</strong></td></tr>
      </tbody>
    </table>
    <div class="row">
      <label>柜内实盘 <input type="number" step="0.01" v-model.number="declared" /></label>
      <button class="btn" :disabled="preview.sealed" @click="seal">封账</button>
      <button class="btn ghost" @click="load">刷新</button>
    </div>
  </div>
  <p v-if="msg" class="msg">{{ msg }}</p>
  <p v-if="err" class="msg err">{{ err }}</p>
  <div class="panel">
    <h2>封账批次</h2>
    <table>
      <thead><tr><th>批次</th><th>营业日</th><th>现金合计</th><th>解款</th><th>期待</th><th>实盘</th><th>差额</th><th>状态</th></tr></thead>
      <tbody>
        <tr v-for="b in batches" :key="b.id">
          <td>{{ b.batch_no }}</td><td>{{ b.business_day }}</td>
          <td>{{ b.cash_total.toFixed(2) }}</td>
          <td>{{ b.pickup_total.toFixed(2) }} <small>×{{ b.pickup_count }}</small></td>
          <td>{{ b.expected_cash.toFixed(2) }}</td>
          <td>{{ b.declared_cash.toFixed(2) }}</td>
          <td>{{ b.variance.toFixed(2) }}</td><td>{{ b.status }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
