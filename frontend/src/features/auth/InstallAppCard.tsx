import { isInstalled, isIos, useInstallPrompt } from '../../lib/pwa/install'

/** "Install the app" help: a one-tap button where the browser supports it, otherwise the manual steps. */
export function InstallAppCard() {
  const { available, install } = useInstallPrompt()
  if (isInstalled()) return null
  return (
    <div className="card stack">
      <div className="card-title" style={{ marginBottom: 0 }}>
        <h3>Cài app lên máy</h3>
      </div>
      <p className="small muted">
        Mở English Tutor từ màn hình chính như app thật: toàn màn hình, không có thanh địa chỉ. App tự cập nhật,
        không cần tải lại từ cửa hàng.
      </p>
      {available ? (
        <div>
          <button className="btn primary" onClick={() => void install()}>
            Cài app
          </button>
        </div>
      ) : isIos() ? (
        <p className="small">
          Trên iPhone / iPad: mở trang này bằng <b>Safari</b>, bấm nút <b>Chia sẻ</b> (ô vuông có mũi tên lên) rồi chọn{' '}
          <b>Thêm vào MH chính</b>.
        </p>
      ) : (
        <p className="small">
          Trên Android: mở bằng <b>Chrome</b>, bấm menu <b>⋮</b> → <b>Cài đặt ứng dụng</b> (hoặc Thêm vào màn hình chính).
          Trên máy tính: dùng Chrome hoặc Edge, bấm biểu tượng cài đặt ở cuối thanh địa chỉ.
        </p>
      )}
    </div>
  )
}
