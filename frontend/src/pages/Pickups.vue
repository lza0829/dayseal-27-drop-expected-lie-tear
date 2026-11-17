<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'

const data = ref(null)
const form = ref({ amount: 100, occurred_at: '', note: '' })
const msg = ref('')
const err = ref('')

async function load() {
  data.value = await api.pickups()
}

async function add() {
  msg.value = ''; err.value = ''
  try {
    await api.createPickup({
      business_day: data.value.business_day,
      amount: form.value.amount,
      occurred_at: form.value.occurred_at || undefined,
      note: form.value.note || undefined,
    })
    msg.value = '已登记解款'
    form.value.note = ''
    await load()
  } catch (e) { err.value = e.message }
}

async function remove(id) {
  msg.value = ''; err.value = ''
  try {
    await api.deletePickup(id)
    msg.value = '已撤销解款'
    await load()
  } catch (e) { err.value = e.message }
}

onMounted(load)
</script>

<template>
  <h2>中途解款</h2>
  <p class="msg">押运走一笔即登记一笔；封账时按「现金流水合计 − 已确认解款」计算期待实盘。</p>
  <div v-if="data" class="stats">
    <div class="stat"><div class="label">营业日</div><div class="value">{{ data.business_day }}</div></div>
    <div class="stat"><div class="label">现金流水合计</div><div class="value">{{ data.cash_total.toFixed(2) }}</div></div>
    <div class="stat"><div class="label">已确认解款</div><div class="value">{{ data.pickup_total.toFixed(2) }} <small>（{{ data.pickup_count }} 笔）</small></div></div>
    <div class="stat"><div class="label">现金期待额</div><div class="value">{{ data.expected_cash.toFixed(2) }}</div></div>
  </div>
  <div v-if="data" class="row">
    <label>金额 <input type="number" step="0.01" v-model.number="form.amount" :disabled="data.sealed" /></label>
    <label>时刻 <input v-model="form.occurred_at" placeholder="留空取当前" :disabled="data.sealed" /></label>
    <label>备注 <input v-model="form.note" :disabled="data.sealed" /></label>
    <button class="btn" :disabled="data.sealed" @click="add">登记解款</button>
  </div>
  <p v-if="data && data.sealed" class="msg">营业日已封账，解款锁定不可补登记。</p>
  <p v-if="msg" class="msg">{{ msg }}</p>
  <p v-if="err" class="msg err">{{ err }}</p>
  <div class="panel" v-if="data">
    <table>
      <thead><tr><th>单号</th><th>时刻</th><th>金额</th><th>备注</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="p in data.pickups" :key="p.id">
          <td>{{ p.pickup_no }}</td><td>{{ p.occurred_at }}</td>
          <td>{{ p.amount.toFixed(2) }}</td><td>{{ p.note || '—' }}</td>
          <td><button class="btn ghost" :disabled="data.sealed" @click="remove(p.id)">撤销</button></td>
        </tr>
        <tr v-if="!data.pickups.length"><td colspan="5">当日暂无解款</td></tr>
      </tbody>
    </table>
  </div>
</template>
