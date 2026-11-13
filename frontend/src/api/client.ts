export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(method: string, path: string, body?: unknown, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  let payload: BodyInit | undefined
  if (body instanceof ArrayBuffer || body instanceof Blob) {
    payload = body
    headers.set('Content-Type', 'application/octet-stream')
  } else if (body !== undefined) {
    payload = JSON.stringify(body)
    headers.set('Content-Type', 'application/json')
  }

  let res: Response
  try {
    res = await fetch(`/api${path}`, { ...init, method, headers, body: payload })
  } catch {
    throw new ApiError(0, 'Không kết nối được máy chủ. Hãy kiểm tra backend đang chạy.')
  }
  if (res.status === 204) return undefined as T
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    throw new ApiError(res.status, extractMessage(data) ?? `Lỗi máy chủ (${res.status}).`)
  }
  return data as T
}

function extractMessage(data: unknown): string | null {
  if (!data || typeof data !== 'object' || !('detail' in data)) return null
  const detail = (data as { detail: unknown }).detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail[0]?.msg) return `Dữ liệu không hợp lệ: ${detail[0].msg}`
  return null
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  del: (path: string) => request<void>('DELETE', path),
}
