<template>
  <div class="demo-page achievements">
    <div class="page-head">
      <div>
        <h1 class="demo-page-title">成就</h1>
        <p class="demo-page-sub">Recent Badges · 本周运营成就</p>
      </div>
      <div class="count-pill">{{ badges.length }} / 12</div>
    </div>

    <div class="hero demo-card">
      <div class="hero-num">{{ badges.filter((b) => b.earned).length }}</div>
      <div>
        <div class="hero-title">已解锁徽章</div>
        <div class="hero-sub">继续完成回拨与预约确认可解锁更多</div>
      </div>
    </div>

    <h2 class="section-title">Recent Badges</h2>
    <div class="grid">
      <article v-for="b in badges" :key="b.id" class="badge-card" :class="{ locked: !b.earned }">
        <div class="icon" :style="{ background: b.bg }">{{ b.emoji }}</div>
        <div class="name">{{ b.name }}</div>
        <div class="desc">{{ b.desc }}</div>
      </article>
    </div>

    <button type="button" class="celebrate-btn" @click="$router.push('/user/celebration')">打开庆祝页</button>
  </div>
</template>

<script setup lang="ts">
const badges = [
  { id: 1, name: '回拨达人', desc: '单日完成 5 条回拨', emoji: '📞', bg: '#EEF0FF', earned: true },
  { id: 2, name: '预约满档', desc: '今日预约全部确认', emoji: '📅', bg: '#E0F2FE', earned: true },
  { id: 3, name: '连续打卡', desc: '连续 7 天处理跟进', emoji: '🔥', bg: '#FFEDD5', earned: true },
  { id: 4, name: '高接通', desc: '接通率超过 90%', emoji: '🎯', bg: '#DCFCE7', earned: true },
  { id: 5, name: '知识管家', desc: '上传 3 份知识库文件', emoji: '📚', bg: '#FCE7F3', earned: false },
  { id: 6, name: '夜班守护', desc: '晚间完成紧急回拨', emoji: '🌙', bg: '#E0E7FF', earned: false },
];
</script>

<style scoped lang="less">
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.count-pill {
  padding: 8px 12px;
  border-radius: 999px;
  background: var(--demo-primary-soft);
  color: var(--demo-primary);
  font-size: 12px;
  font-weight: 800;
}

.hero {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 18px;
  margin-bottom: 18px;
}

.hero-num {
  width: 64px;
  height: 64px;
  border-radius: 20px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #5b4dff, #7c3aed);
  color: #fff;
  font-size: 28px;
  font-weight: 800;
}

.hero-title {
  font-size: 16px;
  font-weight: 800;
}

.hero-sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--demo-muted);
}

.section-title {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 800;
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.badge-card {
  padding: 16px;
  border-radius: var(--demo-radius);
  background: #fff;
  border: 1px solid var(--demo-line);
  box-shadow: var(--demo-shadow);
  text-align: center;

  &.locked {
    opacity: 0.45;
    filter: grayscale(0.4);
  }
}

.icon {
  width: 56px;
  height: 56px;
  margin: 0 auto 10px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 26px;
}

.name {
  font-size: 14px;
  font-weight: 800;
}

.desc {
  margin-top: 4px;
  font-size: 12px;
  color: var(--demo-muted);
}

.celebrate-btn {
  margin-top: 20px;
  width: 100%;
  border: 0;
  border-radius: 999px;
  padding: 12px;
  background: var(--demo-primary);
  color: #fff;
  font-weight: 800;
  font-family: inherit;
  cursor: pointer;
}

@media (min-width: 769px) {
  .grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .celebrate-btn {
    max-width: 280px;
  }
}
</style>
