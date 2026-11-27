import { useRegisterSW } from 'virtual:pwa-register/react'

import { useOnline } from '../../lib/pwa/online'
import './banners.css'

const UPDATE_CHECK_MS = 60 * 60 * 1000 // installed apps can stay open for days: look for a new build hourly

/** App-wide notices: a new version is ready (the learner chooses when to reload, so a talk is never cut off),
 * and the device is offline. */
export function AppBanners() {
  const online = useOnline()
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW: (_url, reg) => {
      if (reg) window.setInterval(() => void reg.update(), UPDATE_CHECK_MS)
    },
  })

  return (
    <div className="app-banners" aria-live="polite">
      {!online && <div className="app-banner warn">Mất kết nối mạng. Kiểm tra Wi-Fi hoặc 4G rồi thử lại.</div>}
      {needRefresh && (
        <div className="app-banner">
          <span>Đã có bản mới của app.</span>
          <button className="btn primary sm" onClick={() => void updateServiceWorker(true)}>
            Tải lại
          </button>
          <button className="btn ghost sm" onClick={() => setNeedRefresh(false)}>
            Để sau
          </button>
        </div>
      )}
    </div>
  )
}
