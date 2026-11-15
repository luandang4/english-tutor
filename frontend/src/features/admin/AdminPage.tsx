import { useState } from 'react'

import { useMeta } from '../../api/hooks'
import { PageHeader } from '../../components/ui'
import { PlansTab } from './PlansTab'
import { SystemTab } from './SystemTab'
import { UsageTab } from './UsageTab'
import { UsersTab } from './UsersTab'
import './admin.css'

type Tab = 'users' | 'plans' | 'usage' | 'system'

const TABS: [Tab, string][] = [
  ['users', 'Người dùng'],
  ['plans', 'Gói'],
  ['usage', 'Sử dụng'],
  ['system', 'Hệ thống'],
]

export function AdminPage() {
  const { data: meta } = useMeta()
  const features = meta?.features ?? []
  const [tab, setTab] = useState<Tab>('users')
  return (
    <div className="page">
      <PageHeader
        title="Quản trị"
        subtitle="Duyệt tài khoản, chọn gói và hạn dùng, cộng thêm lượt, bật / tắt tính năng. Máy chủ kiểm tra lại mọi quyền này ở từng request."
      />
      <div className="tabs" role="tablist">
        {TABS.map(([value, label]) => (
          <button
            key={value}
            role="tab"
            aria-selected={tab === value}
            className={`tab ${tab === value ? 'active' : ''}`}
            onClick={() => setTab(value)}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === 'users' && <UsersTab features={features} />}
      {tab === 'plans' && <PlansTab features={features} />}
      {tab === 'usage' && <UsageTab />}
      {tab === 'system' && <SystemTab features={features} />}
    </div>
  )
}
