<script setup lang="ts">
import { Bot, ClipboardList, HardHat, LayoutDashboard, ShieldAlert, Users } from 'lucide-vue-next'

const navItems = [
  { to: '/dashboard', label: '风险驾驶舱', icon: LayoutDashboard },
  { to: '/profiles/projects', label: '项目画像', icon: ShieldAlert },
  { to: '/profiles/workers', label: '工人画像', icon: HardHat },
  { to: '/profiles/subcontractors', label: '分包商画像', icon: Users },
  { to: '/work-orders', label: '工单闭环', icon: ClipboardList },
  { to: '/assistant', label: '安全助手', icon: Bot },
]
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark">CS</span>
        <div>
          <strong>中建智慧安全</strong>
          <small>Project Safety MVP</small>
        </div>
      </div>
      <nav>
        <RouterLink v-for="item in navItems" :key="item.to" :to="item.to">
          <component :is="item.icon" :size="18" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
    </aside>
    <main class="workspace">
      <header class="topbar">
        <div>
          <span class="eyebrow">集团级试点</span>
          <h1>项目工地智慧安全平台</h1>
        </div>
        <div class="topbar-status">
          <span>MySQL 主库</span>
          <span>强规则优先</span>
          <span>Qwen-plus</span>
        </div>
      </header>
      <RouterView />
    </main>
  </div>
</template>
