export type DashboardSection = {
  slug: string;
  label: string;
  eyebrow: string;
  description: string;
  endpoint: string | null;
  deferred?: boolean;
};

export const dashboardSections: DashboardSection[] = [
  {
    slug: "command-centre",
    label: "指挥中心",
    eyebrow: "COMMAND CENTRE",
    description: "市场状态、数据新鲜度、Top 3、重要事件和风险封锁。",
    endpoint: "/api/v1/command-centre",
  },
  {
    slug: "top-10",
    label: "今日 Top 10",
    eyebrow: "TODAY’S TOP 10",
    description: "保留策略、证据、四维评分和数据置信度的候选观察名单。",
    endpoint: "/api/v1/reports/latest",
  },
  {
    slug: "strategy-screener",
    label: "策略筛选",
    eyebrow: "STRATEGY SCREENER",
    description: "以盈利修正、质量、估值、动量和图形确认运行 11 套独立策略。",
    endpoint: "/api/v1/screens/latest",
  },
  {
    slug: "news-trading",
    label: "新闻研究",
    eyebrow: "TRADE WITH NEWS",
    description: "官方来源事件、影响评分、反应窗口与条件计划证据。",
    endpoint: "/api/v1/news",
  },
  {
    slug: "institutional-insider",
    label: "机构与内部人",
    eyebrow: "OWNERSHIP INTELLIGENCE",
    description: "13F、13D/13G 与 Form 4 的结构化确认证据。",
    endpoint: "/api/v1/ownership",
  },
  {
    slug: "intrinsic-value",
    label: "内在价值",
    eyebrow: "INTRINSIC VALUE",
    description: "严格自由现金流、正常化所有者收益与多模型合理价值。",
    endpoint: "/api/v1/valuations/history",
  },
  {
    slug: "unusual-options",
    label: "异常期权",
    eyebrow: "UNUSUAL OPTIONS",
    description: "V1 延后模块；未选择数据提供商，不显示虚构数据。",
    endpoint: null,
    deferred: true,
  },
  {
    slug: "watchlists",
    label: "观察名单",
    eyebrow: "WATCHLISTS",
    description: "版本化观察名单及其候选证据。",
    endpoint: "/api/v1/watchlists",
  },
  {
    slug: "conditional-plans",
    label: "条件计划",
    eyebrow: "CONDITIONAL PLANS",
    description: "等待确认、失效条件和风险定义；不能执行订单。",
    endpoint: "/api/v1/plans",
  },
  {
    slug: "paper-trades",
    label: "模拟交易",
    eyebrow: "PAPER TRADING",
    description: "按 V1 锁定决定关闭；系统不存在订单执行能力。",
    endpoint: null,
    deferred: true,
  },
  {
    slug: "reports-journal",
    label: "报告与日志",
    eyebrow: "REPORTS & JOURNAL",
    description: "中文日报、历史报告、结果追踪和策略表现。",
    endpoint: "/api/v1/reports/history",
  },
  {
    slug: "system-health",
    label: "系统健康",
    eyebrow: "SYSTEM HEALTH",
    description: "运行状态、提供商状态、存储计数和安全边界。",
    endpoint: "/ready",
  },
  {
    slug: "settings",
    label: "设置",
    eyebrow: "SETTINGS",
    description: "只显示非敏感配置状态；任何密钥都不会返回浏览器。",
    endpoint: "/api/status",
  },
];

export function sectionBySlug(slug: string): DashboardSection | undefined {
  return dashboardSections.find((section) => section.slug === slug);
}
