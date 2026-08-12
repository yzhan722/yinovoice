# Logo / 品牌使用规范（Admin Demo）

## 安全区域

- Logo 四周至少保留 **12px** 安全边距，不得紧贴容器或菜单分割线。
- 空间不足时：**先缩小 Logo**（保持比例），或 **增大 logo 容器**；禁止拉伸变形贴边。

## 尺寸

| 场景 | 容器最小高度 | Logo 最大视觉高度 | 最小视觉高度 |
|------|--------------|-------------------|--------------|
| 侧栏展开 | 64px | 40px | 28px |
| 侧栏折叠 | 56px | 40px | 28px |
| 顶栏 | 56px | 32px | 24px |

- 始终 `object-fit: contain`，禁止固定宽高强制裁切。
- 点击 Logo 回到租户首页 `/user/dashboard`。

## 实现位置

- 侧栏：`src/layouts/components/SideNav.vue`
- 顶栏：`src/layouts/components/Header.vue`
