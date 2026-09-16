import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import DashboardPage from './Dashboard'

const never = new Promise<never>(() => {})

vi.mock('@panwatch/api', () => ({
  dashboardApi: {
    indices: vi.fn().mockResolvedValue([]),
    intradayScan: vi.fn().mockResolvedValue({ stocks: [] }),
    overview: vi.fn().mockResolvedValue({
      kpis: { watchlist_count: 0 },
      action_center: { opportunities: [], risk_items: [] },
    }),
    portfolioSummary: vi.fn(() => never),
    marketStatus: vi.fn().mockResolvedValue([
      { code: 'CN', name: 'A股快车道', is_trading: false },
    ]),
    brief: vi.fn().mockResolvedValue({ empty: true }),
    curate: vi.fn().mockResolvedValue({ items: [] }),
  },
  portfolioApi: {
    diagnostics: vi.fn(() => never),
    benchmark: vi.fn(() => never),
    attribution: vi.fn(() => never),
    aiReview: vi.fn(),
  },
  recommendationsApi: {
    listStrategySignals: vi.fn().mockResolvedValue({ items: [] }),
  },
  homeApi: {
    alertHitsToday: vi.fn().mockResolvedValue([]),
    todos: vi.fn().mockResolvedValue({ todos: [] }),
  },
}))

vi.mock('@/components/DiscoveryPanel', () => ({ default: () => null }))
vi.mock('@panwatch/biz-ui/components/stock-insight-modal', () => ({ default: () => null }))
vi.mock('@panwatch/biz-ui/components/onboarding', () => ({ Onboarding: () => null }))
vi.mock('@/components/BenchmarkShareCard', () => ({ default: () => null }))
vi.mock('@/components/DiagnosticsShareCard', () => ({ default: () => null }))
vi.mock('@/components/DigestShareCard', () => ({ default: () => null }))

describe('Dashboard loading isolation', () => {
  beforeEach(() => {
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      value: {
        getItem: vi.fn(() => 'true'),
        setItem: vi.fn(),
      },
    })
  })

  it('renders fast dashboard data while portfolio requests remain pending', async () => {
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('A股快车道')).toBeTruthy()
    expect(screen.getByText('今日该看什么')).toBeTruthy()
    expect(await screen.findByText('今日暂无明显异动或触发信号 ✓')).toBeTruthy()
  })
})
