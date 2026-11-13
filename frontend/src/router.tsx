import type { ComponentType } from 'react'
import { createBrowserRouter } from 'react-router-dom'

import type { Feature } from './api/types'
import { AppShell } from './components/layout/AppShell'
import { AdminGate, FeatureGate } from './components/layout/FeatureGate'
import { EmptyState, Loading } from './components/ui'
import { DashboardPage } from './features/dashboard/DashboardPage'

/** Code-split route that is only rendered when the user may use `feature` (the API checks it too). */
function gated(feature: Feature, load: () => Promise<ComponentType>) {
  return () =>
    load().then((Page) => ({
      Component: () => (
        <FeatureGate feature={feature}>
          <Page />
        </FeatureGate>
      ),
    }))
}

// Feature pages are code-split: each route loads its own chunk on first visit.
export const router = createBrowserRouter([
  {
    path: '/login',
    lazy: () => import('./features/auth/AuthPage').then((m) => ({ Component: () => <m.AuthPage mode="login" /> })),
  },
  {
    path: '/register',
    lazy: () => import('./features/auth/AuthPage').then((m) => ({ Component: () => <m.AuthPage mode="register" /> })),
  },
  {
    element: <AppShell />,
    hydrateFallbackElement: <Loading />,
    children: [
      { path: '/', element: <DashboardPage /> },
      {
        path: '/conversation',
        lazy: gated('conversation', () => import('./features/conversation/ConversationPage').then((m) => m.ConversationPage)),
      },
      {
        path: '/conversation/history',
        lazy: gated('conversation', () =>
          import('./features/conversation/ConversationHistory').then((m) => m.ConversationHistoryPage),
        ),
      },
      {
        path: '/conversation/history/:id',
        lazy: gated('conversation', () =>
          import('./features/conversation/ConversationHistory').then((m) => m.ConversationDetailPage),
        ),
      },
      {
        path: '/vocabulary',
        lazy: gated('vocabulary', () =>
          import('./features/lessons/LessonHubPage').then((m) => () => <m.LessonHubPage skill="vocabulary" />),
        ),
      },
      {
        path: '/vocabulary/lessons/:id',
        lazy: gated('vocabulary', () =>
          import('./features/lessons/LessonPage').then((m) => () => <m.LessonPage skill="vocabulary" />),
        ),
      },
      {
        path: '/grammar',
        lazy: gated('grammar', () =>
          import('./features/lessons/LessonHubPage').then((m) => () => <m.LessonHubPage skill="grammar" />),
        ),
      },
      {
        path: '/grammar/lessons/:id',
        lazy: gated('grammar', () =>
          import('./features/lessons/LessonPage').then((m) => () => <m.LessonPage skill="grammar" />),
        ),
      },
      {
        path: '/writing',
        lazy: gated('writing', () => import('./features/writing/WritingHubPage').then((m) => m.WritingHubPage)),
      },
      {
        path: '/writing/tasks/:id',
        lazy: gated('writing', () => import('./features/writing/WritingTaskPage').then((m) => m.WritingTaskPage)),
      },
      {
        path: '/account',
        lazy: () => import('./features/auth/AccountPage').then((m) => ({ Component: m.AccountPage })),
      },
      {
        path: '/review',
        lazy: () => import('./features/vocabulary/ReviewPage').then((m) => ({ Component: m.ReviewPage })),
      },
      {
        path: '/admin',
        lazy: () =>
          import('./features/admin/AdminPage').then((m) => ({
            Component: () => (
              <AdminGate>
                <m.AdminPage />
              </AdminGate>
            ),
          })),
      },
      {
        path: '*',
        element: (
          <div className="page">
            <EmptyState emoji="🛸" title="Không tìm thấy trang" text="Đường dẫn không tồn tại." />
          </div>
        ),
      },
    ],
  },
])
