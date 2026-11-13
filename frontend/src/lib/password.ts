/** Same rules as the server (core/security.py: password_problem). */
export const PASSWORD_RULES: { label: string; ok: (p: string) => boolean }[] = [
  { label: 'Ít nhất 8 ký tự', ok: (p) => p.length >= 8 },
  { label: 'Có chữ cái (a–z)', ok: (p) => /\p{L}/u.test(p) },
  { label: 'Có chữ số (0–9)', ok: (p) => /\d/.test(p) },
]

export const passwordStrongEnough = (p: string) => PASSWORD_RULES.every((r) => r.ok(p))
