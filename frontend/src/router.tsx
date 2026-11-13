import { createBrowserRouter } from 'react-router-dom'

import { AppShell } from './components/layout/AppShell'
import { EmptyState, Loading } from './components/ui'
import { DashboardPage } from './features/dashboard/DashboardPage'

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
        lazy: () => import('./features/conversation/ConversationPage').then((m) => ({ Component: m.ConversationPage })),
      },
      {
        path: '/conversation/history',
        lazy: () =>
          import('./features/conversation/ConversationHistory').then((m) => ({ Component: m.ConversationHistoryPage })),
      },
      {
        path: '/conversation/history/:id',
        lazy: () =>
          import('./features/conversation/ConversationHistory').then((m) => ({ Component: m.ConversationDetailPage })),
      },
      {
        path: '/vocabulary',
        lazy: () =>
          import('./features/lessons/LessonHubPage').then((m) => ({ Component: () => <m.LessonHubPage skill="vocabulary" /> })),
      },
      {
        path: '/vocabulary/lessons/:id',
        lazy: () =>
          import('./features/lessons/LessonPage').then((m) => ({ Component: () => <m.LessonPage skill="vocabulary" /> })),
      },
      {
        path: '/grammar',
        lazy: () =>
          import('./features/lessons/LessonHubPage').then((m) => ({ Component: () => <m.LessonHubPage skill="grammar" /> })),
      },
      {
        path: '/grammar/lessons/:id',
        lazy: () =>
          import('./features/lessons/LessonPage').then((m) => ({ Component: () => <m.LessonPage skill="grammar" /> })),
      },
      {
        path: '/writing',
        lazy: () => import('./features/writing/WritingHubPage').then((m) => ({ Component: m.WritingHubPage })),
      },
      {
        path: '/writing/tasks/:id',
        lazy: () => import('./features/writing/WritingTaskPage').then((m) => ({ Component: m.WritingTaskPage })),
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
