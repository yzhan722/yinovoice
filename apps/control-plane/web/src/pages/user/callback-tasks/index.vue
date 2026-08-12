<template>
  <main class="callback-page">
    <header class="page-head">
      <div>
        <h1>回拨任务</h1>
        <p>规划中 · 演示框架</p>
      </div>
      <span>Demo-only</span>
    </header>

    <section class="planned-card" role="note">
      <h2>电话业务尚未接通</h2>
      <p>
        当前阶段不读取来电号码、回拨队列或任务状态，也不提供完成、重开等业务操作。
        后续接入真实电话系统后，再在这里展示经过租户鉴权的回拨任务。
      </p>
    </section>
  </main>
</template>

<style scoped lang="less">
.callback-page {
  display: grid;
  gap: 16px;
  max-width: 960px;
  margin: 0 auto;
  padding: 8px 4px 40px;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

h1,
h2 {
  margin: 0;
  color: var(--td-text-color-primary, #1d2129);
}

.page-head p {
  margin: 7px 0 0;
  color: var(--td-text-color-secondary, #5e626b);
}

.page-head span {
  padding: 6px 10px;
  color: #0052d9;
  font-weight: 700;
  font-size: 12px;
  background: #e8f1ff;
  border-radius: 999px;
}

.planned-card {
  padding: clamp(22px, 4vw, 32px);
  color: #76520e;
  line-height: 1.7;
  background: #fff8e6;
  border: 1px solid #f3d999;
  border-radius: 12px;
}

.planned-card p {
  max-width: 720px;
  margin: 10px 0 0;
}

@media (max-width: 680px) {
  .page-head {
    flex-direction: column;
  }
}
</style>
